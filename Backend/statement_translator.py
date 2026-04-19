from __future__ import annotations

import asyncio
import ast
import anthropic
import binascii
import json
import os
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Iterator

from fastapi import HTTPException
from google import genai


SUPPORTED_BINARY_OPS: dict[type[ast.operator], Any] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b,
    ast.Mod: lambda a, b: a % b,
}

SUPPORTED_UNARY_OPS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}

MAX_EXPRESSION_LENGTH = 256
MAX_AST_NODES = 128
STRICT_JSON_SCHEMA_DIRECTIVE = (
    'You must respond strictly in valid JSON format matching this schema: '
    '{"result": "Main text with KaTeX", "explanation": ["Step 1", "Step 2", '
    '"STEP 4 [VERIFICATION]: ..."], "topics": ["Concept1", "Concept2"]}.'
)

CALCULATE_MATH_TOOL_SCHEMA = {
    "name": "calculate_math",
    "description": (
        "Deterministically evaluate arithmetic expressions for exact numeric computation. "
        "Use this whenever non-trivial arithmetic is needed instead of mental math."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Arithmetic expression to evaluate, e.g. '0.5 * 9.8 * 2000'.",
            }
        },
        "required": ["expression"],
        "additionalProperties": False,
    },
}


def _validate_ast_tree(tree: ast.AST) -> None:
    node_count = 0
    for node in ast.walk(tree):
        node_count += 1
        if node_count > MAX_AST_NODES:
            raise ValueError("Expression too complex.")
        if isinstance(node, (ast.Call, ast.Name, ast.Attribute, ast.Subscript, ast.Dict, ast.List, ast.Tuple, ast.Set)):
            raise ValueError("Unsupported expression: only numeric arithmetic is allowed.")
        if isinstance(node, ast.BinOp) and type(node.op) not in SUPPORTED_BINARY_OPS:
            raise ValueError("Unsupported operator in expression.")
        if isinstance(node, ast.UnaryOp) and type(node.op) not in SUPPORTED_UNARY_OPS:
            raise ValueError("Unsupported unary operator in expression.")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("Only int and float constants are allowed.")


def _eval_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        return float(SUPPORTED_BINARY_OPS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp):
        operand = _eval_ast(node.operand)
        return float(SUPPORTED_UNARY_OPS[type(node.op)](operand))
    raise ValueError("Unsupported expression structure.")


def calculate_math(expression: str) -> float:
    if not isinstance(expression, str):
        raise ValueError("Expression must be a string.")
    cleaned = expression.strip()
    if not cleaned:
        raise ValueError("Expression cannot be empty.")
    if len(cleaned) > MAX_EXPRESSION_LENGTH:
        raise ValueError("Expression too long.")
    tree = ast.parse(cleaned, mode="eval")
    _validate_ast_tree(tree)
    value = _eval_ast(tree)
    if value in (float("inf"), float("-inf")) or value != value:
        raise ValueError("Expression produced a non-finite result.")
    return float(value)


def sanitize_json(raw_string: str) -> str:
    cleaned = str(raw_string or "")
    cleaned = re.sub(r"```(?:json)?", " ", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", " ")
    return cleaned.strip()


def _extract_thinking_tags(raw_text: str) -> str:
    text = str(raw_text or "")
    segments = re.findall(r"<thinking>([\s\S]*?)</thinking>", text, flags=re.IGNORECASE)
    if not segments:
        segments = re.findall(r"<think>([\s\S]*?)</think>", text, flags=re.IGNORECASE)
    cleaned_segments = [re.sub(r"\s+", " ", segment).strip() for segment in segments if str(segment).strip()]
    return " | ".join(cleaned_segments)


def _extract_live_thinking(raw_text: str) -> str:
    text = str(raw_text or "")
    closed_segments = re.findall(r"<thinking>([\s\S]*?)</thinking>", text, flags=re.IGNORECASE)
    if not closed_segments:
        closed_segments = re.findall(r"<think>([\s\S]*?)</think>", text, flags=re.IGNORECASE)

    open_thinking = text.lower().rfind("<thinking>")
    close_thinking = text.lower().rfind("</thinking>")
    open_think = text.lower().rfind("<think>")
    close_think = text.lower().rfind("</think>")

    trailing = ""
    if open_thinking > close_thinking:
        trailing = text[open_thinking + len("<thinking>"):]
    elif open_think > close_think:
        trailing = text[open_think + len("<think>"):]

    segments = [str(segment) for segment in closed_segments]
    if trailing.strip():
        segments.append(trailing)

    cleaned_segments = [re.sub(r"\s+", " ", segment).strip() for segment in segments if str(segment).strip()]
    return " | ".join(cleaned_segments)


class AnthropicTranslator:
    """Anthropic-first translator for language-heavy word problems."""

    PERSONA_DIRECTIVE = (
        "You are the cognitive core of ADDIX Scholars. You are not a standard AI assistant; you are an elite, uncompromising mentor training a student for the highest levels of competitive physics and mathematics. "
        "\n- You demand absolute rigor. "
        "\n- You do not use overly enthusiastic language or emojis. "
        "\n- If the user makes a dimensional error or a fundamental logic flaw, you point it out directly and ruthlessly before correcting it. "
        "\n- Your tone is stoic, analytical, and demanding. You believe the user is capable of greatness, and you respect them enough to never lower your standards."
    )

    SOCRATIC_ENFORCEMENT_DIRECTIVE = (
        "The user has engaged Socratic Mode. If you give them the final answer, you have failed as a mentor. You must only provide the next logical stepping stone or point out a flaw in their current logic."
    )

    STRICT_SOCRATIC_DIRECTIVE = (
        "CRITICAL: The user is in Socratic Mode. DO NOT solve the problem. "
        "Provide only a leading question or the first mathematical principle required to start the problem. "
        "Refuse to give the final answer."
    )

    SOCRATIC_OVERRIDE = (
        "CRITICAL DIRECTIVE: The user is in Socratic Tutor Mode. DO NOT solve the problem. "
        "DO NOT output the final answer. You must analyze the user's question, identify the first "
        "logical step or the core principle required, and output a guided hint or a leading question. "
        "Modify your JSON output to reflect a 'Hint' instead of a 'Solution'."
    )
    CRITIC_PROMPT = (
        "Here is a physics/math question and a proposed JSON answer. Verify the math, units, and logic. "
        "If it is 100% correct, output 'PASS'. If there is a hallucination or error, output the exact correction."
    )

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.primary_model = "claude-3-5-sonnet-20241022"
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        else:
            self.gemini_client = None
        self.system_prompt = (
            "You are the cognitive core of ADDIX Scholars, an elite Olympiad physics and math AI. YOU MUST NOT HALLUCINATE. "
            "When heavy arithmetic is needed, you MUST call the calculate_math tool and use its deterministic output. "
            "Before providing your final JSON response, you MUST think step-by-step inside <thinking></thinking> XML tags. "
            "Inside these tags: break down the variables, state the exact formulas, verify units (e.g., grams to kg), and perform a dimensional analysis check. "
            "You are the ADDIX Scholars language and logic engine. "
            "Your sole purpose is to translate complex, messy human language regarding physics and math "
            "into deterministic, structured data. "
            "Rule 1: Understand the context of the word problem. Identify implicit variables "
            "(e.g., 'starts from rest' means initial velocity = 0). "
            "Rule 2: Convert ALL extracted variables into strict SI units (meters, seconds, kilograms) "
            "based on your language comprehension. "
            "Rule 3: Output ONLY valid JSON containing 'variables' (dict), 'target' (string), "
            "'topics' (array of 2 to 4 short academic concept strings), and 'explanation' (list of 4 logical steps). "
            "CRITICAL DIRECTIVE: You must analyze the physics/math problem and classify it into 2 to 4 core academic concepts (e.g., 'Conservation of Energy', 'Trigonometry', 'Stoichiometry'). Output these strictly as short strings in the 'topics' array. "
            "CRITICAL COGNITIVE PROTOCOL: Inside your reasoning phase, you MUST perform a 'Backward Verification'. "
            "Once you derive the final formula or value, mentally plug the variables back in to ensure both sides of the equation balance and the units are homogenous (Dimensional Analysis). For mechanics and kinematics, explicitly verify boundary conditions (e.g., time cannot be negative). If the logic fails, re-derive before outputting JSON. "
            "Strict edge-case rules: For kinematics and mechanics, explicitly check boundary conditions "
            "(e.g., verify time is not negative, ensure energy is conserved). For inequalities, verify the sign direction."
        )
        self.contexts_dir = Path(__file__).resolve().parent / "contexts"

    def _load_syllabus_boundaries(self, exam_context: str) -> str:
        context_key = str(exam_context or "").strip().lower()
        syllabus_files = {
            "nsejs level": "nsejs_syllabus.txt",
            "ioqm level": "ioqm_syllabus.txt",
            "jee level": "jee_syllabus.txt",
        }
        filename = syllabus_files.get(context_key)
        if not filename:
            return ""

        syllabus_path = self.contexts_dir / filename
        try:
            file_content = syllabus_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

        if not file_content:
            return ""

        return (
            "You are restricted to the following syllabus boundaries. Do NOT use calculus if the syllabus requires algebra-based physics: "
            + file_content
        )

    def build_system_prompt(self, socratic_mode: bool = False, exam_context: str = "General") -> str:
        prompt = self.system_prompt
        prompt = prompt + " " + self.PERSONA_DIRECTIVE
        exam_context_clean = str(exam_context or "").strip() or "General"
        prompt = prompt + f" Calibrate your rigor to the standard of the {exam_context_clean} examination."
        syllabus_boundaries = self._load_syllabus_boundaries(exam_context_clean)
        if syllabus_boundaries:
            prompt = prompt + " " + syllabus_boundaries
        prompt = prompt + " " + STRICT_JSON_SCHEMA_DIRECTIVE
        if socratic_mode:
            prompt = prompt + " " + self.SOCRATIC_ENFORCEMENT_DIRECTIVE + " " + self.SOCRATIC_OVERRIDE + " " + self.STRICT_SOCRATIC_DIRECTIVE
        return prompt

    def _format_chat_history_context(self, chat_history_context: list[dict[str, Any]] | None) -> str:
        history = chat_history_context or []
        if not history:
            return "No prior turns available."

        lines: list[str] = []
        for item in history[-5:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                lines.append(f"{role}: {content}")

        return "\n".join(lines) if lines else "No prior turns available."

    def _normalize_image_base64(self, image_data: str | None) -> str | None:
        raw = str(image_data or "").strip()
        if not raw:
            return None

        # Accept either raw base64 or data URLs from the frontend.
        if "," in raw and raw.lower().startswith("data:"):
            raw = raw.split(",", 1)[1].strip()

        try:
            binascii.a2b_base64(raw)
        except Exception:
            return None
        return raw

    def _build_user_content(self, user_prompt: str, image_data: str | None = None) -> list[dict[str, Any]]:
        user_content: list[dict[str, Any]] = []
        normalized_image_data = self._normalize_image_base64(image_data)
        if normalized_image_data:
            user_content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": normalized_image_data,
                    },
                }
            )
        user_content.append({"type": "text", "text": user_prompt})
        return user_content

    def iter_solver_stream(
        self,
        statement: str,
        target_hint: str = "target variable",
        chat_history_context: list[dict[str, Any]] | None = None,
        socratic_mode: bool = False,
        exam_context: str = "General",
        image_data: str | None = None,
    ) -> Iterator[dict[str, str]]:
        chat_history_text = self._format_chat_history_context(chat_history_context)
        system_prompt = (
            self.build_system_prompt(socratic_mode=socratic_mode, exam_context=exam_context)
            + " Chat History Context:\n"
            + chat_history_text
        )
        user_prompt = (
            "Translate this problem into deterministic JSON. "
            f"Problem: {statement.strip()} "
            f"Preferred target hint: {target_hint}. "
            "Return keys: variables, target, topics, explanation. "
            f"Chat History Context:\n{chat_history_text}"
        )
        messages = [{"role": "user", "content": self._build_user_content(user_prompt, image_data)}]

        accumulated = ""
        emitted_thinking_len = 0
        stream = self.client.messages.create(
            model=self.primary_model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
            temperature=0.1,
            stream=True,
        )
        for event in stream:
            text_delta = ""
            event_type = str(getattr(event, "type", "") or "")
            if event_type == "content_block_delta":
                text_delta = str(getattr(getattr(event, "delta", None), "text", "") or "")
            elif event_type == "content_block_start":
                text_delta = str(getattr(getattr(event, "content_block", None), "text", "") or "")
            elif hasattr(event, "text"):
                text_delta = str(getattr(event, "text", "") or "")

            if not text_delta:
                continue

            accumulated += text_delta
            live_thinking = _extract_live_thinking(accumulated)
            if len(live_thinking) > emitted_thinking_len:
                thought_delta = live_thinking[emitted_thinking_len:]
                emitted_thinking_len = len(live_thinking)
                if thought_delta.strip():
                    yield {"type": "thought", "text": thought_delta}

        yield {"type": "raw", "content": accumulated}

    async def translate_word_problem(
        self,
        statement: str,
        target_hint: str = "target variable",
        chat_history_context: list[dict[str, Any]] | None = None,
        socratic_mode: bool = False,
        exam_context: str = "General",
        image_data: str | None = None,
    ) -> dict[str, Any]:
        if not statement or not statement.strip():
            raise HTTPException(status_code=422, detail="Word problem statement cannot be empty.")

        chat_history_text = self._format_chat_history_context(chat_history_context)
        base_system_prompt = self.build_system_prompt(socratic_mode=socratic_mode, exam_context=exam_context)
        contextual_system_prompt = (
            base_system_prompt
            + " Chat History Context:\n"
            + chat_history_text
        )

        user_prompt = (
            "Translate this problem into deterministic JSON. "
            f"Problem: {statement.strip()} "
            f"Preferred target hint: {target_hint}. "
            "Return keys: variables, target, topics, explanation. "
            "topics must contain 2 to 4 short academic concepts. "
            "explanation must have exactly 4 strings: "
            "1) STEP 1 [SETUP]: extracted variables with SI conversions "
            "2) STEP 2 [CONCEPT]: primary principle/formula "
            "3) STEP 3 [EXECUTION]: computation route "
            "4) STEP 4 [VERIFICATION]: Briefly prove why this answer makes physical or mathematical sense "
            "(e.g., 'The final units resolve correctly to Joules, and the magnitude aligns with the system's total energy.'). "
            f"Chat History Context:\n{chat_history_text}"
        )

        solver_prompt = user_prompt
        try:
            payload: dict[str, Any] | None = None
            thinking_trace = ""
            critic_status = "PASS"
            for _ in range(2):
                content = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._call_anthropic,
                        self.primary_model,
                        solver_prompt,
                        contextual_system_prompt,
                        image_data,
                    ),
                    timeout=8.0,
                )
                extracted_thinking = _extract_thinking_tags(content)
                if extracted_thinking:
                    thinking_trace = extracted_thinking
                payload = self._extract_json(content)

                critic_feedback = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._call_critic,
                        statement.strip(),
                        payload,
                        contextual_system_prompt,
                    ),
                    timeout=5.0,
                )
                if self._critic_passed(critic_feedback):
                    critic_status = "PASS"
                    break

                critic_status = "FAIL"

                solver_prompt = (
                    user_prompt
                    + " Critic correction to apply before finalizing JSON: "
                    + critic_feedback.strip()
                    + " Regenerate a corrected JSON response only."
                )

            if payload is None:
                raise HTTPException(status_code=500, detail="Translator failed to generate payload.")

            variables = payload.get("variables", {})
            if not isinstance(variables, dict):
                payload["variables"] = {}
            payload["target"] = str(payload.get("target", target_hint)).strip() or target_hint
            payload["topics"] = self._normalize_topics(payload.get("topics", []))
            payload["_thinking"] = thinking_trace
            payload["_critic_evaluation"] = critic_status
            return self._normalize_explanation(payload)
        except HTTPException:
            raise
        except asyncio.TimeoutError:
            raise
        except Exception:
            pass

        if self.gemini_api_key:
            try:
                content = await self._call_gemini_fallback(user_prompt, contextual_system_prompt)
                payload = self._extract_json(content)
                variables = payload.get("variables", {})
                if not isinstance(variables, dict):
                    payload["variables"] = {}
                payload["target"] = str(payload.get("target", target_hint)).strip() or target_hint
                payload["topics"] = self._normalize_topics(payload.get("topics", []))
                return self._normalize_explanation(payload)
            except Exception:
                pass

        return self._normalize_explanation(
            {
                "variables": {},
                "target": target_hint,
                "topics": [],
                "explanation": [
                    "STEP 1 [SETUP]: Fallback parser engaged; explicit SI variables not confidently extracted.",
                    "STEP 2 [CONCEPT]: Fallback deterministic law selection from query semantics.",
                    "STEP 3 [EXECUTION]: Proceed with symbolic/local solver safeguards.",
                    "STEP 4 [VERIFICATION]: Apply dimensional and logical consistency checks before final answer.",
                ],
            }
        )

    def _call_anthropic(
        self,
        model_name: str,
        user_prompt: str,
        system_prompt: str | None = None,
        image_data: str | None = None,
    ) -> str:
        prompt = system_prompt or self.system_prompt
        user_content = self._build_user_content(user_prompt, image_data)

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_content},
        ]

        # Allow a bounded tool-use loop: Claude can request deterministic math,
        # receive exact output, and then continue toward the final JSON payload.
        for _ in range(4):
            response = self.client.messages.create(
                model=model_name,
                max_tokens=1024,
                system=prompt,
                messages=messages,
                tools=[CALCULATE_MATH_TOOL_SCHEMA],
                temperature=0.1,
            )

            assistant_blocks: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []
            requested_tool = False

            if getattr(response, "content", None):
                for block in response.content:
                    block_type = getattr(block, "type", "")
                    if block_type == "text":
                        assistant_blocks.append({"type": "text", "text": getattr(block, "text", "")})
                        continue

                    if block_type == "tool_use":
                        requested_tool = True
                        tool_name = getattr(block, "name", "")
                        tool_input = getattr(block, "input", {}) or {}
                        tool_use_id = getattr(block, "id", "")

                        assistant_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": tool_name,
                                "input": tool_input,
                            }
                        )

                        result_payload: dict[str, Any]
                        if tool_name != "calculate_math":
                            result_payload = {"error": f"Unsupported tool requested: {tool_name}"}
                        else:
                            expression = str(tool_input.get("expression", "")).strip()
                            try:
                                value = calculate_math(expression)
                                result_payload = {
                                    "expression": expression,
                                    "value": value,
                                    "value_repr": repr(value),
                                }
                            except Exception as exc:
                                result_payload = {
                                    "expression": expression,
                                    "error": str(exc),
                                }

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": json.dumps(result_payload),
                            }
                        )

            if requested_tool:
                if assistant_blocks:
                    messages.append({"role": "assistant", "content": assistant_blocks})
                messages.append({"role": "user", "content": tool_results})
                continue

            content = ""
            if getattr(response, "content", None):
                chunks: list[str] = []
                for block in response.content:
                    text_value = getattr(block, "text", "")
                    if text_value:
                        chunks.append(str(text_value))
                content = "\n".join(chunks).strip()
            if not content:
                raise HTTPException(status_code=500, detail="Anthropic returned empty content.")
            return str(content)

        raise HTTPException(status_code=500, detail="Anthropic tool loop exhausted without final response.")

    def _critic_passed(self, feedback: str) -> bool:
        return str(feedback or "").strip().upper() == "PASS"

    def _call_critic(
        self,
        question: str,
        proposed_json: dict[str, Any],
        system_prompt: str | None = None,
    ) -> str:
        critic_user_prompt = (
            self.CRITIC_PROMPT
            + "\nQuestion:\n"
            + question
            + "\n\nProposed JSON Answer:\n"
            + json.dumps(proposed_json, ensure_ascii=True)
        )
        critic_response = self.client.messages.create(
            model=self.primary_model,
            max_tokens=256,
            system=(system_prompt or self.system_prompt),
            messages=[{"role": "user", "content": critic_user_prompt}],
            temperature=0.0,
        )

        feedback_chunks: list[str] = []
        if getattr(critic_response, "content", None):
            for block in critic_response.content:
                text_value = getattr(block, "text", "")
                if text_value:
                    feedback_chunks.append(str(text_value))
        feedback = "\n".join(feedback_chunks).strip()
        return feedback or "PASS"

    def _repair_json_candidate(self, candidate: str, attempt: int) -> str:
        repaired = candidate.strip()
        if attempt >= 1:
            repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        if attempt >= 2:
            repaired = re.sub(r"\\(?![\"\\/bfnrtu])", "", repaired)
        return repaired

    async def _call_gemini_fallback(self, user_prompt: str, system_prompt: str | None = None) -> str:
        if not self.gemini_api_key or self.gemini_client is None:
            raise HTTPException(status_code=500, detail="Gemini fallback key missing.")

        prompt_header = system_prompt or self.system_prompt
        prompt = (
            prompt_header
            + " Return ONLY valid JSON with keys variables, target, explanation. "
            + user_prompt
        )

        def _run_gemini() -> str:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return str(getattr(response, "text", "") or "").strip()

        text = await asyncio.to_thread(_run_gemini)
        if not text:
            raise HTTPException(status_code=500, detail="Gemini fallback returned empty content.")
        return text

    def _extract_json(self, text: str, max_retries: int = 2) -> dict[str, Any]:
        if not text or not text.strip():
            raise HTTPException(status_code=500, detail="Translator output is empty.")

        sanitized_text = sanitize_json(text)
        sanitized_text = re.sub(r'<think>.*?</think>', '', sanitized_text, flags=re.DOTALL)
        sanitized_text = re.sub(r'<thinking>.*?</thinking>', '', sanitized_text, flags=re.DOTALL)
        sanitized_text = re.sub(r"</?analysis>", " ", sanitized_text, flags=re.IGNORECASE)
        sanitized_text = sanitized_text.strip()

        # Claude reasoning responses may include extra prose; prefer the final JSON block.
        last_open_brace = sanitized_text.rfind("{")
        search_space = sanitized_text[last_open_brace:] if last_open_brace != -1 else sanitized_text

        match = re.search(r"\{[\s\S]*\}", search_space)
        if not match:
            raise HTTPException(status_code=500, detail="No JSON object found in translator output.")

        raw_json = match.group(0)
        last_error: JSONDecodeError | None = None

        for attempt in range(max_retries + 1):
            candidate = self._repair_json_candidate(raw_json, attempt)
            try:
                payload = json.loads(candidate)
                return self._normalize_explanation(payload)
            except JSONDecodeError as exc:
                last_error = exc
                continue

        assert last_error is not None
        raise HTTPException(
            status_code=500,
            detail=f"JSON parsing failed after {max_retries} retries: {last_error.msg}",
        )

    def _normalize_explanation(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload["topics"] = self._normalize_topics(payload.get("topics", []))
        explanation = payload.get("explanation", [])
        if not isinstance(explanation, list):
            explanation = []

        setup_line = (
            str(explanation[0]).strip()
            if len(explanation) > 0 and str(explanation[0]).strip()
            else "List extracted variables and SI conversions"
        )
        concept_line = (
            str(explanation[1]).strip()
            if len(explanation) > 1 and str(explanation[1]).strip()
            else "Identify the core mathematical or physical law"
        )
        execution_line = (
            str(explanation[2]).strip()
            if len(explanation) > 2 and str(explanation[2]).strip()
            else "Outline the deterministic computation route"
        )
        verification_line = (
            str(explanation[3]).strip()
            if len(explanation) > 3 and str(explanation[3]).strip()
            else "Briefly prove why this answer is physically or mathematically consistent (units, scale, and sign checks)."
        )

        if not setup_line.startswith("STEP 1 [SETUP]:"):
            setup_line = f"STEP 1 [SETUP]: {setup_line}"
        if not concept_line.startswith("STEP 2 [CONCEPT]:"):
            concept_line = f"STEP 2 [CONCEPT]: {concept_line}"
        if not execution_line.startswith("STEP 3 [EXECUTION]:"):
            execution_line = f"STEP 3 [EXECUTION]: {execution_line}"
        if not verification_line.startswith("STEP 4 [VERIFICATION]:"):
            verification_line = f"STEP 4 [VERIFICATION]: {verification_line}"

        payload["explanation"] = [setup_line, concept_line, execution_line, verification_line]
        return payload

    def _normalize_topics(self, topics: Any) -> list[str]:
        if not isinstance(topics, list):
            return []

        normalized: list[str] = []
        for topic in topics:
            topic_text = re.sub(r"\s+", " ", str(topic or "")).strip()
            if not topic_text:
                continue
            if topic_text.lower() in {item.lower() for item in normalized}:
                continue
            normalized.append(topic_text[:48])
            if len(normalized) >= 4:
                break

        return normalized


class DeepSeekTranslator(AnthropicTranslator):
    """Backward-compatible alias for existing imports."""


class StatementTranslator(AnthropicTranslator):
    """Backward-compatible alias for existing imports."""

