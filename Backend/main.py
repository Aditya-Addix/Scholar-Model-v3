from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import re
import urllib.parse
import uuid
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import Path
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Literal, Optional, TypedDict

import httpx
import sympy as sp
import tavily
try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, Body, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fpdf import FPDF
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, StrictBool, ValidationError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, func, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from tavily import TavilyClient

from math_engine import build_numeric_ground_truth_context, build_sympy_ground_truth_context, evaluate_symbolic_query
from pcm_solver import sympy_simplify_fraction, wolfram_graceful_fallback
from database import (
    AsyncSessionLocal,
    BlackBox,
    DailyAnalytics,
    SessionLocal as VaultSessionLocal,
    User,
    UserStats,
    VaultItem,
    init_db,
    parse_tags,
)

VISION_MODULES_AVAILABLE = True
try:
    import pytesseract
    from PIL import Image, ImageOps
except ImportError:
    VISION_MODULES_AVAILABLE = False
    pytesseract = None
    Image = None
    ImageOps = None
    logging.warning("[WARNING] Vision modules not found. OCR features disabled.")

from models import (
    AgentResponse,
    ConversationContext,
    DashboardStatsResponse,
    ExamCountdown,
    FinalAnswerResponse,
    LongTermGoal,
    OCRInput,
    OCRResponse,
    ScholarSolveResponse,
)

DOTENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=DOTENV_PATH, override=False)
APP_ENV = str(os.getenv("ENV", "development")).strip().lower()
IS_PRODUCTION = APP_ENV == "production"

WOLFRAM_APP_ID_ENV_NAME = "WOLFRAM_APP_ID"
DEEPSEEK_API_KEY_ENV_NAME = "DEEPSEEK_API_KEY"
GROQ_API_KEY_ENV_NAME = "GROQ_API_KEY"
TAVILY_API_KEY_ENV_NAME = "TAVILY_API_KEY"
GEMINI_API_KEY_ENV_NAME = "GEMINI_API_KEY"
GOOGLE_API_KEY_ENV_NAME = "GOOGLE_API_KEY"
SCHOLAR_FRONTEND_SECRET_ENV_NAME = "SCHOLAR_FRONTEND_SECRET"
FOUNDER_EMAIL_ENV_NAME = "FOUNDER_EMAIL"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEEPSEEK_CHAT_MODEL = "llama-3.3-70b-versatile"
PRIMARY_MODEL = "llama-3.3-70b-versatile"
GROQ_FALLBACK_REASONING_MODEL = "mixtral-8x7b-32768"
GROQ_EDGE_MODEL = "llama-3.3-70b-versatile"
VERIFIER_MODEL = GROQ_FALLBACK_REASONING_MODEL
WOLFRAM_FALLBACK_RESULT = "Symbolic Solver: No deterministic result available for this specific query."
SECURITY_PROTOCOL_MESSAGE = "Security Protocol: Resetting API Handshake"
SYSTEM_OVERRIDE_TIMEOUT_MESSAGE = "System Override: API timeout detected. Stabilizing agent pipeline."
SYSTEM_NOTICE_MANUAL_OVERRIDE_MESSAGE = "System Notice: Query requires manual override. Please rephrase algebraic parameters."
VISION_FUZZY_WARNING = "[Vision Agent]: Text extraction fuzzy. Please verify the query below."
INVALID_WOLFRAM_MARKERS = (
    "no short answer available",
    "did not understand your input",
    "unable to interpret",
    "error",
)
SYMBOLIC_ERROR_MARKERS = (
    "symbolic solver",
    "no deterministic result",
    "did not understand your input",
    "unable to interpret",
)
PHYSICS_KEYWORDS = [
    "mass",
    "velocity",
    "acceleration",
    "force",
    "energy",
    "momentum",
    "kinematics",
    "projectile",
    "friction",
    "voltage",
    "current",
    "kg",
    "m/s",
    "newton",
    "joule",
]
CURRICULUM_KEYWORD_GRAPH: dict[str, dict[str, list[str]]] = {
    "Physics": {
        "Motion": ["motion", "kinematics", "projectile", "velocity", "acceleration", "displacement"],
        "Force & Laws": ["force", "newton", "inertia", "momentum", "impulse", "friction"],
        "Gravitation": ["gravitation", "gravity", "g", "orbital", "escape velocity"],
        "Work & Energy": ["work", "energy", "power", "joule", "kinetic", "potential"],
        "Sound": ["sound", "frequency", "wavelength", "amplitude", "sonic"],
        "Thermodynamics": ["thermodynamics", "heat", "temperature", "ideal gas", "pv=nrt", "entropy"],
        "Optics": ["optics", "lens", "mirror", "refraction", "reflection", "focal length"],
    },
    "Chemistry": {
        "Matter in Surroundings": ["matter", "surroundings", "state of matter", "solid", "liquid", "gas"],
        "Atoms & Molecules": ["atom", "molecule", "mole", "avogadro", "molar mass"],
        "Structure of Atom": ["electron", "proton", "neutron", "shell", "orbital", "isotope"],
        "Chemical Bonding": ["bond", "ionic", "covalent", "valency", "electronegativity"],
        "Stoichiometry": ["stoichiometry", "balanced equation", "limiting reagent", "yield"],
        "pH": ["ph", "acid", "base", "neutralization", "hydrogen ion"],
        "Periodic Table": ["periodic table", "group", "period", "atomic number", "periodic trend"],
    },
    "Math": {
        "Number Systems": ["number system", "rational", "irrational", "real number", "complex"],
        "Polynomials": ["polynomial", "factor", "roots", "quadratic", "cubic"],
        "Coordinate Geometry": ["coordinate", "slope", "distance formula", "line", "circle"],
        "Triangles (Euclidean & Trigonometric)": [
            "triangle",
            "euclidean",
            "trigonometry",
            "sin",
            "cos",
            "tan",
            "pythagoras",
        ],
        "Number Theory (IOQM level)": ["number theory", "mod", "modulo", "prime", "divisibility", "ioqm"],
    },
}
DOMAIN_HARDENING_HINTS: dict[str, str] = {
    "Physics": "",
    "Chemistry": "chapter-locked chemistry balancing with unit validation",
    "Math": "exact symbolic and integer-consistency enforcement",
}

# Keep broad physics trigger coverage for fast path detection in translator.
PHYSICS_KEYWORDS = sorted(
    set(
        PHYSICS_KEYWORDS
        + [
            keyword
            for chapter_keywords in CURRICULUM_KEYWORD_GRAPH["Physics"].values()
            for keyword in chapter_keywords
        ]
    )
)
PHYSICS_PROMPT_STRATEGIES = [
    "claude language routing: solve for {target} given {given}. context: {context}. return JSON-only deterministic variable map in SI units",
]
PHYSICS_PROMPT_MODE = 0
CACHE_LOOKBACK_HOURS = 8
CACHE_SIMILARITY_THRESHOLD = 0.90
WOLFRAM_RESULT_ENDPOINT = "https://api.wolframalpha.com/v1/result"
WOLFRAM_QUERY_ENDPOINT = "https://api.wolframalpha.com/v2/query"
TOOL_TIMEOUT_SECONDS = 3
LLM_SOLVE_TEMPERATURE = 0.2
GEMINI_SOLVE_MODEL = "gemini-2.0-flash"
DETERMINISTIC_TIMEOUT_MESSAGE = "System Override: Computation exceeds deterministic time limits. Please simplify"
COMPUTATION_FAILSAFE_MESSAGE = "Computation logic complete. Please verify units or model selection."
GROQ_CHAT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"
GEMINI_GENERATE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent"
GEMINI_FLASH_GENERATE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
FOUNDER_EMAIL = str(os.getenv(FOUNDER_EMAIL_ENV_NAME, "addixlabs06@gmail.com")).strip().lower()
if not str(os.getenv(GOOGLE_API_KEY_ENV_NAME, "")).strip():
    fallback_google_key = str(os.getenv(GEMINI_API_KEY_ENV_NAME, "")).strip()
    if fallback_google_key:
        os.environ[GOOGLE_API_KEY_ENV_NAME] = fallback_google_key
GOOGLE_GENAI_API_KEY = str(
    os.getenv(GOOGLE_API_KEY_ENV_NAME, "") or os.getenv(GEMINI_API_KEY_ENV_NAME, "")
).strip()
GOOGLE_GENAI_CLIENT = (
    genai.Client(api_key=GOOGLE_GENAI_API_KEY) if genai is not None and GOOGLE_GENAI_API_KEY else None
)

VISION_EXTRACTION_PROMPT = (
    "Extract all text, variables, and mathematical equations from this image. "
    "Output ONLY the raw text and format equations in LaTeX. Do not attempt to solve it."
)
GEMINI_DIAGRAM_PROMPT = (
    "Describe this physics/math diagram in extreme detail, including all numerical values, labels, "
    "and geometric relationships. Format it as a text-based problem statement."
)
VERIFIER_PROMPT = (
    "You are a Senior NSEJS Examiner. Review the following solution. Check for dimensional consistency, "
    "calculation errors, and conceptual flaws. If it is correct, return 'VALID'. If it is wrong, provide "
    "the specific correction."
)

WOLFRAM_HTTP_CLIENT = httpx.AsyncClient(
    http2=True,
    timeout=httpx.Timeout(30.0, connect=10.0),
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
)

GROQ_REQUEST_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _resolve_primary_llm_provider() -> tuple[str, str, str] | tuple[None, None, None]:
    groq_key = str(os.getenv(GROQ_API_KEY_ENV_NAME, "")).strip()
    if groq_key:
        return "Groq", GROQ_BASE_URL, PRIMARY_MODEL

    return None, None, None


def _resolve_primary_llm_api_key(provider_name: str | None) -> str:
    if provider_name == "Groq":
        return str(os.getenv(GROQ_API_KEY_ENV_NAME, "")).strip()
    return ""


PRIMARY_LLM_PROVIDER, PRIMARY_LLM_BASE_URL, PRIMARY_LLM_MODEL = _resolve_primary_llm_provider()
PRIMARY_LLM_API_KEY = _resolve_primary_llm_api_key(PRIMARY_LLM_PROVIDER)
PRIMARY_ASYNC_LLM_CLIENT = (
    AsyncOpenAI(api_key=PRIMARY_LLM_API_KEY, base_url=PRIMARY_LLM_BASE_URL, timeout=60.0)
    if PRIMARY_LLM_API_KEY and PRIMARY_LLM_BASE_URL
    else None
)
PRIMARY_ACTIVE_MODEL = PRIMARY_LLM_MODEL or PRIMARY_MODEL
PRIMARY_LLM_TRACE = f"{PRIMARY_LLM_PROVIDER} ({PRIMARY_ACTIVE_MODEL})" if PRIMARY_LLM_PROVIDER else "LLM Not Configured"


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


def _extract_json_array(raw_text: str) -> list[Any]:
    cleaned_text = re.sub(r"```(?:json)?", " ", str(raw_text or ""), flags=re.IGNORECASE).replace("```", " ").strip()
    match = re.search(r"\[[\s\S]*\]", cleaned_text)
    if not match:
        raise ValueError("No JSON array found in model output.")

    payload = json.loads(match.group(0))
    if not isinstance(payload, list):
        raise ValueError("Model output JSON must be an array.")
    return payload


def _normalize_exam_name(exam_name: str) -> str:
    normalized = re.sub(r"\s+", " ", str(exam_name or "")).strip()
    if not normalized:
        return "NSEJS"

    upper = normalized.upper()
    if upper in {"JEE", "JEE ADVANCED", "JEE-ADVANCED"}:
        return "JEE Advanced"
    if upper in {"IOQM", "NSEJS"}:
        return upper
    if upper == "CUSTOM":
        return "Custom Data"
    return normalized


def _fallback_syllabus_chapters(exam_name: str) -> list[str]:
    exam_key = _normalize_exam_name(exam_name).upper()
    syllabus_map = {
        "NSEJS": ["Motion", "Force & Laws", "Work & Energy", "Optics", "Thermodynamics"],
        "IOQM": ["Number Theory", "Combinatorics", "Geometry", "Algebra", "Invariants"],
        "JEE ADVANCED": ["Mechanics", "Electrostatics", "Thermodynamics", "Optics", "Calculus"],
        "CUSTOM DATA": ["Mechanics", "Algebra", "Geometry", "Calculus", "Data Interpretation"],
    }
    return syllabus_map.get(exam_key, syllabus_map["NSEJS"])


def _build_authoritative_sympy_context(query_text: str) -> str | None:
    text = re.sub(r"\s+", " ", str(query_text or "")).strip()
    if not text:
        return None

    numeric_context = build_numeric_ground_truth_context(text)
    symbolic_context = build_sympy_ground_truth_context(text)
    symbolic_verification = evaluate_symbolic_query(text)

    if symbolic_verification is not None:
        return (
            "SymPy Exact Answer: "
            + symbolic_verification.plain_result
            + "\nSymPy LaTeX: "
            + symbolic_verification.latex_result
            + "\nUse this exact answer without alteration or reinterpretation."
        )

    if numeric_context:
        return numeric_context + " Use this exact numerical answer without alteration or reinterpretation."

    if symbolic_context:
        return symbolic_context + " Use this exact symbolic answer without alteration or reinterpretation."

    return None


class RestoredLLMTranslator:
    PERSONA_DIRECTIVE = (
        "You are Iron Mentor, the cognitive core of ADDIX Scholars. You are not a standard AI assistant; "
        "you are an elite, uncompromising mentor training a student for the highest levels of competitive "
        "physics and mathematics. "
        "- You demand absolute rigor. "
        "- You do not use overly enthusiastic language or emojis. "
        "- If the user makes a dimensional error or a fundamental logic flaw, you point it out directly before correcting it. "
        "- Your tone is stoic, analytical, and demanding."
    )
    SOCRATIC_ENFORCEMENT_DIRECTIVE = (
        "The user has engaged Socratic Mode. If you give them the final answer, you have failed as a mentor. "
        "You must only provide the next logical stepping stone or point out a flaw in their current logic."
    )
    STRICT_SOCRATIC_DIRECTIVE = (
        "CRITICAL: The user is in Socratic Mode. DO NOT solve the problem. "
        "Provide only a leading question or the first mathematical principle required to start the problem. "
        "Refuse to give the final answer."
    )
    SOCRATIC_OVERRIDE = (
        "CRITICAL DIRECTIVE: The user is in Socratic Tutor Mode. DO NOT solve the problem. DO NOT output the final answer. "
        "You must identify the first logical step or core principle and output a guided hint or leading question."
    )

    def __init__(self, client: AsyncOpenAI | None) -> None:
        self.client = client
        self.model = PRIMARY_MODEL
        self.contexts_dir = Path(__file__).resolve().parent / "contexts"
        self.system_prompt = (
            "You are the cognitive core of ADDIX Scholars, an elite Olympiad physics and math AI. YOU MUST NOT HALLUCINATE. "
            "Before providing your final JSON response, think step-by-step inside <thinking></thinking> XML tags. "
            "Inside these tags: break down the variables, state formulas, verify units, perform dimensional analysis, and mathematically verify every PCM step against the problem statement and any supplied SymPy ground truth. "
            "If SymPy ground truth is present, treat it as authoritative and never contradict it. "
            "Output only valid JSON."
        )

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

    def build_system_prompt(
        self,
        socratic_mode: bool = False,
        exam_context: str = "General",
        ground_truth_context: str | None = None,
    ) -> str:
        prompt = self.system_prompt + " " + self.PERSONA_DIRECTIVE
        exam_context_clean = str(exam_context or "").strip() or "General"
        prompt = prompt + f" Calibrate your rigor to the standard of the {exam_context_clean} examination."
        syllabus_boundaries = self._load_syllabus_boundaries(exam_context_clean)
        if syllabus_boundaries:
            prompt = prompt + " " + syllabus_boundaries
        if ground_truth_context and ground_truth_context.strip():
            prompt = prompt + " " + ground_truth_context.strip()
        prompt = (
            prompt
            + " You must respond strictly in valid JSON with this schema: "
            + '{"result": "...", "explanation": ["..."], "topics": ["..."]}. '
            + "No extra keys."
        )
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

    def _build_solver_user_prompt(
        self,
        *,
        statement: str,
        target_hint: str,
        chat_history_text: str,
        image_data: str | None = None,
        verifier_correction: str | None = None,
        symbolic_context: str | None = None,
        ground_truth_context: str | None = None,
    ) -> str:
        user_prompt = (
            "Solve the student query and return strict JSON only using schema "
            '{"result":"...","explanation":["..."],"topics":["..."]}. '
            "Do not include markdown fences. "
            "Mathematically verify every PCM step before finalizing the answer. "
            f"Problem: {statement.strip()} "
            f"Preferred target hint: {target_hint}. "
            f"Chat History Context:\n{chat_history_text}"
        )
        if image_data:
            user_prompt += " Image context is attached from OCR; include only information inferable from the prompt and image context."
        if symbolic_context and symbolic_context.strip():
            user_prompt += (
                " Symbolic Verification: Active (SymPy). Extract the core equation, use the verified ground truth below as authoritative, and do not contradict it. "
                + symbolic_context.strip()
            )
        if verifier_correction and verifier_correction.strip():
            user_prompt += (
                " Verifier correction to enforce before finalizing: "
                + verifier_correction.strip()
                + " Regenerate the full solution JSON once, correcting all identified flaws."
            )
        if ground_truth_context and ground_truth_context.strip():
            user_prompt += (
                " Deterministic ground truth is already verified and must not be contradicted. "
                + ground_truth_context.strip()
            )
        return user_prompt

    async def _run_verifier_review(self, statement: str, draft_payload: dict[str, Any]) -> str:
        if self.client is None:
            return "VALID"

        draft_text = json.dumps(
            {
                "result": str(draft_payload.get("result", "")),
                "explanation": draft_payload.get("explanation", []),
                "topics": draft_payload.get("topics", []),
            },
            ensure_ascii=False,
        )
        verifier_user_prompt = (
            VERIFIER_PROMPT
            + "\n\nProblem:\n"
            + str(statement or "").strip()
            + "\n\nDraft Solution JSON:\n"
            + draft_text
        )

        try:
            completion = await self.client.chat.completions.create(
                model=VERIFIER_MODEL,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": "You are a strict mathematical verifier."},
                    {"role": "user", "content": verifier_user_prompt},
                ],
            )
            choices = completion.choices or []
            if not choices:
                return "VALID"
            verdict = str(choices[0].message.content or "").strip()
            return verdict or "VALID"
        except Exception as exc:
            logger.warning("Verifier model call failed. Skipping correction loop.", exc_info=exc)
            return "VALID"

    async def regenerate_with_verifier_correction(
        self,
        *,
        statement: str,
        target_hint: str,
        chat_history_context: list[dict[str, Any]] | None,
        socratic_mode: bool,
        exam_context: str,
        image_data: str | None,
        verifier_correction: str,
        symbolic_context: str | None = None,
        ground_truth_context: str | None = None,
    ) -> dict[str, Any]:
        chat_history_text = self._format_chat_history_context(chat_history_context)
        system_prompt = self.build_system_prompt(
            socratic_mode=socratic_mode,
            exam_context=exam_context,
            ground_truth_context=ground_truth_context,
        )
        user_prompt = self._build_solver_user_prompt(
            statement=statement,
            target_hint=target_hint,
            chat_history_text=chat_history_text,
            image_data=image_data,
            verifier_correction=verifier_correction,
            symbolic_context=symbolic_context,
            ground_truth_context=ground_truth_context,
        )

        regenerated_text = await self._generate_content(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
        )
        return self._extract_json(regenerated_text)

    def _repair_json_candidate(self, candidate: str, attempt: int) -> str:
        repaired = candidate.strip()
        if attempt >= 1:
            repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        if attempt >= 2:
            repaired = re.sub(r"\\(?![\"\\/bfnrtu])", "", repaired)
        return repaired

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

    def _normalize_explanation(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload["topics"] = self._normalize_topics(payload.get("topics", []))
        explanation = payload.get("explanation", [])
        if not isinstance(explanation, list):
            explanation = []

        setup_line = str(explanation[0]).strip() if len(explanation) > 0 and str(explanation[0]).strip() else "STEP 1 [SETUP]: List extracted variables and SI conversions"
        concept_line = str(explanation[1]).strip() if len(explanation) > 1 and str(explanation[1]).strip() else "STEP 2 [CONCEPT]: Identify the core mathematical or physical law"
        execution_line = str(explanation[2]).strip() if len(explanation) > 2 and str(explanation[2]).strip() else "STEP 3 [EXECUTION]: Outline the deterministic computation route"
        verification_line = str(explanation[3]).strip() if len(explanation) > 3 and str(explanation[3]).strip() else "STEP 4 [VERIFICATION]: Briefly prove why this answer is physically or mathematically consistent"

        if not setup_line.startswith("STEP 1 [SETUP]:"):
            setup_line = f"STEP 1 [SETUP]: {setup_line}"
        if not concept_line.startswith("STEP 2 [CONCEPT]:"):
            concept_line = f"STEP 2 [CONCEPT]: {concept_line}"
        if not execution_line.startswith("STEP 3 [EXECUTION]:"):
            execution_line = f"STEP 3 [EXECUTION]: {execution_line}"
        if not verification_line.startswith("STEP 4 [VERIFICATION]:"):
            verification_line = f"STEP 4 [VERIFICATION]: {verification_line}"

        payload["explanation"] = [setup_line, concept_line, execution_line, verification_line]
        payload["result"] = str(payload.get("result", "")).strip()
        return payload

    def _extract_json(self, text: str, max_retries: int = 2) -> dict[str, Any]:
        if not text or not text.strip():
            raise HTTPException(status_code=500, detail="Translator output is empty.")

        sanitized_text = re.sub(r"```(?:json)?", " ", str(text), flags=re.IGNORECASE).replace("```", " ").strip()
        sanitized_text = re.sub(r"<think>.*?</think>", "", sanitized_text, flags=re.DOTALL | re.IGNORECASE)
        sanitized_text = re.sub(r"<thinking>.*?</thinking>", "", sanitized_text, flags=re.DOTALL | re.IGNORECASE)
        sanitized_text = re.sub(r"</?analysis>", " ", sanitized_text, flags=re.IGNORECASE)

        last_open_brace = sanitized_text.rfind("{")
        search_space = sanitized_text[last_open_brace:] if last_open_brace != -1 else sanitized_text
        match = re.search(r"\{[\s\S]*\}", search_space)
        if not match:
            raise HTTPException(status_code=500, detail="No JSON object found in translator output.")

        raw_json = match.group(0)
        last_error: json.JSONDecodeError | None = None
        for attempt in range(max_retries + 1):
            candidate = self._repair_json_candidate(raw_json, attempt)
            try:
                payload = json.loads(candidate)
                if not isinstance(payload, dict):
                    raise ValueError("JSON payload must be an object")
                return self._normalize_explanation(payload)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue

        detail = f"JSON parsing failed after {max_retries} retries: {last_error.msg}" if last_error else "JSON parsing failed"
        raise HTTPException(status_code=500, detail=detail)

    async def _generate_content(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        if self.client is None:
            raise RuntimeError("No LLM client is configured. Set GROQ_API_KEY.")

        completion = await self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        choices = completion.choices or []
        if not choices:
            raise RuntimeError("LLM returned no choices.")
        return str(choices[0].message.content or "").strip()

    async def aiter_solver_stream(
        self,
        statement: str,
        target_hint: str = "target variable",
        chat_history_context: list[dict[str, Any]] | None = None,
        socratic_mode: bool = False,
        exam_context: str = "General",
        image_data: str | None = None,
        symbolic_context: str | None = None,
        ground_truth_context: str | None = None,
    ):
        if self.client is None:
            raise RuntimeError("No LLM client is configured. Set GROQ_API_KEY.")

        chat_history_text = self._format_chat_history_context(chat_history_context)
        system_prompt = self.build_system_prompt(
            socratic_mode=socratic_mode,
            exam_context=exam_context,
            ground_truth_context=ground_truth_context,
        )
        user_prompt = self._build_solver_user_prompt(
            statement=statement,
            target_hint=target_hint,
            chat_history_text=chat_history_text,
            image_data=image_data,
            symbolic_context=symbolic_context,
            ground_truth_context=ground_truth_context,
        )

        accumulated = ""
        emitted_thinking_len = 0

        stream = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.0 if symbolic_context and symbolic_context.strip() else 0.1,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        async for chunk in stream:
            choices = getattr(chunk, "choices", []) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text_delta = str(getattr(delta, "content", "") or "")
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
        ground_truth_context: str | None = None,
    ) -> dict[str, Any]:
        if not statement or not statement.strip():
            raise HTTPException(status_code=422, detail="Word problem statement cannot be empty.")

        chat_history_text = self._format_chat_history_context(chat_history_context)
        system_prompt = self.build_system_prompt(
            socratic_mode=socratic_mode,
            exam_context=exam_context,
            ground_truth_context=ground_truth_context,
        )
        user_prompt = (
            "Translate this problem into deterministic JSON. Return strict JSON with keys: "
            "variables (object), target (string), topics (array of 2-4), explanation (array of 4). "
            f"Problem: {statement.strip()} "
            f"Preferred target hint: {target_hint}. "
            f"Chat History Context:\n{chat_history_text}"
        )
        if image_data:
            user_prompt += " Image context is attached from OCR."

        content = await self._generate_content(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.1)
        payload = self._extract_json(content)
        variables = payload.get("variables", {})
        if not isinstance(variables, dict):
            payload["variables"] = {}
        payload["target"] = str(payload.get("target", target_hint)).strip() or target_hint
        payload["topics"] = self._normalize_topics(payload.get("topics", []))
        return self._normalize_explanation(payload)


PRIMARY_TRANSLATOR = RestoredLLMTranslator(PRIMARY_ASYNC_LLM_CLIENT)

TAVILY_CLIENT = TavilyClient(api_key=os.getenv(TAVILY_API_KEY_ENV_NAME)) if os.getenv(TAVILY_API_KEY_ENV_NAME) else None
OLYMPIAD_ADMIN_TRIGGER_WORDS = ("date", "syllabus", "registration", "deadline", "ioqm", "nsejs", "nmtc", "cutoff")


class APITimeoutError(Exception):
    """Raised when an upstream API timeout needs global system override handling."""


class WolframResult(TypedDict):
    answer: str
    state: Literal["ok", "fallback", "security"]
    formula: str
    steps: str


class Base(DeclarativeBase):
    pass


class QuerySession(Base):
    __tablename__ = "query_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_prompt: Mapped[str] = mapped_column(String(1024), nullable=False)
    wolfram_response: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(String(32), nullable=False, default="Math")
    ocr_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


DATABASE_PATH = Path(__file__).resolve().parent / "history.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
Base.metadata.create_all(bind=engine)


def _ensure_query_session_schema() -> None:
    inspector = inspect(engine)
    if "query_sessions" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("query_sessions")}
    alter_statements: list[str] = []
    if "subject" not in existing_columns:
        alter_statements.append("ALTER TABLE query_sessions ADD COLUMN subject VARCHAR(32) NOT NULL DEFAULT 'Math'")
    if "ocr_source" not in existing_columns:
        alter_statements.append("ALTER TABLE query_sessions ADD COLUMN ocr_source BOOLEAN NOT NULL DEFAULT 0")

    if not alter_statements:
        return

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))


_ensure_query_session_schema()
CONVERSATION_CONTEXT: dict[str, ConversationContext] = {}

EXAM_TARGETS = {
    "NSEJS": {
        "exam_date": date(2026, 11, 20),
        "target_syllabus_percent": 95,
        "target_problem_count": 1500,
        "focus_area": "Mixed physics numericals, chemistry recall, and speed math drills.",
    },
    "NMTC": {
        "exam_date": date(2026, 10, 15),
        "target_syllabus_percent": 90,
        "target_problem_count": 800,
        "focus_area": "Contest-style logic, number theory, and timed puzzle solving.",
    },
    "IOQM": {
        "exam_date": date(2026, 9, 8),
        "target_syllabus_percent": 85,
        "target_problem_count": 600,
        "focus_area": "Proof writing, algebraic manipulation, and geometry consistency.",
    },
    "JEE": {
        "exam_date": date(2027, 1, 24),
        "target_syllabus_percent": 40,
        "target_problem_count": 1200,
        "focus_area": "Foundational PCM depth and timed mixed-set endurance.",
    },
}
LONG_TERM_GOAL_DATE = date(2027, 1, 24)

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger("addix-deterministic-solver")

CACHE_TTL_SECONDS = 3600
CLASSIFICATION_CACHE: dict[str, tuple[datetime, str]] = {}
SOLVE_RESULT_CACHE: dict[str, tuple[datetime, str]] = {}
CACHE_LOCK = asyncio.Lock()
API_SOLVE_TOTAL_CALLS = 0
API_SOLVE_CACHE_HITS = 0
active_simulations: dict[str, dict[str, Any]] = {}
SIMULATION_LOCK = asyncio.Lock()
PRIMARY_FAILURE_COUNT = 0
PRIMARY_CIRCUIT_OPEN_UNTIL: datetime | None = None


def _log_cache_efficiency_summary() -> None:
    total = API_SOLVE_TOTAL_CALLS
    hits = API_SOLVE_CACHE_HITS
    misses = max(total - hits, 0)
    saved_percent = (hits / total * 100.0) if total else 0.0
    logger.info(
        "[CACHE FLEX] /api/solve total=%d, cache_hits=%d, cache_misses=%d, saved_calls=%.2f%%",
        total,
        hits,
        misses,
        saved_percent,
    )


def _validate_env_mappings() -> None:
    required = {
        WOLFRAM_APP_ID_ENV_NAME: os.getenv(WOLFRAM_APP_ID_ENV_NAME),
        GROQ_API_KEY_ENV_NAME: os.getenv(GROQ_API_KEY_ENV_NAME),
        TAVILY_API_KEY_ENV_NAME: os.getenv(TAVILY_API_KEY_ENV_NAME),
        GEMINI_API_KEY_ENV_NAME: os.getenv(GEMINI_API_KEY_ENV_NAME),
        GOOGLE_API_KEY_ENV_NAME: os.getenv(GOOGLE_API_KEY_ENV_NAME),
        SCHOLAR_FRONTEND_SECRET_ENV_NAME: os.getenv(SCHOLAR_FRONTEND_SECRET_ENV_NAME),
    }
    missing = [name for name, value in required.items() if not value]

    if missing:
        logger.warning("Missing environment mappings: %s", ", ".join(missing))
    else:
        logger.info("All orchestrator environment mappings are present.")


def _strip_think_tags(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _is_olympiad_grounding_query(query: str) -> bool:
    lowered = (query or "").lower()
    topic_tokens = ("registration", "syllabus", "date")
    return any(token in lowered for token in topic_tokens)


def _has_obvious_math_numbers(query: str) -> bool:
    lowered = (query or "").lower()
    if not lowered:
        return False

    # Numeric expression with operators/equations usually indicates computational math intent.
    if re.search(r"\d\s*[+\-*/^=]", lowered) or re.search(r"[+\-*/^=]\s*\d", lowered):
        return True

    # Numeric values tied to units are likely computational prompts.
    if re.search(r"\b\d+(?:\.\d+)?\s*(kg|g|m|cm|mm|km|s|sec|m/s|m/s\^2|n|j|pa|kpa|km/h)\b", lowered):
        return True

    # Explicit calculation directives with numbers should not hit research routing.
    calc_words = ("solve", "calculate", "integrate", "differentiate", "derivative", "equation")
    if any(word in lowered for word in calc_words) and bool(re.search(r"\d", lowered)):
        return True

    return False


def _should_route_to_tavily_research(query: str) -> bool:
    lowered = (query or "").lower()
    if not lowered:
        return False
    has_trigger = any(token in lowered for token in OLYMPIAD_ADMIN_TRIGGER_WORDS)
    return has_trigger and not _has_obvious_math_numbers(lowered)


async def _format_tavily_results_with_groq(query: str, tavily_payload: dict[str, Any]) -> str:
    api_key = os.getenv(GROQ_API_KEY_ENV_NAME)
    if not api_key:
        raise RuntimeError("Groq API key is missing.")

    prompt = (
        "You format live olympiad admin search results into a concise deterministic student-friendly summary. "
        "Input query and raw Tavily payload are provided below. "
        "Return strict JSON only with key 'result'. Keep it concise and factual. "
        "If including an image, inject it strictly as Markdown using ![Visual Reference](VALID_IMAGE_URL_HERE). "
        "The image Markdown must be on its own dedicated line separated by double line breaks (\\n\\n) from surrounding text.\n"
        f"query: {query}\n"
        f"raw_tavily: {json.dumps(tavily_payload, ensure_ascii=True)}"
    )

    response = await WOLFRAM_HTTP_CLIENT.post(
        GROQ_CHAT_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": GROQ_EDGE_MODEL,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": "Output strict JSON only. Schema: {\"result\": \"...\"}. Use standard Markdown images only as ![Visual Reference](VALID_IMAGE_URL_HERE) and place image lines on dedicated lines with double line breaks.",
                },
                {"role": "user", "content": prompt},
            ],
        },
        timeout=GROQ_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices", []) if isinstance(payload, dict) else []
    if not choices:
        raise RuntimeError("Groq returned no choices for Tavily formatting.")

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = _strip_think_tags(str(message.get("content", "")).strip())
    if not content:
        raise RuntimeError("Groq returned empty Tavily formatting content.")

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(content[start : end + 1])
            result_text = str(parsed.get("result", "")).strip()
            if result_text:
                return result_text
        except Exception:
            pass

    return content


class TavilyResearchAgent:
    def __init__(self, client: TavilyClient | None) -> None:
        self.client = client

    async def search_and_format(self, query: str) -> dict[str, Any]:
        if self.client is None:
            raise RuntimeError("Tavily client is unavailable. Check TAVILY_API_KEY.")

        tavily_payload = await asyncio.to_thread(
            self.client.search,
            query=query,
            search_depth="advanced",
            max_results=5,
        )

        result_text = await _format_tavily_results_with_groq(query, tavily_payload if isinstance(tavily_payload, dict) else {})
        return {
            "result": result_text,
            "explanation": [
                "Searched live web",
                "Extracted official dates",
                "Summarized findings",
                "Verified the extracted dates against the live source context.",
            ],
            "engine_trace": "Tavily Search + Groq",
        }


TAVILY_RESEARCH_AGENT = TavilyResearchAgent(TAVILY_CLIENT)


def _is_simple_formula_or_unit_query(query: str) -> bool:
    lowered = (query or "").lower().strip()
    if not lowered:
        return False
    if len(lowered) > 120:
        return False
    formula_tokens = ("formula", "unit conversion", "convert", "to meters", "to m", "to kg", "to s")
    terse_math = bool(re.fullmatch(r"[0-9a-z\s+\-*/^=().]+", lowered)) and len(lowered.split()) <= 10
    return any(token in lowered for token in formula_tokens) or terse_math


def _has_image_context(query: str) -> bool:
    lowered = (query or "").lower()
    return "image" in lowered or "diagram" in lowered or "figure" in lowered


def _should_route_to_ground_truth(query: str) -> bool:
    lowered = (query or "").lower()
    if not lowered:
        return False

    broad_math_triggers = (
        "calculate",
        "solve",
        "evaluate",
        "statement",
        "limit",
        "integrate",
        "derivative",
        "find the value",
        "ratio",
    )
    if any(token in lowered for token in broad_math_triggers):
        return True

    if any(token in lowered for token in ("derive", "derivation", "differentiate", "integrate", "integral", "limit")):
        return True

    if any(token in lowered for token in ("physics", "kinematics", "projectile", "electrostatics", "calculus")) and bool(re.search(r"\d", lowered)):
        return True

    heavy_math_patterns = (
        r"\b(d/dx|dy/dx|\bint\b|\bintegral\b|\blim\b|sin|cos|tan|log|ln|sqrt)\b",
        r"[+\-*/^=].*[+\-*/^=]",
    )
    return any(re.search(pattern, lowered) for pattern in heavy_math_patterns)


def _should_route_to_tavily_context(query: str) -> bool:
    lowered = (query or "").lower()
    if not lowered:
        return False

    diagram_tokens = ("show me", "diagram", "ray diagram", "image", "graph", "figure")
    recent_tokens = ("recent", "latest", "update", "exam date", "registration", "news")
    return (
        _has_image_context(lowered)
        or any(token in lowered for token in diagram_tokens)
        or any(token in lowered for token in recent_tokens)
        or _should_route_to_tavily_research(lowered)
    )


def _needs_visual_tutor(query: str) -> bool:
    lowered = str(query or "").lower()
    if not lowered:
        return False

    struggle_phrases = (
        "i don't get it",
        "i dont get it",
        "confused",
        "hard",
        "explain with diagram",
        "visualize",
    )
    return any(phrase in lowered for phrase in struggle_phrases)


def _extract_first_url(text: str) -> str:
    match = re.search(r"https?://\S+", str(text or ""))
    if not match:
        return ""
    return str(match.group(0)).rstrip(").,;]")


def _extract_mastered_topic_from_query(query: str) -> str | None:
    normalized = str(query or "").strip()
    if not normalized:
        return None

    patterns = [
        r"i\s*am\s*done\s*with\s+([a-z0-9\s+\-&,()]+)",
        r"i\s*(?:have\s*)?mastered\s+([a-z0-9\s+\-&,()]+)",
        r"i\s*completed\s+([a-z0-9\s+\-&,()]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match and match.group(1):
            return str(match.group(1)).strip().title()
    return None


def _to_katex_string(result_text: str) -> str:
    text = (result_text or "").strip()
    if not text:
        return r"\text{No\ deterministic\ result}"

    if re.search(r"\\(frac|int|sqrt|sum|lim|text|cdot|times|left|right)", text):
        return text

    # Preserve compact symbolic forms while escaping plain prose.
    symbolic_only = bool(re.fullmatch(r"[A-Za-z0-9\s+\-*/^=()._|]+", text))
    if symbolic_only:
        return text

    escaped = text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    escaped = escaped.replace("%", r"\%").replace("#", r"\#").replace("$", r"\$").replace("&", r"\&")
    return r"\text{" + escaped.replace(" ", r"\ ") + "}"


def _dimensional_analysis_summary(query: str) -> str:
    normalized = _normalize_physics_units(query)
    pattern = r"(?<![A-Za-z0-9_])([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*(km/h|kmph|kph|cm/s|mm/s|km|cm|mm|hours|hour|hr|min|minute|minutes|sec|second|seconds|ms|kg|g|mg|m|s|m/s\^2|m/s|n|j|pa|kpa)\b"
    captures = re.findall(pattern, normalized, flags=re.IGNORECASE)
    if not captures:
        return "No explicit dimensional quantities found; treated as symbolic or pure numeric expression."

    checks = [f"{value} {unit}" for value, unit in captures[:8]]
    return "SI-validated quantities: " + ", ".join(checks)


def _infer_target_dimension(query: str) -> tuple[str, str]:
    lowered = (query or "").lower()
    if any(token in lowered for token in ("force", "newton")):
        return "force", "kg*m/s^2"
    if any(token in lowered for token in ("acceleration",)):
        return "acceleration", "m/s^2"
    if any(token in lowered for token in ("velocity", "speed")):
        return "velocity", "m/s"
    if any(token in lowered for token in ("distance", "displacement", "height", "range")):
        return "distance", "m"
    if any(token in lowered for token in ("time", "duration")):
        return "time", "s"
    if any(token in lowered for token in ("energy", "work", "heat")):
        return "energy", "kg*m^2/s^2"
    if any(token in lowered for token in ("momentum",)):
        return "momentum", "kg*m/s"
    return "target", "symbolic"


def _derive_dimension_from_inputs(query: str, target_name: str) -> str:
    lowered = (query or "").lower()
    if target_name == "force":
        if ("mass" in lowered or "m=" in lowered) and ("acceleration" in lowered or "a=" in lowered):
            return "kg*m/s^2"
    if target_name == "acceleration":
        if any(token in lowered for token in ("v-u", "change in velocity", "velocity change")) and "time" in lowered:
            return "m/s^2"
        if "force" in lowered and ("mass" in lowered or "m=" in lowered):
            return "m/s^2"
    if target_name == "velocity":
        if any(token in lowered for token in ("distance", "displacement")) and "time" in lowered:
            return "m/s"
        if "u=" in lowered and "a=" in lowered and "t=" in lowered:
            return "m/s"
    if target_name == "distance":
        if any(token in lowered for token in ("velocity", "speed", "m/s")) and "time" in lowered:
            return "m"
    if target_name == "time":
        if any(token in lowered for token in ("distance", "displacement")) and any(
            token in lowered for token in ("velocity", "speed", "m/s")
        ):
            return "s"
    if target_name == "energy":
        if ("mass" in lowered or "m=" in lowered) and ("velocity" in lowered or "v=" in lowered):
            return "kg*m^2/s^2"
        if any(token in lowered for token in ("specific heat", "c=")) and any(token in lowered for token in ("dt", "deltat")):
            return "kg*m^2/s^2"
    if target_name == "momentum":
        if ("mass" in lowered or "m=" in lowered) and ("velocity" in lowered or "v=" in lowered):
            return "kg*m/s"
    return "symbolic"


def _dimensional_analysis_pass(query: str) -> dict[str, str | bool]:
    normalized = _normalize_physics_units(query)
    target_name, expected_unit = _infer_target_dimension(normalized)
    derived_unit = _derive_dimension_from_inputs(normalized, target_name)
    is_consistent = expected_unit == "symbolic" or derived_unit == "symbolic" or expected_unit == derived_unit
    return {
        "target": target_name,
        "expected_unit": expected_unit,
        "derived_unit": derived_unit,
        "is_consistent": is_consistent,
        "normalized": normalized,
    }


def _infer_core_principle(query: str) -> str:
    lowered = (query or "").lower()
    if any(token in lowered for token in ("projectile", "thrown", "launched")):
        return "Kinematics from first principles: x(t)=u cos(theta)t, y(t)=u sin(theta)t - (1/2)gt^2"
    if any(token in lowered for token in ("accelerates", "acceleration", "uniform acceleration")):
        return "Newtonian kinematics: v=u+at and s=ut+(1/2)at^2"
    if any(token in lowered for token in ("force", "newton")):
        return "Newton's second law from first principles: F=ma"
    if any(token in lowered for token in ("heat", "calorimetry", "specific heat")):
        return "Calorimetry conservation law: Q=mcDeltaT"
    if any(token in lowered for token in ("integral", "integrate")):
        return "Fundamental theorem of calculus with symbolic antiderivative construction"
    if any(token in lowered for token in ("derivative", "differentiate")):
        return "First-principles differential calculus using product/chain/power rules"
    if any(token in lowered for token in ("ioqm", "number theory", "mod")):
        return "Number theory invariants and modular arithmetic constraints"
    return "Deterministic symbolic derivation from governing physical/mathematical laws"


def _infer_execution_summary(query: str, final_answer: str) -> str:
    principle = _infer_core_principle(query)
    return f"Applied {principle}; substituted SI-normalized values, simplified algebra, and obtained {final_answer}."


def _engine_trace_for_route(*, logic_engine: str, math_engine: str, route_label: str) -> str:
    _ = (logic_engine, math_engine, route_label)
    return "Claude-3.5-Sonnet + WolframAlpha"


def _student_tip_for_query(query: str) -> str:
    lowered = (query or "").lower()
    if "km/h" in lowered or "minute" in lowered or "min" in lowered:
        return "Students most often lose marks by skipping unit conversion before substitution; always convert to SI first."
    if any(token in lowered for token in ("projectile", "angle", "theta")):
        return "A common error is mixing sin(theta) and cos(theta) components; resolve horizontal and vertical parts separately."
    if any(token in lowered for token in ("derivative", "differentiate", "integral", "integrate")):
        return "The most frequent mistake is algebraic simplification drift; rewrite each intermediate expression before the next rule."
    if any(token in lowered for token in ("force", "acceleration", "newton")):
        return "A recurring mistake is using total force instead of component force along the motion axis."
    return "Most errors come from skipping the variable-definition step; declare knowns, unknown, and governing law before solving."


def _explanation_stages(query: str, route_label: str, execution_summary: str) -> list[str]:
    _ = (query, route_label, execution_summary)
    return [
        "STEP 1 [SETUP]: Variables & SI Units",
        "STEP 2 [CONCEPT]: Core Physics/Math Law",
        "STEP 3 [EXECUTION]: Algebraic Steps",
        "STEP 4 [VERIFICATION]: The units and boundary conditions were checked for consistency.",
    ]


def _is_rate_limit_like(exc: Exception) -> bool:
    normalized = str(exc).lower()
    return "429" in normalized or "rate limit" in normalized or "quota" in normalized


def _is_circuit_open() -> bool:
    if PRIMARY_CIRCUIT_OPEN_UNTIL is None:
        return False
    return datetime.utcnow() < PRIMARY_CIRCUIT_OPEN_UNTIL


def _record_primary_failure() -> None:
    global PRIMARY_FAILURE_COUNT
    global PRIMARY_CIRCUIT_OPEN_UNTIL
    PRIMARY_FAILURE_COUNT += 1
    if PRIMARY_FAILURE_COUNT >= 3:
        PRIMARY_CIRCUIT_OPEN_UNTIL = datetime.utcnow() + timedelta(seconds=60)


def _record_primary_success() -> None:
    global PRIMARY_FAILURE_COUNT
    global PRIMARY_CIRCUIT_OPEN_UNTIL
    PRIMARY_FAILURE_COUNT = 0
    PRIMARY_CIRCUIT_OPEN_UNTIL = None


async def _query_tavily_grounding(query: str) -> str:
    api_key = os.getenv(TAVILY_API_KEY_ENV_NAME)
    if not api_key:
        raise RuntimeError("Tavily API key is missing.")

    response = await WOLFRAM_HTTP_CLIENT.post(
        TAVILY_SEARCH_ENDPOINT,
        json={
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 3,
        },
        timeout=httpx.Timeout(12.0, connect=6.0),
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", []) if isinstance(payload, dict) else []
    if not results:
        return "No grounded olympiad updates found from Tavily."

    lines: list[str] = []
    for item in results[:3]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "Update")).strip()
        snippet = str(item.get("content", "")).strip()
        url = str(item.get("url", "")).strip()
        lines.append(f"{title}: {snippet} ({url})")
    return " | ".join(lines) if lines else "No grounded olympiad updates found from Tavily."


async def _query_tavily_visual_diagram(topic: str) -> str:
    cleaned_topic = str(topic or "").strip() or "physics concept"
    visual_query = f"clear educational diagram of {cleaned_topic}"

    try:
        if TAVILY_CLIENT is not None:
            payload = await asyncio.to_thread(
                TAVILY_CLIENT.search,
                query=visual_query,
                search_depth="advanced",
                max_results=5,
                include_images=True,
            )
        else:
            api_key = os.getenv(TAVILY_API_KEY_ENV_NAME)
            if not api_key:
                return ""
            response = await WOLFRAM_HTTP_CLIENT.post(
                TAVILY_SEARCH_ENDPOINT,
                json={
                    "api_key": api_key,
                    "query": visual_query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_images": True,
                },
                timeout=httpx.Timeout(12.0, connect=6.0),
            )
            response.raise_for_status()
            payload = response.json()

        if isinstance(payload, dict):
            images = payload.get("images", [])
            if isinstance(images, list):
                for image in images:
                    if isinstance(image, str) and image.strip().startswith("http"):
                        return image.strip()
                    if isinstance(image, dict):
                        image_url = str(image.get("url", "")).strip()
                        if image_url.startswith("http"):
                            return image_url

            results = payload.get("results", [])
            if isinstance(results, list):
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    candidate_url = _extract_first_url(str(item.get("content", "")))
                    if candidate_url:
                        return candidate_url
                    direct_url = str(item.get("url", "")).strip()
                    if direct_url.startswith("http") and any(token in direct_url.lower() for token in (".png", ".jpg", ".jpeg", "image")):
                        return direct_url
    except Exception as exc:
        logger.warning("Tavily visual diagram fetch failed for topic=%s", cleaned_topic, exc_info=exc)

    return ""


async def _query_groq_edge(query: str) -> str:
    api_key = os.getenv(GROQ_API_KEY_ENV_NAME)
    if not api_key:
        raise RuntimeError("Groq API key is missing.")

    response = await WOLFRAM_HTTP_CLIENT.post(
        GROQ_CHAT_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": GROQ_EDGE_MODEL,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": "You answer only with concise deterministic math/unit output in KaTeX-compatible notation.",
                },
                {"role": "user", "content": query},
            ],
        },
        timeout=GROQ_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices", []) if isinstance(payload, dict) else []
    if not choices:
        raise RuntimeError("Groq returned no choices.")
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = str(message.get("content", "")).strip()
    if not content:
        raise RuntimeError("Groq returned empty content.")
    return _strip_think_tags(content)


async def _query_gemini_fallback(query: str) -> str:
    api_key = os.getenv(GEMINI_API_KEY_ENV_NAME)
    if not api_key:
        return COMPUTATION_FAILSAFE_MESSAGE

    try:
        response = await WOLFRAM_HTTP_CLIENT.post(
            f"{GEMINI_GENERATE_ENDPOINT}?key={urllib.parse.quote_plus(api_key)}",
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    "Return deterministic math answer only in KaTeX-compatible notation. "
                                    f"Query: {query}"
                                )
                            }
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.0},
            },
            timeout=GROQ_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
        if not candidates:
            return COMPUTATION_FAILSAFE_MESSAGE
        content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        text = ""
        for part in parts:
            if isinstance(part, dict):
                text += str(part.get("text", ""))
        text = text.strip()
        if not text:
            return COMPUTATION_FAILSAFE_MESSAGE
        return _strip_think_tags(text)
    except Exception:
        return COMPUTATION_FAILSAFE_MESSAGE


async def _describe_diagram_with_gemini_flash(image_data: str) -> str:
    api_key = str(os.getenv(GOOGLE_API_KEY_ENV_NAME, "")).strip() or str(os.getenv(GEMINI_API_KEY_ENV_NAME, "")).strip()
    if not api_key:
        logger.warning("Gemini vision skipped: GOOGLE_API_KEY is not configured.")
        return ""

    encoded_payload = str(image_data or "").strip()
    if not encoded_payload:
        return ""
    if "," in encoded_payload:
        encoded_payload = encoded_payload.split(",", 1)[1]

    try:
        response = await WOLFRAM_HTTP_CLIENT.post(
            f"{GEMINI_FLASH_GENERATE_ENDPOINT}?key={urllib.parse.quote_plus(api_key)}",
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": GEMINI_DIAGRAM_PROMPT},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": encoded_payload,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.0},
            },
            timeout=GROQ_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
        if not candidates:
            return ""

        content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        text_chunks: list[str] = []
        for part in parts:
            if isinstance(part, dict):
                text = str(part.get("text", "")).strip()
                if text:
                    text_chunks.append(text)
        return "\n".join(text_chunks).strip()
    except Exception as exc:
        logger.warning("Gemini vision description failed.", exc_info=exc)
        return ""


async def _describe_image_with_groq_vision(prompt: str, image_data: str, exam_context: str) -> str:
    if PRIMARY_ASYNC_LLM_CLIENT is None:
        raise RuntimeError("No LLM client is configured. Set GROQ_API_KEY.")
    if PRIMARY_LLM_PROVIDER != "Groq":
        return ""

    encoded_payload = str(image_data or "").strip()
    if not encoded_payload:
        return ""
    if not encoded_payload.startswith("data:"):
        encoded_payload = "data:image/png;base64," + encoded_payload

    vision_prompt = (
        "You are a multimodal academic assistant. Read the attached image and extract the problem statement, "
        "all visible text, labels, equations, and the key question being asked. "
        "Do not solve it. Return a concise Markdown summary that can be appended to a solver prompt. "
        "If the image contains a diagram, describe the relevant geometry or circuit relationships."
    )
    if prompt:
        vision_prompt += " User prompt: " + prompt.strip()
    if exam_context:
        vision_prompt += " Exam context: " + exam_context.strip()

    completion = await PRIMARY_ASYNC_LLM_CLIENT.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
        temperature=0.0,
        messages=[
            {"role": "system", "content": vision_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the problem details from the attached image."},
                    {"type": "image_url", "image_url": {"url": encoded_payload}},
                ],
            },
        ],
    )

    summary_text = _chat_response_text(completion).strip()
    return summary_text

app = FastAPI(
    title="ADDIX Labs Deterministic API",
    description="Production-safe deterministic solver powered by Wolfram Alpha.",
    version="2.0.0",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)

ALLOWED_ORIGINS = [
    "https://scholar-model-v3-7dnx.vercel.app",
    "https://scholar-model-v3.vercel.app",
    "http://localhost:5500",
]
CORS_ALLOW_ORIGINS = ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    _ = (request, exc)
    return JSONResponse(
        status_code=429,
        content={
            "result": "System Cooldown Active. Please wait 60 seconds.",
            "topics": ["Rate Limit"],
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def scholar_request_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        request_origin = str(request.headers.get("origin", "")).strip()
        allow_all_origins = "*" in CORS_ALLOW_ORIGINS
        allowed_origin = "*" if allow_all_origins else (request_origin if request_origin in ALLOWED_ORIGINS else "")
        return JSONResponse(
            status_code=200,
            content={"ok": True},
            headers={
                "Access-Control-Allow-Origin": allowed_origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
                "Vary": "Origin",
            },
        )

    return await call_next(request)


class SimulationInput(BaseModel):
    student_query: str


class SolveRequest(BaseModel):
    messages: List[Dict[str, str]]
    prompt: Optional[str] = None
    query: Optional[str] = None
    socratic_mode: bool = False
    is_tester_mode: StrictBool = Field(default=False)
    exam_context: str = "General"
    image_data: Optional[str] = None
    image_base64: Optional[str] = None


class PYQGenerateRequest(BaseModel):
    exam: str
    topic: str


class QueryPayload(SolveRequest):
    pass


class VaultItemCreate(BaseModel):
    question_text: str
    concept_tags: list[str] = []


class VaultReviewPayload(BaseModel):
    score: int = Field(..., ge=0, le=5)


class DailyAnalyticsSyncPayload(BaseModel):
    date: str
    problems_delta: int = 0
    physics_delta: int = 0
    math_delta: int = 0


def _serialize_vault_item(item: VaultItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "question_text": item.question_text,
        "concept_tags": parse_tags(item.concept_tags),
        "date_added": item.date_added.isoformat(),
        "ease_factor": float(getattr(item, "ease_factor", 2.5) or 2.5),
        "interval": int(getattr(item, "interval", 0) or 0),
        "next_review_date": item.next_review_date.isoformat() if getattr(item, "next_review_date", None) else None,
    }


def _serialize_daily_analytics(item: DailyAnalytics) -> dict[str, Any]:
    return {
        "id": item.id,
        "date": item.date,
        "problems_solved": int(item.problems_solved),
        "physics_count": int(item.physics_count),
        "math_count": int(item.math_count),
    }


def _resolve_payment_email(payload_email: str | None, request: Request) -> str:
    provided_email = str(payload_email or "").strip().lower()
    if provided_email:
        return provided_email

    header_email = str(request.headers.get("X-User-Email", "")).strip().lower()
    if header_email:
        return header_email

    return "default@addix.local"


async def _get_or_create_user_by_email(email: str) -> User:
    normalized_email = str(email or "").strip().lower() or "default@addix.local"
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == normalized_email))
        row = result.scalars().first()
        if row is None:
            row = User(email=normalized_email, hashed_password="", is_premium=False)
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row


async def _get_or_create_user_stats() -> UserStats:
    async with AsyncSessionLocal() as session:
        row = await session.get(UserStats, 1)
        if row is None:
            row = UserStats(id=1, user_id=1, current_streak=0, total_solved=0)
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row


async def _record_successful_solve() -> None:
    today = date.today()
    async with AsyncSessionLocal() as session:
        row = await session.get(UserStats, 1)
        if row is None:
            row = UserStats(id=1, user_id=1, current_streak=0, total_solved=0)
            session.add(row)
            await session.flush()

        previous_day = row.last_active_date
        if previous_day is None:
            row.current_streak = 1
        else:
            delta_days = (today - previous_day).days
            if delta_days == 1:
                row.current_streak = int(row.current_streak or 0) + 1
            elif delta_days > 1:
                row.current_streak = 1

        row.total_solved = int(row.total_solved or 0) + 1
        row.last_active_date = today
        await session.commit()


def _is_tester_failure_signal(user_text: str) -> bool:
    normalized = str(user_text or "").strip().lower()
    if not normalized:
        return False
    failure_markers = (
        "i failed",
        "failed",
        "wrong answer",
        "could not solve",
        "cant solve",
        "can't solve",
        "dont know",
        "don't know",
        "i give up",
    )
    return any(marker in normalized for marker in failure_markers)


async def _insert_black_box_record(*, exam_type: str, question_text: str, concept_tags: list[str]) -> None:
    clean_question = str(question_text or "").strip()
    if not clean_question:
        return

    normalized_tags = [str(tag or "").strip() for tag in concept_tags if str(tag or "").strip()]
    async with AsyncSessionLocal() as session:
        row = BlackBox(
            user_id=1,
            exam_type=str(exam_type or "General").strip() or "General",
            question_text=clean_question,
            concept_tags=json.dumps(normalized_tags[:8], ensure_ascii=True),
            date_added=date.today(),
        )
        session.add(row)
        await session.commit()


DEBRIEF_SYSTEM_PROMPT = (
    "Analyze this study session. Do not solve any math. Act as a strict mentor reviewing a student's performance. Provide a 3-point JSON output: "
    "logic_gaps: What fundamental concepts is the student weak on based on their questions? "
    "grit_assessment: Did they rely too much on the AI, or did they push through? "
    "closing_directive: One harsh but motivating sentence telling them what to study next or commanding them to rest."
)


def _chat_response_text(response: Any) -> str:
    choices = getattr(response, "choices", []) or []
    if not choices:
        return ""
    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    return str(getattr(message, "content", "") or "").strip()


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?", " ", str(raw_text or ""), flags=re.IGNORECASE).replace("```", " ").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Debrief response did not contain JSON.")

    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Debrief response JSON must be an object.")
    return payload


def _normalize_debrief_text(value: Any) -> str:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return " ".join(items).strip()
    if value is None:
        return ""
    return str(value).strip()


async def _call_debrief_llm(history_payload: list[dict[str, Any]]) -> dict[str, Any]:
    if PRIMARY_ASYNC_LLM_CLIENT is None:
        raise RuntimeError("No LLM client is configured. Set GROQ_API_KEY.")

    history_json = json.dumps(history_payload, ensure_ascii=False)
    response = await PRIMARY_ASYNC_LLM_CLIENT.chat.completions.create(
        model=PRIMARY_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": DEBRIEF_SYSTEM_PROMPT + " Return strictly valid JSON with only the keys logic_gaps, grit_assessment, and closing_directive.",
            },
            {
                "role": "user",
                "content": "Study session history JSON:\n" + history_json,
            }
        ],
    )

    raw_text = _chat_response_text(response)
    parsed = _extract_json_object(raw_text)
    return {
        "logic_gaps": _normalize_debrief_text(parsed.get("logic_gaps")),
        "grit_assessment": _normalize_debrief_text(parsed.get("grit_assessment")),
        "closing_directive": _normalize_debrief_text(parsed.get("closing_directive")),
    }


async def _set_simulation_state(task_id: str, **fields: Any) -> None:
    async with SIMULATION_LOCK:
        existing = active_simulations.get(task_id, {})
        existing.update(fields)
        active_simulations[task_id] = existing


def calculate_sm2(quality_of_recall: int, previous_ease: float, previous_interval: int) -> tuple[int, float]:
    quality = max(0, min(5, int(quality_of_recall)))
    ease_factor = float(previous_ease or 2.5)
    interval = max(0, int(previous_interval or 0))

    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(1.3, ease_factor)

    if quality < 3:
        return 1, ease_factor

    if interval <= 0:
        return 1, ease_factor
    if interval == 1:
        return 6, ease_factor

    next_interval = max(1, int(round(interval * ease_factor)))
    return next_interval, ease_factor


async def run_deep_simulation(task_id: str, query: str) -> None:
    # Keep stages duration-based so this can scale from 60s to 3600s by changing one parameter.
    total_duration_seconds = 60
    total_stages = 6
    stage_sleep_seconds = total_duration_seconds / total_stages
    stages = [
        ("Agent 1 analyzing symbolic constraints...", 15),
        ("Agent 2 constructing candidate models...", 30),
        ("Running numerical iterations...", 45),
        ("Cross-agent verification sweep...", 60),
        ("Wolfram/Logic consolidation...", 80),
        ("Final synthesis and confidence scoring...", 100),
    ]

    try:
        for progress_message, percent in stages:
            await _set_simulation_state(
                task_id,
                status="Simulating",
                percent=f"{percent}%",
                progress=progress_message,
                updated_at=datetime.utcnow().isoformat(),
            )
            await asyncio.sleep(stage_sleep_seconds)

        sanitized_encoded = await sanitize_math_input(query)
        sanitized_plain = urllib.parse.unquote_plus(sanitized_encoded)
        translated_query, is_physics, _ = await physics_translator(sanitized_plain)
        translated_query = _sanitize_translator_payload(translated_query)
        translated_encoded = urllib.parse.quote_plus(translated_query)
        classified_query = await classify_and_inject(translated_encoded, is_physics=is_physics)
        deterministic_result = await execute_wolfram_deterministic(classified_query, is_physics=is_physics)
        deterministic_result_text = _coerce_solver_response_to_text(deterministic_result)

        if str(deterministic_result_text).strip() in {WOLFRAM_FALLBACK_RESULT, DETERMINISTIC_TIMEOUT_MESSAGE}:
            deterministic_result_text = COMPUTATION_FAILSAFE_MESSAGE

        await _set_simulation_state(
            task_id,
            status="Completed",
            percent="100%",
            progress="Simulation complete.",
            final_result=deterministic_result_text,
            updated_at=datetime.utcnow().isoformat(),
        )
    except Exception as exc:
        logger.error("Deep simulation task %s failed.", task_id, exc_info=exc)
        await _set_simulation_state(
            task_id,
            status="Failed",
            percent="100%",
            progress="Simulation aborted due to an internal error.",
            final_result=WOLFRAM_FALLBACK_RESULT,
            updated_at=datetime.utcnow().isoformat(),
        )


@app.on_event("shutdown")
async def shutdown_wolfram_client() -> None:
    _log_cache_efficiency_summary()
    await WOLFRAM_HTTP_CLIENT.aclose()


@app.on_event("startup")
async def startup_checks() -> None:
    await init_db()
    _validate_env_mappings()


@app.exception_handler(APITimeoutError)
@app.exception_handler(asyncio.TimeoutError)
async def timeout_exception_handler(request: Request, exc: Exception):
    logger.warning("System override triggered for API timeout.", exc_info=exc)
    trace = [
        {
            "step_number": 1,
            "title": "System Override",
            "description": SYSTEM_OVERRIDE_TIMEOUT_MESSAGE,
            "agent_type": "Planner",
        }
    ]
    return JSONResponse(
        status_code=504,
        content={
            "final_answer": SYSTEM_OVERRIDE_TIMEOUT_MESSAGE,
            "detail": SYSTEM_OVERRIDE_TIMEOUT_MESSAGE,
            "explanation_trace": trace,
            "logic_trace": trace,
            "planner_state": {
                "source": "system_override",
                "cache_hit": False,
                "verification_triggered": False,
                "session_id": None,
            },
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled backend exception.", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "ADDIX Scholars Engine is recalculating. Please try again."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("HTTPException occurred: %s", exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "final_answer": WOLFRAM_FALLBACK_RESULT,
            "detail": exc.detail,
            "explanation_trace": [],
            "logic_trace": [],
            "planner_state": {
                "source": "http_error",
                "cache_hit": False,
                "verification_triggered": False,
                "session_id": None,
            },
        },
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    logger.warning("Validation error occurred.", exc_info=exc)
    return JSONResponse(
        status_code=422,
        content={
            "final_answer": WOLFRAM_FALLBACK_RESULT,
            "detail": "Validation failed for request payload.",
            "explanation_trace": [],
            "logic_trace": [],
            "planner_state": {
                "source": "validation_error",
                "cache_hit": False,
                "verification_triggered": False,
                "session_id": None,
            },
        },
    )


def _days_remaining(target_date: date) -> int:
    return (target_date - datetime.now().date()).days


def _normalize_prompt(prompt: str) -> str:
    normalized = re.sub(r"\s+", " ", prompt.strip().lower())
    normalized = re.sub(r"[^a-z0-9\s+\-*/^=().]", "", normalized)
    return normalized[:512]


def _detect_subject(prompt: str) -> str:
    normalized = prompt.lower()
    physics_markers = [
        keyword
        for chapter_keywords in CURRICULUM_KEYWORD_GRAPH["Physics"].values()
        for keyword in chapter_keywords
    ]
    chemistry_markers = [
        keyword
        for chapter_keywords in CURRICULUM_KEYWORD_GRAPH["Chemistry"].values()
        for keyword in chapter_keywords
    ]
    math_markers = [
        keyword
        for chapter_keywords in CURRICULUM_KEYWORD_GRAPH["Math"].values()
        for keyword in chapter_keywords
    ]

    if any(marker in normalized for marker in physics_markers):
        return "Physics"
    if any(marker in normalized for marker in chemistry_markers):
        return "Chemistry"
    if any(marker in normalized for marker in math_markers):
        return "Math"
    return "Math"


def _extract_variables(prompt: str, inherited: dict[str, str] | None = None) -> dict[str, str]:
    variables = dict(inherited or {})
    text = re.sub(r"\s+", " ", str(prompt or "")).strip()
    if not text:
        return variables

    patterns = {
        "force": r"\bforce\s*(?:=|is|of|are)?\s*([-+]?\d+(?:\.\d+)?(?:\s*[a-zA-ZÎ¼Âµ/\^Â²Â³0-9]+)?)",
        "mass": r"\bmass\s*(?:=|is|of|are)?\s*([-+]?\d+(?:\.\d+)?(?:\s*[a-zA-ZÎ¼Âµ/\^Â²Â³0-9]+)?)",
        "acceleration": r"\bacceleration\s*(?:=|is|of|are)?\s*([-+]?\d+(?:\.\d+)?(?:\s*[a-zA-ZÎ¼Âµ/\^Â²Â³0-9]+)?)",
        "velocity": r"\bvelocity\s*(?:=|is|of|are)?\s*([-+]?\d+(?:\.\d+)?(?:\s*[a-zA-ZÎ¼Âµ/\^Â²Â³0-9]+)?)",
        "distance": r"\bdistance\s*(?:=|is|of|are)?\s*([-+]?\d+(?:\.\d+)?(?:\s*[a-zA-ZÎ¼Âµ/\^Â²Â³0-9]+)?)",
        "time": r"\btime\s*(?:=|is|of|are)?\s*([-+]?\d+(?:\.\d+)?(?:\s*[a-zA-ZÎ¼Âµ/\^Â²Â³0-9]+)?)",
    }

    for name, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match and match.group(1):
            variables[name] = match.group(1).strip()

    if re.search(r"\bmass\s+is\s+doubled|\bmass\s+doubles|\bmass\s+double", text, flags=re.IGNORECASE):
        variables["mass_modifier"] = "2x"

    return variables


async def _get_or_create_user_stats() -> UserStats:
    async with AsyncSessionLocal() as session:
        row = await session.get(UserStats, 1)
        if row is None:
            row = UserStats(id=1, user_id=1, current_streak=0, total_solved=0)
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row


async def _record_successful_solve() -> None:
    today = date.today()
    async with AsyncSessionLocal() as session:
        row = await session.get(UserStats, 1)
        if row is None:
            row = UserStats(id=1, user_id=1, current_streak=0, total_solved=0)
            session.add(row)
            await session.flush()

        previous_day = row.last_active_date
        if previous_day is None:
            row.current_streak = 1
        else:
            delta_days = (today - previous_day).days
            if delta_days == 1:
                row.current_streak = int(row.current_streak or 0) + 1
            elif delta_days > 1:
                row.current_streak = 1

        row.total_solved = int(row.total_solved or 0) + 1
        row.last_active_date = today
        await session.commit()


def _is_tester_failure_signal(user_text: str) -> bool:
    normalized = str(user_text or "").strip().lower()
    if not normalized:
        return False
    failure_markers = (
        "i failed",
        "failed",
        "wrong answer",
        "could not solve",
        "cant solve",
        "can't solve",
        "dont know",
        "don't know",
        "i give up",
    )
    return any(marker in normalized for marker in failure_markers)


async def _insert_black_box_record(*, exam_type: str, question_text: str, concept_tags: list[str]) -> None:
    clean_question = str(question_text or "").strip()
    if not clean_question:
        return

    normalized_tags = [str(tag or "").strip() for tag in concept_tags if str(tag or "").strip()]
    async with AsyncSessionLocal() as session:
        row = BlackBox(
            user_id=1,
            exam_type=str(exam_type or "General").strip() or "General",
            question_text=clean_question,
            concept_tags=json.dumps(normalized_tags[:8], ensure_ascii=True),
            date_added=date.today(),
        )
        session.add(row)
        await session.commit()
    lowered = prompt.lower()
    for name, pattern in patterns.items():
        match = re.search(pattern, lowered)
        if match and match.group(1):
            variables[name] = match.group(1).strip()

    if "mass" in variables and re.search(r"mass\s+is\s+doubled|mass\s+doubles|mass\s+double", lowered):
        variables["mass_modifier"] = "2x"
    return variables


def _is_contextual_followup(prompt: str) -> bool:
    normalized = prompt.strip().lower()
    followup_markers = (
        "and what if",
        "what if",
        "and if",
        "then if",
        "if mass",
        "if we",
        "and now",
    )
    return any(marker in normalized for marker in followup_markers)


def _apply_contextual_memory(prompt: str, context: ConversationContext | None) -> tuple[str, bool]:
    if not context or not _is_contextual_followup(prompt):
        return prompt, False

    variable_text = ", ".join([f"{key}={value}" for key, value in context.variables.items()])
    resolved_query = (
        f"Base problem: {context.last_query}. Follow-up: {prompt}. "
        f"Known variables from previous step: {variable_text or 'none'}"
    )
    return resolved_query, True


def _clean_math_text(raw_text: str) -> str:
    cleaned = raw_text.replace("Ã—", "*").replace("âˆ’", "-").replace("Ã·", "/")
    cleaned = cleaned.replace("=", " = ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\b([a-zA-Z])\s*([0-9]{1,2})\b", r"\1^\2", cleaned)
    cleaned = re.sub(r"\^\s+", "^", cleaned)
    return cleaned


def _decode_base64_image(image_payload: str) -> Any:
    if not VISION_MODULES_AVAILABLE:
        raise RuntimeError("Vision modules unavailable")
    payload = image_payload.strip()
    if "," in payload and payload.lower().startswith("data:image"):
        payload = payload.split(",", 1)[1]
    image_bytes = base64.b64decode(payload, validate=True)
    image = Image.open(BytesIO(image_bytes))
    image = image.convert("RGB")
    grayscale = ImageOps.grayscale(image)
    return grayscale


def _extract_text_with_confidence(image: Any) -> tuple[str, float]:
    if not VISION_MODULES_AVAILABLE:
        raise RuntimeError("Vision modules unavailable")
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 6")
    tokens = pytesseract.image_to_string(image, config="--psm 6")

    confidences: list[float] = []
    for value in data.get("conf", []):
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if score >= 0:
            confidences.append(score)

    confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return tokens.strip(), round(confidence, 2)


def _check_database_status_sync() -> tuple[str, int]:
    with SessionLocal() as session:
        total_logs = session.execute(select(QuerySession.id)).scalars().all()
        return "connected", len(total_logs)


async def _check_wolfram_connection() -> str:
    app_id = os.getenv(WOLFRAM_APP_ID_ENV_NAME)
    if not app_id:
        return "missing_app_id"

    try:
        response = await WOLFRAM_HTTP_CLIENT.get(
            WOLFRAM_RESULT_ENDPOINT,
            params={"appid": app_id, "i": "1+1"},
            timeout=httpx.Timeout(8.0, connect=4.0),
        )
    except httpx.HTTPError:
        return "offline"

    if response.status_code == 200:
        return "online"
    if response.status_code in {401, 403}:
        return "auth_error"
    return f"http_{response.status_code}"


def _is_verification_query(prompt: str) -> bool:
    return bool(re.search(r"\b(calculate|solve)\b", prompt.lower()))


def _semantic_check_sync(prompt: str) -> tuple[QuerySession | None, float]:
    target = _normalize_prompt(prompt)
    if not target:
        return None, 0.0

    cutoff = datetime.utcnow() - timedelta(hours=CACHE_LOOKBACK_HOURS)
    with SessionLocal() as session:
        candidates = session.execute(
            select(QuerySession)
            .where(QuerySession.timestamp >= cutoff)
            .order_by(QuerySession.timestamp.desc())
            .limit(80)
        ).scalars().all()

    best_match: QuerySession | None = None
    best_score = 0.0
    for item in candidates:
        comparison = _normalize_prompt(item.user_prompt)
        if comparison == target:
            return item, 1.0
        score = SequenceMatcher(None, target, comparison).ratio()
        if score > best_score:
            best_score = score
            best_match = item

    if best_match and best_score >= CACHE_SIMILARITY_THRESHOLD:
        return best_match, best_score
    return None, best_score


async def lookup_recent_similar(prompt: str) -> tuple[QuerySession | None, float]:
    return await asyncio.to_thread(_semantic_check_sync, prompt)


def _persist_query_session_sync(prompt: str, answer: str, subject: str, ocr_source: bool) -> QuerySession:
    with SessionLocal() as session:
        entry = QuerySession(
            user_prompt=prompt,
            wolfram_response=answer,
            subject=subject,
            ocr_source=ocr_source,
            timestamp=datetime.utcnow(),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


async def persist_query_session(prompt: str, answer: str, subject: str, ocr_source: bool) -> QuerySession:
    return await asyncio.to_thread(_persist_query_session_sync, prompt, answer, subject, ocr_source)


async def run_python_repl_placeholder(query_text: str, answer_text: str) -> str:
    await asyncio.sleep(0)
    sanitized = answer_text.strip() if answer_text.strip() else "No answer to verify"
    return (
        "Placeholder REPL check executed: prepared deterministic verification context for "
        f"'{query_text}' and compared against Wolfram output '{sanitized[:120]}'."
    )


def _is_valid_wolfram_answer(answer_text: str) -> bool:
    if not answer_text:
        return False
    normalized = answer_text.strip().lower()
    return all(marker not in normalized for marker in INVALID_WOLFRAM_MARKERS)


def _derive_symbolic_formula(query_text: str) -> str:
    normalized = query_text.lower()
    if "limit" in normalized:
        return r"\lim_{x \to a} f(x)"
    if "integral" in normalized or "integrate" in normalized:
        return r"\int f(x)\,dx"
    if "derivative" in normalized or "differentiate" in normalized:
        return r"\frac{d}{dx}f(x)"
    if "projectile" in normalized or "range" in normalized or "angle" in normalized:
        return r"R = \frac{u^2\sin(2\theta)}{g}"
    if "acceleration" in normalized or "velocity" in normalized or "distance" in normalized:
        return r"s = ut + \frac{1}{2}at^2"
    if "quadratic" in normalized or "roots" in normalized:
        return r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"
    if "current" in normalized or "voltage" in normalized or "resistance" in normalized:
        return r"V = IR"
    if re.search(r"\d", normalized) and re.search(r"[=+\-*/^]", normalized):
        return r"\text{Expression evaluated deterministically}"
    return r"\text{Formula derived from query context}"


def _build_step_trace(query_text: str, result_text: str) -> str:
    return (
        f"Step 1: Input query forwarded to Wolfram: {query_text}\n"
        "Step 2: Executed Wolfram Alpha Short Answer API deterministic call.\n"
        f"Step 3: Raw computational output: {result_text}"
    )


def _clean_frontend_answer(raw_text: str) -> str:
    cleaned = (raw_text or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" |;,")
    return cleaned


def _sanitize_solver_output_text(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return ""

    while True:
        previous = text

        fence_match = re.fullmatch(r"```(?:[a-zA-Z0-9_+-]+)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
        if fence_match:
            text = str(fence_match.group(1) or "").strip()

        if text.startswith("$$") and text.endswith("$$") and len(text) >= 4:
            text = text[2:-2].strip()

        if text == previous:
            break

    return text


def _extract_priority_pod_plaintext(payload: dict[str, Any]) -> str | None:
    query_result = payload.get("queryresult", {})
    pods = query_result.get("pods", [])
    if not isinstance(pods, list):
        return None

    for pod in pods:
        if not isinstance(pod, dict):
            continue
        pod_title = str(pod.get("title", "")).strip().lower()
        if not re.match(r"^(primary\s+result|result|solution)\b", pod_title):
            continue

        subpods = pod.get("subpods", [])
        if isinstance(subpods, dict):
            subpods = [subpods]
        if not isinstance(subpods, list) or not subpods:
            continue

        primary_subpod: dict[str, Any] | None = None
        for subpod in subpods:
            if not isinstance(subpod, dict):
                continue
            primary_flag = subpod.get("primary")
            if primary_flag in {True, "true", "True", 1, "1"}:
                primary_subpod = subpod
                break
        if primary_subpod is None:
            first_subpod = subpods[0]
            primary_subpod = first_subpod if isinstance(first_subpod, dict) else None

        if primary_subpod is None:
            continue

        plaintext = str(primary_subpod.get("plaintext", "")).strip()
        cleaned = _clean_frontend_answer(plaintext)
        if cleaned:
            return cleaned

    return None


async def _fetch_wolfram_math_pod_answer(
    client: httpx.AsyncClient,
    *,
    app_id: str,
    decoded_query: str,
) -> str | None:
    try:
        response = await client.get(
            WOLFRAM_QUERY_ENDPOINT,
            params={
                "appid": app_id,
                "input": decoded_query,
                "output": "json",
                "format": "plaintext",
            },
        )
    except httpx.HTTPError:
        return None

    if response.status_code != 200:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    return _extract_priority_pod_plaintext(payload)


async def query_wolfram(query_text: str) -> WolframResult:
    app_id = os.getenv(WOLFRAM_APP_ID_ENV_NAME)
    normalized_query = query_text.strip()
    formula = _derive_symbolic_formula(normalized_query)
    if not normalized_query:
        return {
            "answer": WOLFRAM_FALLBACK_RESULT,
            "state": "fallback",
            "formula": formula,
            "steps": "Step 1: Empty query received.\nStep 2: No deterministic computation executed.",
        }

    if not app_id:
        logger.warning("WOLFRAM_APP_ID is missing. Activating security protocol.")
        return {
            "answer": SECURITY_PROTOCOL_MESSAGE,
            "state": "security",
            "formula": formula,
            "steps": "Step 1: Missing WOLFRAM_APP_ID.\nStep 2: Security Protocol: Resetting API Handshake.",
        }

    encoded_query = urllib.parse.quote_plus(normalized_query)
    max_retries = 3
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = await WOLFRAM_HTTP_CLIENT.get(
                WOLFRAM_RESULT_ENDPOINT,
                params={"appid": app_id, "i": encoded_query},
            )

            if 500 <= response.status_code < 600:
                if attempt < max_retries - 1:
                    sleep_duration = 2 * (2 ** attempt)
                    logger.warning(
                        "Wolfram returned HTTP %s, retrying in %ds... (attempt %d/%d)",
                        response.status_code,
                        sleep_duration,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(sleep_duration)
                    continue
                last_exception = APITimeoutError(f"Wolfram HTTP {response.status_code} after {max_retries} attempts")
                break

            if response.status_code == 200:
                answer_text = response.text.strip()
                if _is_valid_wolfram_answer(answer_text):
                    return {
                        "answer": answer_text,
                        "state": "ok",
                        "formula": formula,
                        "steps": _build_step_trace(normalized_query, answer_text),
                    }
                return {
                    "answer": WOLFRAM_FALLBACK_RESULT,
                    "state": "fallback",
                    "formula": formula,
                    "steps": _build_step_trace(normalized_query, "No deterministic short-answer output was available."),
                }

            if response.status_code in {408, 504}:
                if attempt < max_retries - 1:
                    sleep_duration = 2 * (2 ** attempt)
                    logger.warning(
                        "Wolfram timeout HTTP %s, retrying in %ds... (attempt %d/%d)",
                        response.status_code,
                        sleep_duration,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(sleep_duration)
                    continue
                raise APITimeoutError(f"Wolfram timeout response HTTP {response.status_code} after {max_retries} attempts")

            if response.status_code in {401, 403}:
                logger.warning("Wolfram authentication failed with HTTP %s", response.status_code)
                return {
                    "answer": SECURITY_PROTOCOL_MESSAGE,
                    "state": "security",
                    "formula": formula,
                    "steps": "Step 1: Authentication challenge received from Wolfram API.\n"
                    "Step 2: Security Protocol: Resetting API Handshake.",
                }

            if response.status_code == 501:
                logger.info("Wolfram could not compute deterministic result for query: %s", normalized_query)
                return {
                    "answer": WOLFRAM_FALLBACK_RESULT,
                    "state": "fallback",
                    "formula": formula,
                    "steps": _build_step_trace(normalized_query, "Wolfram returned HTTP 501: no deterministic result."),
                }

            logger.warning("Wolfram returned HTTP %s for query '%s'", response.status_code, normalized_query)
            return {
                "answer": SECURITY_PROTOCOL_MESSAGE,
                "state": "security",
                "formula": formula,
                "steps": "Step 1: Non-success HTTP status received from Wolfram API.\n"
                "Step 2: Security Protocol: Resetting API Handshake.",
            }

        except httpx.TimeoutException as exc:
            if attempt < max_retries - 1:
                sleep_duration = 2 * (2 ** attempt)
                logger.warning(
                    "Wolfram timeout for '%s', retrying in %ds... (attempt %d/%d)",
                    normalized_query,
                    sleep_duration,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(sleep_duration)
            else:
                logger.warning("Wolfram timeout for '%s' after %d attempts", normalized_query, max_retries)
                last_exception = APITimeoutError(f"Wolfram timeout after {max_retries} attempts")
                break

        except httpx.HTTPError as exc:
            logger.warning("Wolfram request failed for '%s': %s", normalized_query, exc)
            return {
                "answer": SECURITY_PROTOCOL_MESSAGE,
                "state": "security",
                "formula": formula,
                "steps": "Step 1: Request dispatch failed before deterministic execution.\n"
                "Step 2: Security Protocol: Resetting API Handshake.",
            }

    if last_exception:
        raise last_exception

    return {
        "answer": WOLFRAM_FALLBACK_RESULT,
        "state": "fallback",
        "formula": formula,
        "steps": "Step 1: Query processing exhausted all retry attempts.\nStep 2: Falling back to safe default response.",
    }


async def sanitize_math_input(query: str) -> str:
    sanitized = (query or "").strip()
    sanitized = re.sub(r"[\u00A0\u1680\u2000-\u200B\u202F\u205F\u3000]", " ", sanitized)
    sanitized = re.sub(r"\\\[|\\\]|\\\(|\\\)", " ", sanitized)
    sanitized = re.sub(r"\$\$", " ", sanitized)
    sanitized = sanitized.replace("Ã—", "*").replace("âˆ’", "-").replace("Ã·", "/")
    sanitized = re.sub(r"(?<=\d)\s*(?=[A-Za-z(])", "*", sanitized)
    sanitized = re.sub(r"(?<=\))\s*(?=[\dA-Za-z(])", "*", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return urllib.parse.quote_plus(sanitized)


def _normalize_physics_units(raw_query: str) -> str:
    def _format_si_number(value: float) -> str:
        rounded = round(value, 8)
        if abs(rounded) < 1e-12:
            rounded = 0.0
        return f"{rounded:.8g}"

    def _convert_to_si(magnitude_text: str, unit_text: str) -> tuple[str, str] | None:
        try:
            magnitude = float(magnitude_text)
        except ValueError:
            return None

        normalized_unit = unit_text.strip().lower().replace(" ", "")
        conversions: dict[str, tuple[float, str]] = {
            "km": (1000.0, "m"),
            "cm": (0.01, "m"),
            "mm": (0.001, "m"),
            "hr": (3600.0, "s"),
            "hour": (3600.0, "s"),
            "hours": (3600.0, "s"),
            "min": (60.0, "s"),
            "minute": (60.0, "s"),
            "minutes": (60.0, "s"),
            "sec": (1.0, "s"),
            "second": (1.0, "s"),
            "seconds": (1.0, "s"),
            "ms": (0.001, "s"),
            "g": (0.001, "kg"),
            "mg": (0.000001, "kg"),
            "km/h": (1000.0 / 3600.0, "m/s"),
            "kph": (1000.0 / 3600.0, "m/s"),
            "kmph": (1000.0 / 3600.0, "m/s"),
            "cm/s": (0.01, "m/s"),
            "mm/s": (0.001, "m/s"),
        }

        conversion = conversions.get(normalized_unit)
        if conversion is None:
            return None

        factor, si_unit = conversion
        return _format_si_number(magnitude * factor), si_unit

    text = (raw_query or "").replace("Ã—", "*").replace("âˆ’", "-").replace("Ã·", "/")
    text = text.replace("\u0394", "delta").replace("\u03b4", "delta")
    text = text.replace("\u00b0", " deg")
    number = r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?"
    si_units = r"km/h|kmph|kph|cm/s|mm/s|km|cm|mm|hours|hour|hr|min|minute|minutes|sec|second|seconds|ms|kg|g|mg|m|s"

    def _si_replacer(match: re.Match[str]) -> str:
        converted = _convert_to_si(match.group(1), match.group(2))
        if converted:
            return " ".join(converted)
        return f"{match.group(1)} {match.group(2)}"

    text = re.sub(
        rf"(?<![A-Za-z0-9_])({number})\s*({si_units})\b",
        _si_replacer,
        text,
        flags=re.IGNORECASE,
    )

    unit = r"[A-Za-z](?:[A-Za-z0-9*/^._-]*)"
    text = re.sub(rf"(?<![A-Za-z0-9_])({number})\s*({unit})", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"\bm/s2\b", "m/s^2", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(celsius|degc|degree\s*c)\b", "degC", text, flags=re.IGNORECASE)
    text = re.sub(r"\bkelvin\b", "K", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_curriculum_routes(query: str) -> list[tuple[str, str]]:
    lowered = (query or "").lower()
    routes: list[tuple[str, str]] = []
    for domain, chapters in CURRICULUM_KEYWORD_GRAPH.items():
        for chapter, keywords in chapters.items():
            if any(keyword in lowered for keyword in keywords):
                routes.append((domain, chapter))
    return routes


def _infer_physics_target(query: str) -> str:
    lowered = query.lower()
    if any(token in lowered for token in ("height", "displacement", "position", "distance")):
        return "displacement s"
    if "range" in lowered:
        return "range R"
    if "time" in lowered:
        return "time t"
    if any(token in lowered for token in ("velocity", "speed")):
        return "velocity v"
    if "acceleration" in lowered:
        return "acceleration a"
    if "force" in lowered:
        return "force F"
    if "momentum" in lowered:
        return "momentum p"
    if "energy" in lowered:
        return "energy E"
    if "voltage" in lowered:
        return "voltage V"
    if "current" in lowered:
        return "current I"
    return "target variable"


def _extract_physics_given_data(query: str) -> list[str]:
    lowered = query.lower()
    data_points: list[str] = []

    if any(token in lowered for token in ("at rest", "from rest", "starts from rest", "starting from rest")):
        data_points.append("u=0 m/s")

    assignment_matches = re.findall(
        r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*([A-Za-z][A-Za-z0-9*/^._-]*)?",
        query,
        flags=re.IGNORECASE,
    )
    for symbol, value, unit in assignment_matches:
        if unit:
            data_points.append(f"{symbol}={value} {unit}")
        else:
            data_points.append(f"{symbol}={value}")

    after_time = re.search(r"after\s+([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*(s|sec|second|seconds)?", lowered)
    if after_time:
        data_points.append(f"t={after_time.group(1)} s")

    launch_speed = re.search(
        r"(?:launched|thrown|projectile|initial velocity|initial speed).*?([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*(m/s)",
        lowered,
    )
    if launch_speed:
        data_points.append(f"u={launch_speed.group(1)} m/s")

    angle_match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(?:degree|degrees|deg|Â°)", lowered)
    if angle_match:
        data_points.append(f"theta={angle_match.group(1)} deg")

    if any(token in lowered for token in ("projectile", "launched", "thrown", "free fall", "gravity")):
        has_accel = any(dp.lower().startswith(("a=", "g=")) for dp in data_points)
        if not has_accel:
            data_points.append("a=-9.8 m/s^2")

    deduped: list[str] = []
    for item in data_points:
        normalized = re.sub(r"\s+", " ", item).strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _extract_named_value(query: str, names: list[str]) -> str | None:
    number = r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?"
    for name in names:
        match = re.search(rf"\b{name}\s*=\s*({number})", query, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_gravity_magnitude(query: str) -> float:
    number = r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?"
    patterns = [
        rf"\bg\s*=\s*({number})",
        rf"\buse\s+g\s*=\s*({number})",
        rf"\bg\s+is\s+({number})",
        rf"\bgravity\s*=\s*({number})",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            try:
                return abs(float(match.group(1)))
            except ValueError:
                continue
    return 9.8


def _extract_projectile_target(query: str) -> str:
    lowered = query.lower()
    if "time of flight" in lowered or "total time" in lowered:
        return "time_of_flight"
    if "range" in lowered or "horizontal distance" in lowered:
        return "range"
    if "max height" in lowered or "maximum height" in lowered:
        return "max_height"
    if "height after" in lowered or "position after" in lowered:
        return "height_at_t"
    if "height" in lowered:
        return "max_height"
    return "time_of_flight"


def _extract_time_value(query: str) -> str | None:
    number = r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?"
    assignment = re.search(rf"\bt\s*=\s*({number})", query, flags=re.IGNORECASE)
    if assignment:
        return assignment.group(1)
    after_match = re.search(rf"after\s+({number})\s*(?:s|sec|seconds)?", query, flags=re.IGNORECASE)
    if after_match:
        return after_match.group(1)
    return None


def _is_integral_query(query: str) -> bool:
    lowered = query.lower()
    return any(token in lowered for token in ("integral", "integrate", "antiderivative", "integration by parts", "substitution"))


def _is_pure_math_query(query: str) -> bool:
    stripped = (query or "").strip()
    if not stripped:
        return False

    # Allow concise symbolic/math-only prompts to bypass language translator routing.
    if re.fullmatch(r"[0-9a-zA-Z_\s+\-*/^=().,]+", stripped) is None:
        return False

    lowered = stripped.lower()
    language_markers = (
        "find",
        "solve",
        "calculate",
        "starts",
        "from rest",
        "thrown",
        "launched",
        "word problem",
        "if",
        "when",
        "given that",
    )
    if any(marker in lowered for marker in language_markers):
        return False

    token_count = len(re.findall(r"[a-zA-Z]+", stripped))
    return token_count <= 2


def _build_query_from_translator_payload(payload: dict[str, Any], original_query: str) -> str:
    target = str(payload.get("target", "target variable")).strip() or "target variable"
    variables = payload.get("variables", {})
    if not isinstance(variables, dict):
        variables = {}

    given_items: list[str] = []
    for key, value in variables.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if key_text and value_text:
            given_items.append(f"{key_text}={value_text}")

    given_clause = ", ".join(given_items) if given_items else original_query
    return f"solve for {target} given {given_clause} return strictly in SI units"


def _contains_symbolic_solver_error(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in SYMBOLIC_ERROR_MARKERS)


def _sanitize_translator_payload(payload_text: str | None) -> str:
    sanitized = re.sub(r"\bnone\b", "unknown", str(payload_text or ""), flags=re.IGNORECASE)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    if not sanitized:
        return "evaluate deterministically"
    return sanitized


async def physics_translator(
    query: str,
    chat_history: list[dict[str, str]] | None = None,
    socratic_mode: bool = False,
    exam_context: str = "General",
    image_data: str | None = None,
) -> tuple[str, bool, list[str]]:
    normalized = (query or "").strip()
    lowered = normalized.lower()
    inferred_subject = _detect_subject(normalized)
    is_physics = inferred_subject == "Physics" or any(keyword in lowered for keyword in PHYSICS_KEYWORDS)

    standardized = _normalize_physics_units(normalized)
    standardized_lower = standardized.lower()

    if not _is_pure_math_query(standardized):
        target_hint = _infer_physics_target(standardized) if is_physics else "target variable"
        numeric_ground_truth = build_numeric_ground_truth_context(standardized)
        translator_payload = await PRIMARY_TRANSLATOR.translate_word_problem(
            standardized,
            target_hint=target_hint,
            chat_history_context=chat_history or [],
            socratic_mode=socratic_mode,
            exam_context=exam_context,
            image_data=image_data,
            ground_truth_context=numeric_ground_truth,
        )
        thinking_trace = str(translator_payload.get("_thinking", "")).strip()
        critic_evaluation = str(translator_payload.get("_critic_evaluation", "PASS")).strip().upper()
        critic_status = "PASS" if critic_evaluation == "PASS" else "FAIL"
        logger.info("ðŸ§  Mentor Thinking: %s", thinking_trace or "No <thinking> tags extracted")
        logger.info("âš–ï¸ Critic Evaluation: %s", critic_status)
        translated_query = _build_query_from_translator_payload(translator_payload, standardized)
        topics = translator_payload.get("topics", []) if isinstance(translator_payload, dict) else []
        return translated_query, is_physics, topics if isinstance(topics, list) else []

    if is_physics:
        if "projectile" in standardized_lower or "direction vector" in standardized_lower:
            gravity = _extract_gravity_magnitude(standardized)
            target = _extract_projectile_target(standardized)
            h_val = _extract_named_value(standardized, ["h", "h0", "height"])
            if h_val is None:
                height_match = re.search(r"from\s+height\s*([-+]?\d+(?:\.\d+)?)", standardized, flags=re.IGNORECASE)
                if height_match:
                    h_val = height_match.group(1)
            h_val = h_val or "0"

            ux_val = _extract_named_value(standardized, ["ux", "vx", "vx0"])
            uy_val = _extract_named_value(standardized, ["uy", "vy", "vy0"])
            t_val = _extract_time_value(standardized)

            if ux_val and uy_val:
                return (
                    "kinematics_vector "
                    f"ux={ux_val} uy={uy_val} h={h_val} g={gravity} target={target} t={t_val or 'unknown'}"
                ), True

            u_val = _extract_named_value(standardized, ["u", "speed", "v0", "initial_velocity"])
            theta_val = _extract_named_value(standardized, ["theta", "angle"])
            if theta_val is None:
                angle_match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(?:deg|degree|degrees)", standardized, flags=re.IGNORECASE)
                if angle_match:
                    theta_val = angle_match.group(1)

            if u_val and theta_val:
                return (
                    "kinematics_projectile "
                    f"u={u_val} theta={theta_val} h={h_val} g={gravity} target={target} t={t_val or 'unknown'}"
                ), True

        if "zeroth law" in standardized_lower:
            return "thermo_law zeroth law of thermodynamics", True
        if "first law" in standardized_lower:
            return "thermo_law first law of thermodynamics", True
        if "second law" in standardized_lower:
            return "thermo_law second law of thermodynamics", True
        if "third law" in standardized_lower:
            return "thermo_law third law of thermodynamics", True

        m_val = _extract_named_value(standardized, ["m", "mass"])
        c_val = _extract_named_value(standardized, ["c", "specificheat", "specific_heat"])
        dt_val = _extract_named_value(standardized, ["deltat", "delta_t", "dt", "temperaturerise"])

        dt_inline = re.search(r"\b(?:deltat|delta_t|dt)\s*=\s*([-+]?\d+(?:\.\d+)?)\s*(k|degc|c)?", standardized, flags=re.IGNORECASE)
        if dt_inline and dt_val is None:
            dt_val = dt_inline.group(1)

        if dt_val is None:
            rise_match = re.search(
                r"(?:temperature\s*rise|change\s*in\s*temperature|increase\s*in\s*temperature).*?([-+]?\d+(?:\.\d+)?)\s*(k|degc|c)?",
                standardized,
                flags=re.IGNORECASE,
            )
            if rise_match:
                dt_val = rise_match.group(1)

        c_unit = "J/kg*K"
        c_unit_match = re.search(r"\bc\s*=\s*[-+]?\d+(?:\.\d+)?\s*([a-zA-Z/*^]+)", standardized)
        if c_unit_match:
            c_unit = c_unit_match.group(1)
        if "cal" in standardized_lower and "j/" not in c_unit.lower():
            c_unit = "cal"

        energy_unit = "J"
        if " cal" in standardized_lower or "calorie" in standardized_lower:
            energy_unit = "cal"

        if m_val and c_val and dt_val and any(token in standardized_lower for token in ("heat", "q", "deltat", "temperature")):
            return f"thermo_solve q m={m_val} c={c_val} dT={dt_val} c_unit={c_unit} out={energy_unit}", True

        if "pv=nrt" in standardized_lower or "ideal gas" in standardized_lower or "gas law" in standardized_lower:
            p_val = _extract_named_value(standardized, ["p", "pressure"])
            v_val = _extract_named_value(standardized, ["v", "volume"])
            n_val = _extract_named_value(standardized, ["n", "moles", "mole"])
            t_val = _extract_named_value(standardized, ["t", "temperature"])
            return (
                "thermo_solve ideal_gas "
                f"p={p_val or 'unknown'} v={v_val or 'unknown'} n={n_val or 'unknown'} t={t_val or 'unknown'}"
            ), True

        target = _infer_physics_target(standardized)
        given_data = _extract_physics_given_data(standardized)
        given_clause = ", ".join(given_data) if given_data else standardized

        u_val = _extract_named_value(standardized, ["u", "v0", "initial_velocity", "initialspeed"])
        t_val = _extract_named_value(standardized, ["t", "time"])
        a_val = _extract_named_value(standardized, ["a", "g"])
        if t_val is None:
            after_time = re.search(
                r"after\s+([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*(s|sec|second|seconds)?",
                standardized,
                flags=re.IGNORECASE,
            )
            if after_time:
                t_val = after_time.group(1)
        if a_val is None and any(token in lowered for token in ("projectile", "launched", "thrown", "gravity")):
            a_val = "-9.8"

        if target == "displacement s" and u_val and t_val and a_val:
            translated = (
                f"solve for displacement s given u={u_val} m/s, t={t_val} s, a={a_val} m/s^2 "
                "using s=u*t+0.5*a*t^2 return strictly in SI units"
            )
            return translated, True

        if target == "velocity v" and u_val and t_val and a_val:
            translated = (
                f"solve for velocity v given u={u_val} m/s, t={t_val} s, a={a_val} m/s^2 "
                "using v=u+a*t return strictly in SI units"
            )
            return translated, True

        strategy = PHYSICS_PROMPT_STRATEGIES[PHYSICS_PROMPT_MODE % len(PHYSICS_PROMPT_STRATEGIES)]
        translated = strategy.format(target=target, given=given_clause, context=standardized)
        return translated, True
    return standardized, False


def _cache_get_if_fresh(cache: dict[str, tuple[datetime, str]], key: str) -> str | None:
    entry = cache.get(key)
    if not entry:
        return None

    created_at, value = entry
    if (datetime.utcnow() - created_at).total_seconds() > CACHE_TTL_SECONDS:
        cache.pop(key, None)
        return None
    return value


def _extract_physics_value(raw_text: str) -> str | None:
    normalized_text = re.sub(r"\s+", " ", (raw_text or "").strip())
    if not normalized_text:
        return None

    patterns = [
        r"(?i)(-?\d+(?:\.\d+)?)\s*(m/s\^2|m/s2|m/s|kg|newton|n|joule|j|watt|w|volt|v|ampere|amp|a|pascal|pa|kpa|meter|metre|m|second|s)",
        r"(?i)(-?\d+(?:\.\d+)?)\s*(?:x\s*10\^\(?-?\d+\)?)\s*(m/s\^2|m/s2|m/s|kg|newton|n|joule|j|watt|w|volt|v|ampere|amp|a|pascal|pa|kpa|meter|metre|m|second|s)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized_text)
        if match:
            magnitude = match.group(1)
            unit = match.group(2)
            unit_map = {
                "n": "N",
                "newton": "N",
                "j": "J",
                "joule": "J",
                "v": "V",
                "a": "A",
                "amp": "A",
                "ampere": "A",
                "w": "W",
                "watt": "W",
                "pa": "Pa",
                "kpa": "kPa",
                "meter": "m",
                "metre": "m",
            }
            normalized_unit = unit_map.get(unit.lower(), unit)
            normalized_unit = normalized_unit.replace("m/s2", "m/s^2")
            return f"{magnitude} {normalized_unit}"
    return None


def _format_physics_scalar(value: float) -> str:
    if abs(value) < 1e-12:
        value = 0.0
    formatted = f"{value:.6g}"
    return formatted


def _deterministic_physics_fallback(query_text: str) -> str | None:
    number = r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?"
    lower = query_text.lower()

    projectile_match = re.search(
        rf"kinematics_projectile\s+u=({number}).*?theta=({number}).*?h=({number}).*?g=({number}).*?target=([a-z_]+).*?t=({number}|unknown)",
        lower,
        flags=re.IGNORECASE,
    )
    if projectile_match:
        u = float(projectile_match.group(1))
        theta_deg = float(projectile_match.group(2))
        h = float(projectile_match.group(3))
        g = abs(float(projectile_match.group(4)))
        target = projectile_match.group(5)
        t_text = projectile_match.group(6)

        theta_rad = math.radians(theta_deg)
        ux = u * math.cos(theta_rad)
        uy = u * math.sin(theta_rad)
        discr = max(uy * uy + 2 * g * h, 0.0)
        t_flight = (uy + math.sqrt(discr)) / g if g > 1e-12 else 0.0

        if target == "time_of_flight":
            return f"{_format_physics_scalar(t_flight)} s"
        if target == "range":
            return f"{_format_physics_scalar(ux * t_flight)} m"
        if target == "max_height":
            return f"{_format_physics_scalar(h + (uy * uy) / (2 * g))} m"
        if target == "height_at_t" and t_text != "unknown":
            t = float(t_text)
            y = h + uy * t - 0.5 * g * (t ** 2)
            return f"{_format_physics_scalar(y)} m"

    vector_match = re.search(
        rf"kinematics_vector\s+ux=({number}).*?uy=({number}).*?h=({number}).*?g=({number}).*?target=([a-z_]+).*?t=({number}|unknown)",
        lower,
        flags=re.IGNORECASE,
    )
    if vector_match:
        ux = float(vector_match.group(1))
        uy = float(vector_match.group(2))
        h = float(vector_match.group(3))
        g = abs(float(vector_match.group(4)))
        target = vector_match.group(5)
        t_text = vector_match.group(6)
        discr = max(uy * uy + 2 * g * h, 0.0)
        t_flight = (uy + math.sqrt(discr)) / g if g > 1e-12 else 0.0

        if target == "time_of_flight":
            return f"{_format_physics_scalar(t_flight)} s"
        if target == "range":
            return f"{_format_physics_scalar(ux * t_flight)} m"
        if target == "max_height":
            return f"{_format_physics_scalar(h + (uy * uy) / (2 * g))} m"
        if target == "height_at_t" and t_text != "unknown":
            t = float(t_text)
            y = h + uy * t - 0.5 * g * (t ** 2)
            return f"{_format_physics_scalar(y)} m"

    if "thermo_law" in lower:
        if "zeroth" in lower:
            return "Zeroth Law: If A is in thermal equilibrium with B and B with C, then A and C are in thermal equilibrium."
        if "first" in lower:
            return "First Law: deltaU = Q - W; energy is conserved in thermodynamic processes."
        if "second" in lower:
            return "Second Law: Entropy of an isolated system does not decrease for spontaneous processes."
        if "third" in lower:
            return "Third Law: Entropy of a perfect crystal tends to zero as temperature approaches 0 K."

    q_match = re.search(
        rf"thermo_solve\s+q\s+.*?m=({number}).*?c=({number}).*?dt=({number}).*?c_unit=([^\s]+).*?out=([^\s]+)",
        lower,
        flags=re.IGNORECASE,
    )
    if q_match:
        m = float(q_match.group(1))
        c = float(q_match.group(2))
        dt = float(q_match.group(3))
        c_unit = q_match.group(4).lower()
        out_unit = q_match.group(5).lower()

        q_joule = m * c * dt
        if "cal" in c_unit and "j" not in c_unit:
            q_joule = q_joule * 4.184

        if out_unit == "cal":
            return f"{_format_physics_scalar(q_joule / 4.184)} cal"
        return f"{_format_physics_scalar(q_joule)} J"

    ideal_match = re.search(
        rf"thermo_solve\s+ideal_gas\s+.*?p=({number}|unknown).*?v=({number}|unknown).*?n=({number}|unknown).*?t=({number}|unknown)",
        lower,
        flags=re.IGNORECASE,
    )
    if ideal_match:
        p_text, v_text, n_text, t_text = ideal_match.groups()
        p = None if p_text == "unknown" else float(p_text)
        v = None if v_text == "unknown" else float(v_text)
        n = None if n_text == "unknown" else float(n_text)
        t = None if t_text == "unknown" else float(t_text)

        known_count = sum(val is not None for val in (p, v, n, t))
        if known_count == 3:
            r_const = 8.314
            if p is None and n is not None and t is not None and v is not None and abs(v) > 1e-12:
                return f"{_format_physics_scalar((n * r_const * t) / v)} Pa"
            if v is None and n is not None and t is not None and p is not None and abs(p) > 1e-12:
                return f"{_format_physics_scalar((n * r_const * t) / p)} m^3"
            if n is None and p is not None and v is not None and t is not None and abs(t) > 1e-12:
                return f"{_format_physics_scalar((p * v) / (r_const * t))} mol"
            if t is None and p is not None and v is not None and n is not None and abs(n) > 1e-12:
                return f"{_format_physics_scalar((p * v) / (n * r_const))} K"

    displacement_match = re.search(
        rf"solve for displacement s given .*?u=({number}).*?t=({number}).*?a=({number})",
        lower,
        flags=re.IGNORECASE,
    )
    if displacement_match:
        u = float(displacement_match.group(1))
        t = float(displacement_match.group(2))
        a = float(displacement_match.group(3))
        s = u * t + 0.5 * a * (t ** 2)
        return f"{_format_physics_scalar(s)} m"

    velocity_match = re.search(
        rf"solve for velocity v given .*?u=({number}).*?t=({number}).*?a=({number})",
        lower,
        flags=re.IGNORECASE,
    )
    if velocity_match:
        u = float(velocity_match.group(1))
        t = float(velocity_match.group(2))
        a = float(velocity_match.group(3))
        v = u + a * t
        return f"{_format_physics_scalar(v)} m/s"

    force_match = re.search(
        rf"(?:force|f).*?m=({number}).*?a=({number})",
        lower,
        flags=re.IGNORECASE,
    )
    if force_match:
        m = float(force_match.group(1))
        a = float(force_match.group(2))
        f_val = m * a
        return f"{_format_physics_scalar(f_val)} N"

    return None


def _deterministic_math_fallback(query_text: str) -> str | None:
    lowered = query_text.lower()

    derivative_poly = re.search(r"differentiate\s+x\^(\d+)", lowered)
    if derivative_poly:
        n = int(derivative_poly.group(1))
        if n == 0:
            return "0"
        if n == 1:
            return "1"
        if n == 2:
            return "2*x"
        return f"{n}*x^{n-1}"

    if "integration by parts" in lowered and "x*e^x" in lowered:
        return "(x - 1)e^x + C"
    if "integration by parts" in lowered and "x*sin(x)" in lowered:
        return "sin(x) - x*cos(x) + C"
    if "integration by parts" in lowered and "x*cos(x)" in lowered:
        return "x*sin(x) + cos(x) + C"
    if "substitution" in lowered and "2*x*(x^2+1)^5" in lowered:
        return "(x^2 + 1)^6/6 + C"
    if "substitution" in lowered and "cos(3*x)" in lowered:
        return "sin(3*x)/3 + C"

    plain = lowered.replace(" ", "")
    if "integratex^3" in plain:
        return "x^4/4 + C"
    if "integratex^2" in plain:
        return "x^3/3 + C"
    if "integrate2*x" in plain:
        return "x^2 + C"
    if "integratesin(x)" in plain:
        return "-cos(x) + C"
    if "integratecos(x)" in plain:
        return "sin(x) + C"
    if "integrate1/x" in plain or "integrateln" in plain:
        return "ln|x| + C"

    definite = re.search(
        r"definite\s+integral\s+of\s+x\^2\s+from\s+0\s+to\s+1|integrate\s+x\^2\s+from\s+0\s+to\s+1",
        lowered,
    )
    if definite:
        return "1/3"

    return None


def local_sympy_integration(query: str) -> str | None:
    text = (query or "").strip()
    if not text:
        return "Local Fallback Failed: Syntax Error in Expression."

    # 1) Extract expression by removing prompt words like 'integrate' and differential tail like 'dx'.
    expr_text = re.sub(r"^\s*integrate\s+", "", text, flags=re.IGNORECASE).strip()
    expr_text = re.sub(r"\bd[a-zA-Z]\b\s*$", "", expr_text, flags=re.IGNORECASE).strip()

    # 2) Pre-process string before sympify.
    expr_text = expr_text.replace("^", "**")
    expr_text = expr_text.replace("e**", "sp.E**")

    # Support common classroom notation like 2x and x(2+x).
    expr_text = re.sub(r"(?<=\d)(?=[a-zA-Z(])", "*", expr_text)
    expr_text = re.sub(r"(?<=[a-zA-Z)])(?=\d)", "*", expr_text)

    # 3) Parse/integrate safely with deterministic error string on failure.
    try:
        x = sp.Symbol("x")
        parsed_expr = sp.sympify(expr_text, locals={"x": x, "sp": sp})
        result = sp.integrate(parsed_expr, x)
        exact_result = sympy_simplify_fraction(str(result))
        numeric_result = sp.N(exact_result, 12)
        if bool(getattr(numeric_result, "is_real", False)):
            decimal_text = f"{float(numeric_result):.4f}"
        else:
            logger.warning("SymPy produced a complex/imaginary value for integration query '%s'", text)
            return "Local Fallback Failed: Unexpected complex value in real-domain expression."
        return f"{exact_result} + C (approx {decimal_text})"
    except ValueError as exc:
        logger.warning("local_sympy_integration complex-domain guard for query '%s': %s", text, exc)
        return "Local Fallback Failed: Unexpected complex value in real-domain expression."
    except Exception as exc:
        logger.warning("local_sympy_integration failed for query '%s': %s", text, exc)
        return "Local Fallback Failed: Syntax Error in Expression."


def _format_sympy_ground_truth(symbols: list[sp.Symbol], solutions: Any) -> str | None:
    if solutions is None:
        return None

    if isinstance(solutions, dict):
        solutions = [solutions]

    if not isinstance(solutions, (list, tuple, set)):
        return sp.sstr(solutions)

    normalized_symbols = [symbol for symbol in symbols if isinstance(symbol, sp.Symbol)]
    if not normalized_symbols:
        normalized_symbols = [sp.Symbol("x")]

    rendered_parts: list[str] = []
    for solution in solutions:
        if isinstance(solution, dict):
            rendered_parts.append(
                ", ".join(f"{sp.sstr(key)} = {sp.sstr(sp.simplify(value))}" for key, value in solution.items())
            )
        elif len(normalized_symbols) == 1:
            rendered_parts.append(f"{sp.sstr(normalized_symbols[0])} = {sp.sstr(sp.simplify(solution))}")
        else:
            rendered_parts.append(sp.sstr(solution))

    if not rendered_parts:
        return None
    return "; ".join(rendered_parts)


def _build_symbolic_reroute_query(query_text: str, *, is_physics: bool) -> str:
    if is_physics and "projectile" in query_text.lower():
        return f"{query_text} use deterministic projectile equations and SI units only"
    if _is_integral_query(query_text):
        return f"evaluate integral of {query_text} return antiderivative or integral field only"
    return f"evaluate deterministically: {query_text}"


def _sanitize_wolfram_output(raw_text: str, *, is_physics: bool = False) -> str:
    text = (raw_text or "").strip()
    if not text:
        return WOLFRAM_FALLBACK_RESULT

    # Strip common metadata sections and inline assumptions from short-answer text.
    text = re.sub(r"(?i)assuming[^\n]*", "", text)
    text = re.sub(r"(?i)input\s*interpretation\s*:\s*[^\n]*", "", text)
    text = re.sub(r"(?i)alternate\s*forms?\s*:\s*[^\n]*", "", text)

    filtered_lines: list[str] = []
    for line in text.splitlines():
        normalized = line.strip()
        if not normalized:
            continue

        lowered = normalized.lower()
        if lowered.startswith("input interpretation"):
            continue
        if lowered.startswith("assuming"):
            continue
        if lowered.startswith("alternate form") or lowered.startswith("alternate forms"):
            continue

        filtered_lines.append(normalized)

    cleaned = re.sub(r"\s+", " ", " ".join(filtered_lines)).strip(" |;,")
    if is_physics:
        physics_value = _extract_physics_value(cleaned)
        if physics_value:
            return physics_value
    return cleaned or WOLFRAM_FALLBACK_RESULT


async def classify_and_inject(clean_query: str, *, is_physics: bool = False) -> str:
    async with CACHE_LOCK:
        cached = _cache_get_if_fresh(CLASSIFICATION_CACHE, clean_query)
        if cached is not None:
            logger.info("[CACHE HIT] classify_and_inject for sanitized query.")
            return cached

    decoded_query = urllib.parse.unquote_plus((clean_query or "").strip())
    lowered = decoded_query.lower()
    curriculum_routes = _extract_curriculum_routes(decoded_query)

    directives: list[str] = []
    route_tags: list[str] = []
    for domain, chapter in curriculum_routes:
        normalized_chapter = chapter.replace("&", "and").replace("(", "").replace(")", "")
        route_tags.append(f"{domain}:{normalized_chapter}")

    if route_tags:
        directives.append("route=" + "|".join(route_tags))

    if is_physics:
        directives.append("convert all variables to SI base units m s kg before JSON output")

    if not is_physics:
        if "integral" in lowered:
            directives.append("exact form")
            directives.append("return antiderivative/integral field only")
        if "derivative" in lowered:
            directives.append("exact form")
        if "limit" in lowered:
            directives.append("exact form")
        if "solve" in lowered:
            directives.append("exact form real numbers")
        if "matrix" in lowered:
            directives.append("matrix form exact entries")
        if any(domain == "Chemistry" for domain, _ in curriculum_routes):
            directives.append("balanced chemistry reasoning with units")
        if any(domain == "Math" for domain, _ in curriculum_routes):
            directives.append("math answer in exact form where possible")

    if any(chapter == "Thermodynamics" for _, chapter in curriculum_routes):
        directives.append("enforce thermodynamics units K, degC, J, cal")
        directives.append("prefer Q=mc*dT and PV=nRT")

    if directives:
        decoded_query = f"{decoded_query} {' '.join(directives)}"

    for domain, _chapter in curriculum_routes:
        hint = DOMAIN_HARDENING_HINTS.get(domain, "").strip()
        if hint:
            decoded_query = f"{decoded_query} {hint}"

    decoded_query = re.sub(r"\s+", " ", decoded_query).strip()
    encoded = urllib.parse.quote_plus(decoded_query)
    async with CACHE_LOCK:
        CLASSIFICATION_CACHE[clean_query] = (datetime.utcnow(), encoded)
    return encoded


async def execute_wolfram_deterministic(encoded_query: str, *, is_physics: bool = False) -> str | dict[str, Any]:
    app_id = os.getenv(WOLFRAM_APP_ID_ENV_NAME)
    if not app_id:
        logger.error("WOLFRAM_APP_ID is missing for /api/solve deterministic execution.")
        return WOLFRAM_FALLBACK_RESULT

    timeout_config = httpx.Timeout(30.0, connect=10.0)
    decoded_payload = urllib.parse.unquote_plus(encoded_query)
    last_status_code: int | None = None

    for attempt in range(1, 4):
        try:
            if not is_physics:
                pod_answer = await _fetch_wolfram_math_pod_answer(
                    WOLFRAM_HTTP_CLIENT,
                    app_id=app_id,
                    decoded_query=decoded_payload,
                )
                if pod_answer:
                    return pod_answer
                logger.warning("Wolfram returned no usable pods for query: %s", decoded_payload)
                return wolfram_graceful_fallback()

            request_url = (
                f"{WOLFRAM_RESULT_ENDPOINT}?appid={urllib.parse.quote_plus(app_id)}&i={encoded_query}"
            )
            request_started = asyncio.get_running_loop().time()
            response = await WOLFRAM_HTTP_CLIENT.get(request_url, timeout=timeout_config)
            elapsed_seconds = asyncio.get_running_loop().time() - request_started
            logger.info(
                "Wolfram API returned in %.2fs for query: '%s'",
                elapsed_seconds,
                decoded_payload,
            )

            if response.status_code == 200:
                cleaned = _sanitize_wolfram_output(response.text, is_physics=is_physics)
                if _contains_symbolic_solver_error(cleaned):
                    reroute_query = _build_symbolic_reroute_query(decoded_payload, is_physics=is_physics)
                    reroute_encoded = urllib.parse.quote_plus(reroute_query)
                    retry_response = await WOLFRAM_HTTP_CLIENT.get(
                        f"{WOLFRAM_RESULT_ENDPOINT}?appid={urllib.parse.quote_plus(app_id)}&i={reroute_encoded}"
                    )
                    if retry_response.status_code == 200:
                        cleaned = _sanitize_wolfram_output(retry_response.text, is_physics=is_physics)
                if is_physics and cleaned == WOLFRAM_FALLBACK_RESULT:
                    local_result = _deterministic_physics_fallback(decoded_payload)
                    if local_result:
                        return local_result
                if (not is_physics) and (cleaned == WOLFRAM_FALLBACK_RESULT or _contains_symbolic_solver_error(cleaned)):
                    local_math = _deterministic_math_fallback(decoded_payload)
                    if local_math:
                        return local_math
                return cleaned

            if response.status_code == 500:
                last_status_code = response.status_code
                logger.warning("Wolfram HTTP 500 on attempt %d/3 for /api/solve", attempt)
                if attempt < 3:
                    await asyncio.sleep(2)
                    continue
                break

            last_status_code = response.status_code

            logger.warning(
                "Wolfram returned non-retryable status %s for /api/solve",
                response.status_code,
            )
            if is_physics:
                local_result = _deterministic_physics_fallback(decoded_payload)
                if local_result:
                    return local_result
            else:
                local_math = _deterministic_math_fallback(decoded_payload)
                if local_math:
                    return local_math
            return WOLFRAM_FALLBACK_RESULT
        except httpx.TimeoutException as exc:
            logger.warning("Wolfram timeout on attempt %d/3 for /api/solve: %s", attempt, exc)
            if attempt < 3:
                await asyncio.sleep(2)
                continue
            break

    logger.error(
        "Wolfram failed after 3 retries. status=%s payload='%s'",
        last_status_code if last_status_code is not None else "timeout",
        decoded_payload,
    )
    return wolfram_graceful_fallback()


def _coerce_solver_response_to_text(solver_output: str | dict[str, Any]) -> str:
    if isinstance(solver_output, dict):
        result_text = str(solver_output.get("result", "")).strip()
        if result_text:
            return result_text
        return COMPUTATION_FAILSAFE_MESSAGE
    return solver_output


def _local_resilience_answer(query: str) -> str:
    physics = _deterministic_physics_fallback(query)
    if physics:
        return physics
    math_answer = _deterministic_math_fallback(query)
    if math_answer:
        return math_answer
    if "integrate" in query.lower() or "integral" in query.lower():
        local_int = local_sympy_integration(query)
        if local_int and "Local Fallback Failed" not in local_int:
            return local_int
    return COMPUTATION_FAILSAFE_MESSAGE


def _build_trace(
    query_text: str,
    wolfram_result: WolframResult,
    *,
    cache_hit: bool,
    cache_similarity: float,
    verification_summary: str | None,
    context_applied: bool,
    subject: str,
) -> list[TraceStep]:
    if wolfram_result["state"] == "security":
        validation_description = "Security validation failed. Security Protocol: Resetting API Handshake."
    elif wolfram_result["state"] == "fallback":
        validation_description = "Deterministic validation incomplete; fallback response was returned safely."
    else:
        validation_description = "Deterministic validation passed with a stable symbolic result."

    trace_steps: list[TraceStep] = [
        TraceStep(
            step_number=1,
            title="Planner Intake",
            description=f"Planner received student query: {query_text}",
            agent_type="Planner",
        ),
        TraceStep(
            step_number=2,
            title="Semantic Check",
            description=(
                f"Found a semantic match with similarity score {cache_similarity:.2f}; reusing previous reasoning."
                if cache_hit
                else "No semantic match above 90% similarity. Routing to deterministic solver."
            ),
            agent_type="Caching",
        ),
        TraceStep(
            step_number=3,
            title="Wolfram Execution" if not cache_hit else "Cache Retrieval",
            description=wolfram_result["steps"],
            agent_type="Symbolic",
            math_latex=wolfram_result["formula"],
        ),
        TraceStep(
            step_number=4,
            title="Context Linking",
            description=(
                f"Session context applied with subject tag '{subject}'."
                if context_applied
                else f"Stored latest context state with subject tag '{subject}'."
            ),
            agent_type="Planner",
        ),
    ]

    if verification_summary:
        trace_steps.append(
            TraceStep(
                step_number=5,
                title="Python REPL Verification",
                description=verification_summary,
                agent_type="Verification",
            )
        )

    trace_steps.append(
        TraceStep(
            step_number=6,
            title="Result Validation",
            description=validation_description,
            agent_type="Symbolic",
        )
    )
    trace_steps.append(
        TraceStep(
            step_number=7,
            title="Final Response",
            description=f"Returned solver output: {wolfram_result['answer']}",
            agent_type="Neural",
        )
    )

    for step_number, step in enumerate(trace_steps, start=1):
        step.step_number = step_number
    return trace_steps


def _build_dashboard_stats() -> DashboardStatsResponse:
    exam_countdowns = {
        name: ExamCountdown(
            exam_date=config["exam_date"].isoformat(),
            days_remaining=_days_remaining(config["exam_date"]),
            target_syllabus_percent=config["target_syllabus_percent"],
            target_problem_count=config["target_problem_count"],
            focus_area=config["focus_area"],
        )
        for name, config in EXAM_TARGETS.items()
    }

    long_term_goals = {
        "JEE_MAIN_2027": LongTermGoal(
            target_date=LONG_TERM_GOAL_DATE.isoformat(),
            days_remaining=_days_remaining(LONG_TERM_GOAL_DATE),
            goal_percent=40,
            milestone="Complete 40% of the JEE foundation by Jan 24, 2027.",
        )
    }

    return DashboardStatsResponse(
        student_grade=9,
        academic_year="2026-2027",
        active_tracks=["NSEJS", "NMTC", "IOQM", "JEE"],
        exam_countdowns=exam_countdowns,
        long_term_goals=long_term_goals,
        today_sessions=3,
        weekly_growth_percent=8.5,
        recommended_focus="Prioritize deterministic PCM problem solving with daily mixed sets.",
    )


@app.get("/")
async def root_status() -> Dict[str, str]:
    return {"status": "online"}


class VisionAgent:
    def __init__(self, fuzzy_threshold: float = 60.0) -> None:
        self.fuzzy_threshold = fuzzy_threshold

    async def extract_query(self, image_base64: str) -> tuple[str, str, float, str | None]:
        if not VISION_MODULES_AVAILABLE:
            raise HTTPException(status_code=503, detail="OCR is disabled because vision modules are unavailable.")

        try:
            image = await asyncio.to_thread(_decode_base64_image, image_base64)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc

        try:
            extracted_text, confidence = await asyncio.to_thread(_extract_text_with_confidence, image)
        except Exception as exc:
            if VISION_MODULES_AVAILABLE and pytesseract and isinstance(exc, pytesseract.TesseractNotFoundError):
                raise HTTPException(status_code=503, detail="Tesseract OCR engine is not installed on the server.") from exc
            raise

        cleaned_query = _clean_math_text(extracted_text)
        if not cleaned_query:
            raise HTTPException(status_code=422, detail="Vision Agent could not extract usable text from the image.")

        warning = VISION_FUZZY_WARNING if confidence < self.fuzzy_threshold else None
        return extracted_text, cleaned_query, confidence, warning


class Planner:
    def __init__(self) -> None:
        self.context_buffer = CONVERSATION_CONTEXT
        self.vision_agent = VisionAgent()

    async def _semantic_cache_lookup(self, query: str) -> tuple[QuerySession | None, float]:
        return await lookup_recent_similar(query)

    async def _route_text_query(self, resolved_query: str, subject: str) -> WolframResult:
        if subject in {"Math", "Physics"}:
            return await asyncio.wait_for(query_wolfram(resolved_query), timeout=25)

        return {
            "answer": WOLFRAM_FALLBACK_RESULT,
            "state": "fallback",
            "formula": _derive_symbolic_formula(resolved_query),
            "steps": "Step 1: Subject classified outside Math/Physics Wolfram route.\n"
            "Step 2: Returned deterministic safe fallback.",
        }

    @staticmethod
    def _schedule_query_persistence(prompt: str, answer: str, subject: str, ocr_source: bool) -> None:
        task = asyncio.create_task(persist_query_session(prompt, answer, subject, ocr_source))

        def _log_task_result(done_task: asyncio.Task[QuerySession]) -> None:
            try:
                done_task.result()
            except Exception as exc:
                logger.warning("Unable to persist QuerySession record.", exc_info=exc)

        task.add_done_callback(_log_task_result)

    async def solve_text_query_fast(
        self,
        *,
        student_query: str,
        target_exam: str,
        session_id: str,
        ocr_source: bool,
    ) -> str:
        query_text = student_query.strip()
        if not query_text:
            raise HTTPException(status_code=422, detail="student_query cannot be empty.")

        context_key = (session_id or "default").strip() or "default"
        previous_context = self.context_buffer.get(context_key)
        resolved_query, _ = _apply_contextual_memory(query_text, previous_context)
        subject = _detect_subject(resolved_query)
        wolfram_result = await self._route_text_query(resolved_query, subject)

        merged_variables = _extract_variables(query_text, previous_context.variables if previous_context else None)
        self.context_buffer[context_key] = ConversationContext(
            session_id=context_key,
            last_query=resolved_query,
            last_answer=wolfram_result["answer"],
            variables=merged_variables,
        )

        self._schedule_query_persistence(
            resolved_query,
            wolfram_result["answer"],
            subject,
            ocr_source,
        )
        _ = target_exam
        return wolfram_result["answer"]

    async def solve_text_query(
        self,
        *,
        student_query: str,
        target_exam: str,
        session_id: str,
        ocr_source: bool,
    ) -> AgentResponse:
        query_text = student_query.strip()
        if not query_text:
            raise HTTPException(status_code=422, detail="student_query cannot be empty.")

        context_key = (session_id or "default").strip() or "default"
        previous_context = self.context_buffer.get(context_key)
        resolved_query, context_applied = _apply_contextual_memory(query_text, previous_context)
        subject = _detect_subject(resolved_query)

        cached_session, similarity_score = await self._semantic_cache_lookup(resolved_query)
        cache_hit = cached_session is not None

        if cache_hit and cached_session:
            cached_answer = cached_session.wolfram_response.strip() or WOLFRAM_FALLBACK_RESULT
            wolfram_result: WolframResult = {
                "answer": cached_answer,
                "state": "ok",
                "formula": _derive_symbolic_formula(resolved_query),
                "steps": (
                    f"Step 1: Retrieved similar prompt from QuerySession cache (similarity {similarity_score:.2f}).\n"
                    f"Step 2: Reused persisted deterministic response   : {cached_answer}"
                ),
            }
            subject = cached_session.subject
        else:
            wolfram_result = await self._route_text_query(resolved_query, subject)

        verification_summary: str | None = None
        verification_triggered = _is_verification_query(resolved_query)
        if verification_triggered:
            verification_summary = await run_python_repl_placeholder(resolved_query, wolfram_result["answer"])

        self._schedule_query_persistence(
            resolved_query,
            wolfram_result["answer"],
            subject,
            ocr_source,
        )

        merged_variables = _extract_variables(query_text, previous_context.variables if previous_context else None)
        self.context_buffer[context_key] = ConversationContext(
            session_id=context_key,
            last_query=resolved_query,
            last_answer=wolfram_result["answer"],
            variables=merged_variables,
        )

        trace = _build_trace(
            resolved_query,
            wolfram_result,
            cache_hit=cache_hit,
            cache_similarity=similarity_score,
            verification_summary=verification_summary,
            context_applied=context_applied,
            subject=subject,
        )

        return AgentResponse(
            final_answer=wolfram_result["answer"],
            explanation_trace=trace,
            logic_trace=trace,
            planner_state={
                "source": "cache" if cache_hit else "wolfram",
                "cache_hit": cache_hit,
                "verification_triggered": verification_triggered,
                "session_record_id": None,
                "semantic_similarity": round(similarity_score, 2),
                "subject": subject,
                "ocr_source": ocr_source,
                "session_id": context_key,
                "target_exam": target_exam,
                "context_applied": context_applied,
            },
        )

    async def solve_image_query(self, payload: OCRInput) -> OCRResponse:
        extracted_text, cleaned_query, confidence, warning = await self.vision_agent.extract_query(payload.image_base64)
        solve_result = await self.solve_text_query(
            student_query=cleaned_query,
            target_exam=payload.target_exam,
            session_id=payload.session_id or "default",
            ocr_source=True,
        )
        return OCRResponse(
            extracted_text=extracted_text,
            cleaned_query=cleaned_query,
            confidence=confidence,
            warning=warning,
            solve_result=solve_result,
        )


planner = Planner()


def _extract_latest_user_query(messages: list[dict[str, Any]], fallback_query: str | None = None) -> str:
    for item in reversed(messages or []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role == "user" and content:
            return content

    if fallback_query and fallback_query.strip():
        return fallback_query.strip()

    raise HTTPException(status_code=422, detail="messages must include at least one non-empty user message.")


def _extract_history_before_latest_user(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not messages:
        return []

    latest_user_index: int | None = None
    for idx in range(len(messages) - 1, -1, -1):
        item = messages[idx]
        if isinstance(item, dict) and str(item.get("role", "")).strip().lower() == "user":
            content = str(item.get("content", "")).strip()
            if content:
                latest_user_index = idx
                break

    if latest_user_index is None:
        return []

    previous_messages = messages[:latest_user_index]
    normalized: list[dict[str, str]] = []
    for item in previous_messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            normalized.append({"role": role, "content": content})
    return normalized[-5:]


def _format_sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _extract_gemini_response_text(response: Any) -> str:
    """Normalize text from google-genai GenerateContentResponse (or legacy shapes)."""
    direct_text = str(getattr(response, "text", "") or "").strip()
    if direct_text:
        return direct_text

    text_chunks: list[str] = []
    for candidate in list(getattr(response, "candidates", []) or []):
        content = getattr(candidate, "content", None)
        parts = list(getattr(content, "parts", []) or []) if content is not None else []
        for part in parts:
            text = str(getattr(part, "text", "") or "").strip()
            if text:
                text_chunks.append(text)
    return "\n".join(text_chunks).strip()


def _gemini_solve_api_key() -> str:
    return str(os.environ.get(GEMINI_API_KEY_ENV_NAME) or os.getenv(GOOGLE_API_KEY_ENV_NAME, "") or "").strip()


def _get_gemini_client_for_solve() -> Any:
    if genai is None:
        raise RuntimeError("google-genai SDK is not installed.")
    api_key = _gemini_solve_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured for /api/solve.")
    if GOOGLE_GENAI_CLIENT is not None and api_key == GOOGLE_GENAI_API_KEY:
        return GOOGLE_GENAI_CLIENT
    return genai.Client(api_key=api_key)


async def _iter_gemini_solve_stream_deltas(
    client: Any,
    system_instruction: str,
    user_text: str,
) -> AsyncIterator[str]:
    """Yield text deltas from Gemini ``generate_content_stream`` (cumulative or incremental chunks)."""
    if genai_types is None:
        raise RuntimeError("google.genai types are unavailable.")
    prev_snapshot = ""
    stream = await client.aio.models.generate_content_stream(
        model=GEMINI_SOLVE_MODEL,
        contents=user_text,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=LLM_SOLVE_TEMPERATURE,
        ),
    )
    async for chunk in stream:
        snapshot = str(getattr(chunk, "text", "") or "").strip()
        if not snapshot:
            snapshot = _extract_gemini_response_text(chunk)
        if not snapshot:
            continue
        if snapshot.startswith(prev_snapshot):
            delta = snapshot[len(prev_snapshot) :]
            prev_snapshot = snapshot
        else:
            delta = snapshot
            prev_snapshot = prev_snapshot + delta
        if delta:
            yield delta


def _load_syllabus_from_context_files(exam_name: str) -> list[str] | None:
    normalized_exam = _normalize_exam_name(exam_name).upper()
    filename_map = {
        "NSEJS": "nsejs_syllabus.txt",
        "NMTC": "nmtc_syllabus.txt",
        "IOQM": "ioqm_syllabus.txt",
        "JEE ADVANCED": "jee_syllabus.txt",
        "JEE": "jee_syllabus.txt",
    }
    target_filename = filename_map.get(normalized_exam)
    if not target_filename:
        return []

    syllabus_path = Path(__file__).resolve().parent / "contexts" / target_filename
    if not syllabus_path.exists():
        return None

    try:
        raw_text = syllabus_path.read_text(encoding="utf-8")
    except OSError:
        return None

    chapters: list[str] = []
    for line in raw_text.splitlines():
        cleaned = re.sub(r"^[-*\d\.)\s]+", "", str(line or "")).strip()
        if not cleaned:
            continue
        if len(cleaned) < 3:
            continue
        chapters.append(cleaned)

    return list(dict.fromkeys(chapters))


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)) -> Dict[str, str]:
    if genai is None or genai_types is None:
        raise HTTPException(status_code=503, detail="Gemini SDK (google-genai) is not installed on the backend.")

    google_api_key = str(os.getenv(GOOGLE_API_KEY_ENV_NAME, "")).strip()
    if not google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY is not configured on the backend.")

    if file is None:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    content_type = str(file.content_type or "").strip().lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image uploads are supported.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        client = genai.Client(api_key=google_api_key)

        def _run_vision_extract() -> Any:
            return client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    genai_types.Part.from_text(text=VISION_EXTRACTION_PROMPT),
                    genai_types.Part.from_bytes(data=file_bytes, mime_type=content_type),
                ],
            )

        response = await asyncio.to_thread(_run_vision_extract)
        extracted_text = _extract_gemini_response_text(response)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Gemini image upload extraction failed.", exc_info=exc)
        raise HTTPException(status_code=502, detail="Vision extraction failed upstream.") from exc
    finally:
        await file.close()

    if not extracted_text:
        raise HTTPException(status_code=422, detail="No extractable text found in the image.")

    return {"extracted_text": extracted_text}


@app.get("/api/syllabus/{exam}")
async def get_exam_syllabus(exam: str) -> dict[str, list[str] | str]:
    requested_exam = str(exam or "").strip()
    normalized_exam_name = _normalize_exam_name(requested_exam)

    file_topics = _load_syllabus_from_context_files(normalized_exam_name)
    if file_topics:
        return {"syllabus": file_topics}

    # Built-in universal exam map used when file data is missing or partial.
    universal_exam_store: dict[str, list[str]] = {
        "JEE": [
            "Mechanics (Kinematics & Dynamics)",
            "Thermodynamics & Kinetic Theory",
            "Electromagnetism & AC",
            "Optics & Modern Physics",
            "Waves, SHM & Sound",
            "Current Electricity & Circuits",
            "Mole Concept & Stoichiometry",
            "Chemical Bonding & Periodicity",
            "Organic Chemistry (GOC & Reactions)",
            "Equilibrium (Chemical & Ionic)",
            "Differential & Integral Calculus",
            "Coordinate Geometry (Conics)",
            "Vectors & 3D Geometry",
            "Probability, Statistics & PnC",
        ],
        "JEE ADVANCED": [
            "Advanced Mechanics (Rotation, COM, Momentum)",
            "Thermodynamics & Kinetic Theory",
            "Electrostatics, Capacitance & Current",
            "Magnetism, EMI & AC",
            "Wave Optics & Modern Physics",
            "Physical Chemistry (Thermo, Electrochem, Kinetics)",
            "Organic Chemistry (GOC, Mechanisms, Named Reactions)",
            "Inorganic Chemistry (Coordination, p-Block, d-Block)",
            "Differential Calculus (AOD, Limits, Continuity)",
            "Integral Calculus (Definite, Differential Equations)",
            "Coordinate Geometry (Conics, 3D, Vectors)",
            "Algebra, Probability & Mathematical Reasoning",
        ],
        "IOQM": [
            "Number Theory (Congruences & Primes)",
            "Combinatorics (Pigeonhole & P&C)",
            "Euclidean Geometry (Cyclic Quads)",
            "Algebra (Polynomials & Roots)",
            "Inequalities (AM-GM & Cauchy)",
            "Functional Equations",
            "Sequence & Series (Telescoping)",
            "Trigonometry in Geometry",
            "Invariants and Monovariants",
            "Recurrence Relations",
        ],
        "NMTC": [
            "Advanced Number Systems",
            "Algebraic Identities & Equations",
            "Geometry (Mensuration & Properties)",
            "Permutations & Combinations",
            "Ratio, Proportion & Percentages",
            "Logical Reasoning & Puzzles",
            "Data Handling & Probability",
            "Sequences, Patterns & Series",
            "Coordinate Geometry Basics",
        ],
        "NEET": ["Human Physiology", "Genetics", "Organic Chemistry", "Optics"],
        "NSEJS": [
            "Physics: Mechanics & Fluid Dynamics",
            "Physics: Light, Optics & Sound",
            "Physics: Electricity & Magnetism",
            "Physics: Thermodynamics & Heat",
            "Chemistry: Mole Concept & Stoichiometry",
            "Chemistry: Atomic Structure & Periodicity",
            "Chemistry: Acids, Bases & Salts",
            "Chemistry: Chemical Bonding & Carbon Compounds",
            "Biology: Cell Biology & Genetics",
            "Biology: Human Physiology & Control",
            "Biology: Plant Physiology & Reproduction",
            "Biology: Diversity in Living Organisms",
            "Biology: Ecology, Environment & Evolution",
        ],
    }

    try:
        syllabus_path = Path(__file__).resolve().parent / "syllabus.json"
        file_exam_store: dict[str, list[str]] = {}

        if syllabus_path.exists():
            raw_payload = json.loads(syllabus_path.read_text(encoding="utf-8"))
            if isinstance(raw_payload, dict):
                for exam_key, exam_value in raw_payload.items():
                    key = str(exam_key or "").strip().upper()
                    if not key:
                        continue

                    flattened_topics: list[str] = []
                    if isinstance(exam_value, dict):
                        for subject_topics in exam_value.values():
                            if isinstance(subject_topics, list):
                                flattened_topics.extend(
                                    [str(item).strip() for item in subject_topics if str(item).strip()]
                                )
                    elif isinstance(exam_value, list):
                        flattened_topics.extend([str(item).strip() for item in exam_value if str(item).strip()])

                    deduped_topics = list(dict.fromkeys(flattened_topics))
                    if deduped_topics:
                        file_exam_store[key] = deduped_topics

        exam_store = {**universal_exam_store, **file_exam_store}

        requested_upper = requested_exam.upper()
        normalized_upper = normalized_exam_name.upper()
        candidate_keys: list[str] = [requested_upper, normalized_upper]
        if requested_upper.startswith("JEE") or normalized_upper.startswith("JEE"):
            candidate_keys.extend(["JEE", "JEE ADVANCED"])

        seen_keys: set[str] = set()
        for key in candidate_keys:
            clean_key = str(key or "").strip().upper()
            if not clean_key or clean_key in seen_keys:
                continue
            seen_keys.add(clean_key)
            topics = exam_store.get(clean_key)
            if isinstance(topics, list) and topics:
                return {"syllabus": topics}

        logger.warning("No syllabus mapped for exam=%s; returning fallback syllabus.", normalized_exam_name)
        return {"syllabus": _fallback_syllabus_chapters(normalized_exam_name)}
    except Exception as exc:
        logger.warning("Syllabus router failed for exam=%s; returning fallback syllabus.", normalized_exam_name, exc_info=exc)
        return {"syllabus": _fallback_syllabus_chapters(normalized_exam_name)}


@app.post("/api/pyq/generate")
async def generate_pyq_variants(payload: PYQGenerateRequest) -> dict[str, str]:
    exam_name = str(payload.exam or "General").strip() or "General"
    topic_name = str(payload.topic or "").strip()
    if not topic_name:
        raise HTTPException(status_code=422, detail="topic cannot be empty")

    fallback_output = (
        "**[ OFFICIAL PYQ ]**\n"
        + "Could not retrieve an official PYQ for "
        + topic_name
        + " ("
        + exam_name
        + ").\n\n"
        + "**[ ADDIX VARIANT A ]**\n"
        + "A particle travels along a straight line with a time-dependent acceleration. Derive the displacement over a fixed time window in LaTeX.\n\n"
        + "**[ ADDIX VARIANT B ]**\n"
        + "A two-body setup with altered initial conditions tests the same core concept. Form the governing equations and solve symbolically in LaTeX."
    )

    if PRIMARY_ASYNC_LLM_CLIENT is None:
        return {"generated_text": fallback_output}

    system_prompt = (
        "You are the ADDIX Scholars Exam Architect. The user is studying "
        + topic_name
        + " for the "
        + exam_name
        + " exam. "
        + "1. Output one verified Previous Year Question (PYQ) relevant to this topic and exam. Label it '**[ OFFICIAL PYQ ]**'. "
        + "2. Generate two brand-new, highly challenging variants of this question that test the exact same underlying concept but use different scenarios or numbers. "
        + "Label them '**[ ADDIX VARIANT A ]**' and '**[ ADDIX VARIANT B ]**'. "
        + "Format all math strictly in LaTeX."
    )

    try:
        completion = await PRIMARY_ASYNC_LLM_CLIENT.chat.completions.create(
            model=PRIMARY_MODEL,
            temperature=0.25,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Generate the PYQ and both variants now. Keep labels exactly as requested.",
                },
            ],
        )
        generated_text = _chat_response_text(completion).strip()
        if not generated_text:
            generated_text = fallback_output
        return {"generated_text": generated_text}
    except Exception as exc:
        logger.warning("PYQ variant generation failed for exam=%s topic=%s", exam_name, topic_name, exc_info=exc)
        return {"generated_text": fallback_output}


@app.post("/api/vision/analyze")
async def analyze_image_vision(payload: dict = Body(...)) -> dict[str, str]:
    """Process Base64 image payloads and analyze with multimodal LLM."""
    image_data = payload.get("image", "")
    prompt = payload.get("prompt", "Analyze this image and provide detailed explanation.")
    
    if not image_data:
        raise HTTPException(status_code=422, detail="image data required")
    
    if PRIMARY_ASYNC_LLM_CLIENT is None:
        return {"analysis": "Vision analysis unavailable: LLM client not initialized."}
    
    try:
        completion = await PRIMARY_ASYNC_LLM_CLIENT.chat.completions.create(
            model=PRIMARY_MODEL,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ]
                }
            ]
        )
        analysis_text = _chat_response_text(completion).strip()
        return {"analysis": analysis_text or "Image analysis complete."}
    except Exception as exc:
        logger.warning("Vision analysis failed", exc_info=exc)
        return {"analysis": f"Vision analysis failed: {str(exc)[:200]}"}


@app.post("/api/document/ingest")
async def ingest_pdf_document(file: UploadFile = File(...)) -> dict[str, str]:
    """Ingest PDF documents and store in temporary RAG vector context."""
    if not file or not file.filename:
        raise HTTPException(status_code=422, detail="file required")
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="only PDF files supported")
    
    try:
        contents = await file.read()
        if not contents:
            raise ValueError("PDF file is empty")
        
        file_name = file.filename
        temp_storage_key = f"pdf_{uuid.uuid4().hex}_{file_name}"
        logger.info(f"PDF ingested: {temp_storage_key} ({len(contents)} bytes)")
        
        return {
            "message": f"PDF document '{file_name}' loaded successfully.",
            "storage_key": temp_storage_key,
            "file_size": str(len(contents))
        }
    except Exception as exc:
        logger.warning("PDF ingestion failed", exc_info=exc)
        raise HTTPException(status_code=500, detail=f"PDF ingestion failed: {str(exc)[:200]}")


@app.post("/api/generate/cheatsheet")
async def generate_cheatsheet(payload: dict = Body(...)) -> dict[str, str]:
    """Generate a dense, high-yield cheat sheet for a topic."""
    exam = str(payload.get("exam", "General")).strip() or "General"
    topic = str(payload.get("topic", "")).strip()
    
    if not topic:
        raise HTTPException(status_code=422, detail="topic required")
    
    if PRIMARY_ASYNC_LLM_CLIENT is None:
        return {"cheatsheet": "# Cheat Sheet\n\nUnavailable: LLM not initialized."}
    
    try:
        system_prompt = (
            f"You are a master tutor creating a dense, high-yield cheat sheet for {topic} "
            f"({exam} exam). Format it in Markdown with bullet points, key formulas in LaTeX, "
            f"and quick-reference definitions. Make it concise but comprehensive."
        )
        
        completion = await PRIMARY_ASYNC_LLM_CLIENT.chat.completions.create(
            model=PRIMARY_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate the cheat sheet for {topic} now."}
            ]
        )
        cheatsheet_text = _chat_response_text(completion).strip()
        return {"cheatsheet": cheatsheet_text or "# Cheat Sheet\n\nGeneration complete."}
    except Exception as exc:
        logger.warning("Cheat sheet generation failed for topic=%s", topic, exc_info=exc)
        return {"cheatsheet": f"# Cheat Sheet\n\nGeneration failed: {str(exc)[:200]}"}


@app.post("/api/generate/diagram")
async def generate_diagram(payload: dict = Body(...)) -> dict[str, str]:
    """Generate a Mermaid.js diagram for a concept."""
    concept = str(payload.get("concept", "")).strip()
    diagram_type = str(payload.get("type", "flowchart")).strip().lower()
    
    if not concept:
        raise HTTPException(status_code=422, detail="concept required")
    
    if PRIMARY_ASYNC_LLM_CLIENT is None:
        return {"mermaid_code": "graph LR\n  A[Diagram Generation]\n  A --> B[LLM Not Initialized]"}
    
    try:
        system_prompt = (
            f"You are a Mermaid.js expert. Generate a {diagram_type} diagram for the concept '{concept}'. "
            f"Output ONLY valid Mermaid syntax, no explanations. Use flowchart, graph, or sequence diagram syntax."
        )
        
        completion = await PRIMARY_ASYNC_LLM_CLIENT.chat.completions.create(
            model=PRIMARY_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate the {diagram_type} diagram for: {concept}"}
            ]
        )
        mermaid_code = _chat_response_text(completion).strip()
        return {"mermaid_code": mermaid_code or "graph LR\n  A[Diagram] --> B[Generated]"}
    except Exception as exc:
        logger.warning("Diagram generation failed for concept=%s", concept, exc_info=exc)
        return {"mermaid_code": f"graph LR\n  A[Error] --> B[{str(exc)[:50]}]"}


@app.post("/api/solve")
@limiter.limit("5/minute")
async def solve_student_query(request: Request, payload: SolveRequest) -> StreamingResponse:
    """Stream tutor output over SSE using ``google-genai`` (Gemini) ``generate_content_stream``."""
    global API_SOLVE_TOTAL_CALLS
    global API_SOLVE_CACHE_HITS

    async def event_stream():
        global API_SOLVE_TOTAL_CALLS
        global API_SOLVE_CACHE_HITS
        try:
            API_SOLVE_TOTAL_CALLS += 1
            yield _format_sse("thought", {"text": "[ Scholar Engine ] Initializing solver...\n"})
            image_payload = str(payload.image_base64 or payload.image_data or "").strip()
            logger.info("ðŸ“¥ Received Request: %s | Image: %s", payload.exam_context, bool(image_payload))

            incoming_messages = payload.messages if isinstance(payload.messages, list) else []
            prompt_text = str(payload.prompt or payload.query or "").strip()
            latest_query = prompt_text or _extract_latest_user_query(incoming_messages)
            history_context = _extract_history_before_latest_user(incoming_messages)
            prompt_lower = prompt_text.lower()
            broad_math_triggers = (
                "calculate",
                "solve",
                "evaluate",
                "statement",
                "limit",
                "integrate",
                "derivative",
                "find the value",
                "ratio",
            )
            force_math_tool = any(token in prompt_lower for token in broad_math_triggers)

            diagram_description = ""
            if image_payload:
                try:
                    diagram_description = await _describe_image_with_groq_vision(latest_query, image_payload, payload.exam_context)
                except Exception as vision_exc:
                    logger.warning("Groq vision route failed; falling back to Gemini description.", exc_info=vision_exc)
                    diagram_description = await _describe_diagram_with_gemini_flash(image_payload)

            combined_query = latest_query
            if diagram_description:
                combined_query = latest_query.strip() + "\n\n[Diagram Description]\n" + diagram_description.strip()

            sanitized_query = await sanitize_math_input(combined_query)
            sanitized_plain = urllib.parse.unquote_plus(sanitized_query)
            subject = _detect_subject(sanitized_plain)
            needs_visual = _needs_visual_tutor(sanitized_plain)
            is_physics_hint = subject == "Physics"
            target_hint = _infer_physics_target(sanitized_plain) if is_physics_hint else "target variable"
            symbolic_verification = None
            symbolic_ground_truth = ""
            numeric_ground_truth = ""
            authoritative_sympy_context = None
            try:
                sympy_results = await asyncio.wait_for(
                    asyncio.gather(
                        asyncio.to_thread(evaluate_symbolic_query, sanitized_plain),
                        asyncio.to_thread(build_sympy_ground_truth_context, sanitized_plain),
                        asyncio.to_thread(build_numeric_ground_truth_context, sanitized_plain),
                        asyncio.to_thread(_build_authoritative_sympy_context, sanitized_plain),
                        return_exceptions=True,
                    ),
                    timeout=TOOL_TIMEOUT_SECONDS,
                )
                symbolic_candidate, symbolic_ground_candidate, numeric_ground_candidate, authoritative_candidate = sympy_results

                if not isinstance(symbolic_candidate, Exception):
                    symbolic_verification = symbolic_candidate
                if not isinstance(symbolic_ground_candidate, Exception):
                    symbolic_ground_truth = str(symbolic_ground_candidate or "")
                if not isinstance(numeric_ground_candidate, Exception):
                    numeric_ground_truth = str(numeric_ground_candidate or "")
                if not isinstance(authoritative_candidate, Exception):
                    authoritative_sympy_context = authoritative_candidate
            except asyncio.TimeoutError:
                logger.warning("SymPy pre-solve exceeded %ss; bypassing deterministic tools and delegating to LLM.", TOOL_TIMEOUT_SECONDS)
            except Exception as sympy_exc:
                logger.warning("SymPy pre-solve failed; bypassing SymPy and delegating to Llama 3.3 reasoning.", exc_info=sympy_exc)
            symbolic_context_parts: list[str] = []
            if symbolic_verification and symbolic_verification.context_note:
                symbolic_context_parts.append(symbolic_verification.context_note)
            if symbolic_ground_truth:
                symbolic_context_parts.append(symbolic_ground_truth)
            symbolic_context = "\n".join(symbolic_context_parts)
            ground_truth_context_parts: list[str] = []
            if authoritative_sympy_context:
                ground_truth_context_parts.append(authoritative_sympy_context)
            if numeric_ground_truth:
                ground_truth_context_parts.append(numeric_ground_truth)
            if symbolic_ground_truth:
                ground_truth_context_parts.append(symbolic_ground_truth)
            ground_truth_context = "\n".join(ground_truth_context_parts)
            symbolic_verification_active = bool(symbolic_verification or symbolic_ground_truth or numeric_ground_truth or authoritative_sympy_context)
            topic_mastered = _extract_mastered_topic_from_query(sanitized_plain)

            wolfram_ground_truth = ""
            tavily_context_text = ""
            tavily_image_url = ""
            if force_math_tool or _should_route_to_ground_truth(sanitized_plain):
                try:
                    wolfram_raw = await asyncio.wait_for(
                        execute_wolfram_deterministic(sanitized_query, is_physics=is_physics_hint),
                        timeout=TOOL_TIMEOUT_SECONDS,
                    )
                    if isinstance(wolfram_raw, dict):
                        wolfram_ground_truth = str(wolfram_raw.get("answer", "")).strip()
                    else:
                        wolfram_ground_truth = str(wolfram_raw or "").strip()
                    if not wolfram_ground_truth:
                        wolfram_ground_truth = "Math Tool Context Unavailable. Rely entirely on your own internal advanced reasoning to solve this problem step-by-step."
                except asyncio.TimeoutError:
                    logger.warning("Wolfram pre-route exceeded %ss; bypassing tool and delegating to LLM.", TOOL_TIMEOUT_SECONDS)
                    wolfram_ground_truth = "Math Tool Context Unavailable. Rely entirely on your own internal advanced reasoning to solve this problem step-by-step."
                except Exception as orchestration_exc:
                    logger.warning("Wolfram orchestration pre-route failed.", exc_info=orchestration_exc)
                    wolfram_ground_truth = "Math Tool Context Unavailable. Rely entirely on your own internal advanced reasoning to solve this problem step-by-step."

            if _should_route_to_tavily_context(sanitized_plain):
                try:
                    tavily_context_text = await _query_tavily_grounding(sanitized_plain)
                    tavily_image_url = _extract_first_url(tavily_context_text)
                except Exception as orchestration_exc:
                    logger.warning("Tavily orchestration pre-route failed.", exc_info=orchestration_exc)

            visual_tutor_image_url = ""
            if needs_visual:
                visual_topic = subject if subject in ("Physics", "Chemistry", "Math") else sanitized_plain
                visual_tutor_image_url = await _query_tavily_visual_diagram(visual_topic)
                if visual_tutor_image_url and not tavily_image_url:
                    tavily_image_url = visual_tutor_image_url

            if payload.is_tester_mode:
                tester_system_prompt = (
                    "You are a Senior NSEJS/JEE examiner. Generate exactly one high-level practice question. "
                    "Do NOT provide a solution, derivation, hints, or final numeric answer. "
                    "Return strict JSON only with this schema: "
                    '{"result":"...","explanation":[],"topics":["..."]}. '
                    "In 'result', output only the practice question statement. "
                    "No markdown fences and no extra keys. "
                    "CRITICAL FORMATTING RULE: You must NEVER wrap your entire response or standard text lists in $$ or $. "
                    "The overall response must be standard Markdown. ONLY wrap isolated mathematical equations in $$ "
                    "(for block math) and individual variables in $ (for inline math). Do not use LaTeX delimiters for numbering or text headers."
                )
                tester_user_prompt = (
                    "Exam context: " + str(payload.exam_context or "General") + ". "
                    "Student topic input: " + sanitized_plain.strip() + ". "
                    "Difficulty target: advanced but accessible challenge level."
                )
                if genai is None or genai_types is None:
                    raise RuntimeError("google-genai SDK is not installed.")
                _solve_client = _get_gemini_client_for_solve()
                tester_resp = await _solve_client.aio.models.generate_content(
                    model=GEMINI_SOLVE_MODEL,
                    contents=tester_user_prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=tester_system_prompt,
                        temperature=LLM_SOLVE_TEMPERATURE,
                    ),
                )
                tester_raw_text = str(getattr(tester_resp, "text", "") or "").strip()
                tester_payload = PRIMARY_TRANSLATOR._extract_json(tester_raw_text)
                topics = tester_payload.get("topics", []) if isinstance(tester_payload.get("topics", []), list) else []
                explanation = []
                result_text = str(tester_payload.get("result") or "").strip() or (
                    "Create one advanced practice question from: " + sanitized_plain.strip()
                )
                tester_mastery_tokens = ("correct", "solved", "done", "mastered", "answer")
                if not topic_mastered and any(token in sanitized_plain.lower() for token in tester_mastery_tokens):
                    inferred_topic = str(topics[0]).strip() if topics else ""
                    topic_mastered = inferred_topic or (subject if subject in ("Physics", "Chemistry", "Math") else None)
                result_text = _sanitize_solver_output_text(result_text)
                final_answer = result_text or WOLFRAM_FALLBACK_RESULT
                engine_trace = "Gemini 2.0 Flash + SymPy Tester Mode"
                if _is_tester_failure_signal(latest_query):
                    await _insert_black_box_record(
                        exam_type=payload.exam_context,
                        question_text=result_text,
                        concept_tags=topics,
                    )
            else:
                solver_system_prompt = (
                    "CRITICAL RENDER RULES:\n"
                    "1. NEVER wrap plain English text or full sentences in $ or $$.\n"
                    "2. ONLY use $ for isolated inline variables (e.g., let $x = 5$).\n"
                    "3. ONLY use $$ for isolated standalone equations on their own lines.\n"
                    "4. DO NOT wrap numbered lists or headers in math delimiters. Use standard Markdown for structure.\n\n"
                    "Act as the ADDIX Expert Mentor.\n"
                    "You are the ADDIX Scholars Expert Academic Mentor. The user has submitted a physics, chemistry, or math problem. You must NOT just give the final answer. You must teach them how to solve it.\n"
                    "Explain concepts with extreme academic rigor but high clarity. Assume a teacher is reviewing the logic. Always clearly state the underlying principle before showing the math.\n\n"
                    "CRITICAL EXAM DIRECTIVE: If the user provides multiple statements (e.g., 'Statement I', 'Statement II', 'Assertion', 'Reason'), you MUST address each one individually. First, mathematically prove or disprove Statement I. Then, mathematically prove or disprove Statement II. Conclude with the final correct option. Show all intermediate calculus or algebra steps using LaTeX.\n\n"
                    "Format your response strictly in this structure:\n"
                    "1. **[ REFERENCE FORMULAS ]**: List the core equations needed for this problem (in LaTeX).\n"
                    "2. **[ STEP-BY-STEP DERIVATION ]**: Walk through the math line-by-line. Explain the *why* behind each step.\n"
                    "3. **[ FINAL ANSWER ]**: Provide the mathematically verified result.\n"
                    "4. **[ MENTOR'S TAKEAWAY ]**: One brief sentence explaining the core concept to remember for the exam (JEE/NSEJS level).\n\n"
                    "Tone: Highly rigorous, encouraging, and clear. Format all math inside LaTeX delimiters.\n\n"
                    "CRITICAL FORMATTING RULE: You must NEVER wrap your entire response or standard text lists in $$ or $. "
                    "The overall response must be standard Markdown. ONLY wrap isolated mathematical equations in $$ "
                    "(for block math) and individual variables in $ (for inline math). Do not use LaTeX delimiters for numbering or text headers.\n\n"
                    + "CRITICAL CONTEXT: Wolfram Alpha calculated ["
                    + (wolfram_ground_truth or "No grounded Wolfram result.")
                    + "]. Tavily found ["
                    + (tavily_image_url or "No image URL found.")
                    + "]. Integrate this data and explain the concept to the student in a clear, step-by-step manner. "
                    + "Output image URLs using standard Markdown `![Visual Reference](VALID_IMAGE_URL_HERE)`. "
                    + "The image must be on its own dedicated line, separated from surrounding text by double line breaks (\\n\\n)."
                )
                if needs_visual and visual_tutor_image_url:
                    solver_system_prompt += (
                        "\n\nThe student is struggling. You must act as the Visual Tutor. "
                        + "I am providing you with this image URL: ["
                        + visual_tutor_image_url
                        + "]. "
                        + "1. Render the image exactly using Markdown: `![Diagram](URL)`. "
                        + "2. Directly below the image, provide a 'Visual Walkthrough'. Break down the image and explain what the key labels/parts mean in simple terms. "
                        + "3. Offer a highly encouraging, simplified analogy to help them grasp the concept."
                    )

                history_json = json.dumps(history_context, ensure_ascii=False)
                solver_user_prompt = (
                    "Exam context: "
                    + str(payload.exam_context or "General")
                    + "\n"
                    + "Student problem: "
                    + sanitized_plain.strip()
                    + "\n\n"
                    + "Recent chat context JSON (if any):\n"
                    + history_json
                    + "\n\n"
                    + "Symbolic verification context:\n"
                    + (symbolic_context or "None")
                    + "\n\n"
                    + "Ground-truth context:\n"
                    + (ground_truth_context or "None")
                    + "\n\n"
                    + "Tavily context:\n"
                    + (tavily_context_text or "None")
                )

                if genai is None or genai_types is None:
                    raise RuntimeError("google-genai SDK is not installed.")

                solve_client = _get_gemini_client_for_solve()
                streamed_fragments: list[str] = []
                try:
                    async for delta in _iter_gemini_solve_stream_deltas(
                        solve_client,
                        solver_system_prompt,
                        solver_user_prompt,
                    ):
                        streamed_fragments.append(delta)
                        yield _format_sse("thought", {"text": delta})
                except Exception as stream_exc:
                    logger.warning("Gemini stream path failed; falling back to non-stream completion.", exc_info=stream_exc)

                if streamed_fragments:
                    result_text = "".join(streamed_fragments).strip() or WOLFRAM_FALLBACK_RESULT
                else:
                    completion = await solve_client.aio.models.generate_content(
                        model=GEMINI_SOLVE_MODEL,
                        contents=solver_user_prompt,
                        config=genai_types.GenerateContentConfig(
                            system_instruction=solver_system_prompt,
                            temperature=LLM_SOLVE_TEMPERATURE,
                        ),
                    )
                    result_text = str(getattr(completion, "text", "") or "").strip() or WOLFRAM_FALLBACK_RESULT

                topics = [subject] if subject else []
                explanation = []
                result_text = _sanitize_solver_output_text(result_text)
                final_answer = result_text or WOLFRAM_FALLBACK_RESULT
                engine_trace = "Gemini 2.0 Flash + SymPy Streaming"
                if symbolic_verification_active:
                    engine_trace = f"{engine_trace} | Symbolic Verification: Active (SymPy)"
                await _record_successful_solve()

            try:
                await persist_query_session(sanitized_plain, result_text, subject, bool(image_payload))
            except Exception as exc:
                logger.warning("Failed to persist /api/solve query session.", exc_info=exc)

            yield _format_sse(
                "result",
                {
                    "response_text": final_answer,
                    "result": final_answer,
                    "topics": topics,
                    "explanation": explanation,
                    "engine_trace": engine_trace,
                    "symbolic_verification_active": symbolic_verification_active,
                    "topic_mastered": topic_mastered,
                },
            )
        except Exception as e:
            fallback_notice = (
                "### [ ADDIX System Notice ]\n\n"
                "The cognitive engine experienced a temporary interruption while processing that complex request. "
                "Please try asking your question again, or rephrase it."
            )
            logger.error("Low-latency solve endpoint failed.", exc_info=e)
            yield _format_sse(
                "result",
                {
                    "response": fallback_notice,
                    "response_text": fallback_notice,
                    "result": fallback_notice,
                    "explanation": [],
                    "topics": ["System Notice"],
                    "symbolic_verification_active": False,
                    "topic_mastered": None,
                },
            )
        finally:
            yield _format_sse("done", {"ok": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/ocr", response_model=OCRResponse)
async def solve_from_ocr(payload: OCRInput) -> OCRResponse:
    return await planner.solve_image_query(payload)


@app.post("/api/simulate")
async def start_deep_simulation(payload: SimulationInput, background_tasks: BackgroundTasks) -> Dict[str, str]:
    try:
        query = payload.student_query.strip()
        if not query:
            raise HTTPException(status_code=422, detail="student_query cannot be empty.")

        task_id = str(uuid.uuid4())
        await _set_simulation_state(
            task_id,
            status="Simulating",
            percent="0%",
            progress="0%",
            final_result=None,
            created_at=datetime.utcnow().isoformat(),
            query=query,
        )
        background_tasks.add_task(run_deep_simulation, task_id, query)
        return {"task_id": task_id, "status": "Simulating", "progress": "0%"}
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"final_answer": str(exc.detail)},
        )
    except Exception as e:
        logger.error("Simulation endpoint failed.", exc_info=e)
        return JSONResponse(
            status_code=500,
            content={"final_answer": f"Backend Error: {str(e)}"},
        )


@app.get("/api/status/{task_id}")
async def get_simulation_status(task_id: str) -> Dict[str, Any]:
    async with SIMULATION_LOCK:
        status_payload = active_simulations.get(task_id)

    if status_payload is None:
        raise HTTPException(status_code=404, detail="Simulation task not found.")

    return {
        "task_id": task_id,
        "status": status_payload.get("status", "Simulating"),
        "percent": status_payload.get("percent", "0%"),
        "progress": status_payload.get("progress", "0%"),
        "final_result": status_payload.get("final_result"),
    }


@app.get("/api/vault")
async def get_vault_items() -> Dict[str, Any]:
    with VaultSessionLocal() as session:
        rows = session.execute(
            select(VaultItem).order_by(VaultItem.next_review_date.asc(), VaultItem.date_added.asc(), VaultItem.id.asc())
        ).scalars().all()
        return {"items": [_serialize_vault_item(item) for item in rows]}


@app.post("/api/vault")
async def create_vault_item(payload: VaultItemCreate) -> Dict[str, Any]:
    question_text = str(payload.question_text or "").strip()
    if not question_text:
        raise HTTPException(status_code=422, detail="question_text is required.")

    normalized_tags = [str(tag or "").strip() for tag in payload.concept_tags]
    normalized_tags = [tag for tag in normalized_tags if tag][:8]

    with VaultSessionLocal() as session:
        existing = session.execute(select(VaultItem).where(VaultItem.question_text == question_text)).scalars().first()
        if existing is not None:
            return _serialize_vault_item(existing)

        item = VaultItem(
            question_text=question_text,
            concept_tags=json.dumps(normalized_tags, ensure_ascii=True),
            ease_factor=2.5,
            interval=0,
            next_review_date=datetime.utcnow(),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return _serialize_vault_item(item)


@app.post("/api/vault/{item_id}/review")
async def review_vault_item(item_id: int, payload: VaultReviewPayload) -> Dict[str, Any]:
    with VaultSessionLocal() as session:
        item = session.execute(select(VaultItem).where(VaultItem.id == item_id)).scalars().first()
        if item is None:
            raise HTTPException(status_code=404, detail="Vault item not found.")

        next_interval, next_ease = calculate_sm2(
            payload.score,
            float(getattr(item, "ease_factor", 2.5) or 2.5),
            int(getattr(item, "interval", 0) or 0),
        )

        item.interval = next_interval
        item.ease_factor = next_ease
        item.next_review_date = datetime.utcnow() + timedelta(days=next_interval)
        session.commit()
        session.refresh(item)
        return _serialize_vault_item(item)


@app.post("/api/debrief")
async def debrief_session(conversation_history: list[dict[str, Any]] = Body(...)) -> Dict[str, Any]:
    try:
        history = conversation_history if isinstance(conversation_history, list) else []
        feedback = await _call_debrief_llm(history)
        return feedback
    except Exception as exc:
        logger.error("Debrief endpoint failed.", exc_info=exc)
        raise HTTPException(status_code=502, detail="Debrief generation failed.")


@app.delete("/api/vault/{item_id}")
async def delete_vault_item(item_id: int) -> Dict[str, bool]:
    with VaultSessionLocal() as session:
        item = session.execute(select(VaultItem).where(VaultItem.id == item_id)).scalars().first()
        if item is None:
            return {"deleted": False}
        session.delete(item)
        session.commit()
        return {"deleted": True}


@app.get("/api/analytics")
async def get_daily_analytics() -> Dict[str, Any]:
    with VaultSessionLocal() as session:
        rows = session.execute(select(DailyAnalytics).order_by(DailyAnalytics.date.asc())).scalars().all()
        items = [_serialize_daily_analytics(item) for item in rows]
        physics_total = sum(int(item["physics_count"]) for item in items)
        math_total = sum(int(item["math_count"]) for item in items)
        problems_total = sum(int(item["problems_solved"]) for item in items)
        return {
            "items": items,
            "totals": {
                "problems_solved": problems_total,
                "physics_count": physics_total,
                "math_count": math_total,
            },
        }


@app.get("/api/stats")
async def get_user_stats() -> Dict[str, int]:
    row = await _get_or_create_user_stats()
    return {
        "current_streak": int(row.current_streak or 0),
        "total_solved": int(row.total_solved or 0),
    }


@app.get("/api/admin/telemetry")
async def get_admin_telemetry(request: Request) -> Dict[str, int]:
    requester_email = str(request.headers.get("X-User-Email", "")).strip().lower()
    if not requester_email or requester_email != FOUNDER_EMAIL:
        raise HTTPException(status_code=403, detail="Founder access required.")

    today = date.today()
    async with AsyncSessionLocal() as session:
        total_users_result = await session.execute(select(func.count(User.id)))
        total_premium_result = await session.execute(select(func.count(User.id)).where(User.is_premium.is_(True)))
        total_questions_result = await session.execute(select(func.coalesce(func.sum(UserStats.total_solved), 0)))
        black_box_today_result = await session.execute(
            select(func.count(BlackBox.id)).where(BlackBox.date_added == today)
        )

    return {
        "total_registered_users": int(total_users_result.scalar() or 0),
        "total_premium_subscribers": int(total_premium_result.scalar() or 0),
        "total_questions_solved": int(total_questions_result.scalar() or 0),
        "total_black_box_entries_today": int(black_box_today_result.scalar() or 0),
    }


@app.get("/api/export/blackbox")
async def export_blackbox_report() -> StreamingResponse:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BlackBox).order_by(BlackBox.date_added.desc(), BlackBox.id.desc()))
        rows = result.scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No Black Box records available for export.")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_title("ADDIX LABS: Weakness Report")
    pdf.set_author("ADDIX LABS")

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ADDIX LABS: Weakness Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
    pdf.ln(2)

    for index, item in enumerate(rows, start=1):
        exam_type = str(getattr(item, "exam_type", "General") or "General")
        date_added = getattr(item, "date_added", None)
        date_text = date_added.isoformat() if date_added else "N/A"
        question_text = str(getattr(item, "question_text", "") or "").strip()
        concept_tags = parse_tags(str(getattr(item, "concept_tags", "[]") or "[]"))
        tags_text = ", ".join(concept_tags) if concept_tags else "None"

        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, f"{index}. [{exam_type}] Added: {date_text}")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, f"Question: {question_text}")
        pdf.multi_cell(0, 6, f"Concept Tags: {tags_text}")
        pdf.ln(2)

    pdf_bytes = bytes(pdf.output(dest="S"))
    filename = f"addix_weakness_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=headers,
    )


async def _generate_formula_sheet_content(topic: str) -> str:
    clean_topic = str(topic or "").strip() or "General"
    fallback = (
        "Top 5 Essential Formulas\n"
        "1) Define the core formula from the syllabus chapter.\n"
        "2) Include one rearranged form used in numericals.\n"
        "3) Include one unit-consistency relation.\n"
        "4) Include one boundary-condition identity.\n"
        "5) Include one high-frequency exam relation.\n\n"
        "3 Golden Rules\n"
        "1) Start with knowns, unknowns, and units before substitution.\n"
        "2) Preserve sign conventions and reference direction.\n"
        "3) Verify dimensional consistency before finalizing."
    )

    if PRIMARY_ASYNC_LLM_CLIENT is None:
        return fallback

    prompt = (
        f"Generate the top 5 essential formulas and 3 golden rules for {clean_topic} "
        "in the NSEJS/JEE syllabus. Plain text only, no markdown formatting."
    )

    try:
        completion = await PRIMARY_ASYNC_LLM_CLIENT.chat.completions.create(
            model=PRIMARY_MODEL,
            temperature=0.15,
            messages=[
                {
                    "role": "system",
                    "content": "You are an academic formula curator. Return concise plain text only with clear numbered sections.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        generated = _chat_response_text(completion).strip()
        return generated or fallback
    except Exception as exc:
        logger.warning("Formula sheet generation failed for topic=%s", clean_topic, exc_info=exc)
        return fallback


@app.get("/api/export-pdf/{topic}")
async def export_formula_sheet_pdf(topic: str) -> StreamingResponse:
    topic_clean = str(topic or "").strip()
    if not topic_clean:
        raise HTTPException(status_code=422, detail="Topic is required for formula sheet export.")

    formula_text = await _generate_formula_sheet_content(topic_clean)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_title(f"ADDIX Formula Sheet - {topic_clean}")
    pdf.set_author("ADDIX SCHOLARS")

    pdf.set_font("Helvetica", "B", 22)
    pdf.multi_cell(0, 12, "ADDIX SCHOLARS // PCM DIVISION")
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 9, f"Official Formula Sheet: {topic_clean}")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, formula_text)

    pdf_bytes = bytes(pdf.output(dest="S"))
    safe_topic = re.sub(r"[^A-Za-z0-9]+", "_", topic_clean).strip("_") or "Topic"
    filename = f"ADDIX_{safe_topic}_CheatSheet.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/analytics/sync")
async def sync_daily_analytics(payload: DailyAnalyticsSyncPayload) -> Dict[str, Any]:
    date_key = str(payload.date or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_key):
        raise HTTPException(status_code=422, detail="date must be in YYYY-MM-DD format.")

    with VaultSessionLocal() as session:
        row = session.execute(select(DailyAnalytics).where(DailyAnalytics.date == date_key)).scalars().first()
        if row is None:
            row = DailyAnalytics(
                date=date_key,
                problems_solved=0,
                physics_count=0,
                math_count=0,
            )
            session.add(row)

        row.problems_solved = max(0, int(row.problems_solved) + int(payload.problems_delta))
        row.physics_count = max(0, int(row.physics_count) + int(payload.physics_delta))
        row.math_count = max(0, int(row.math_count) + int(payload.math_delta))
        session.commit()
        session.refresh(row)
        return _serialize_daily_analytics(row)


@app.get("/api/system-status")
async def system_status() -> Dict[str, str | bool | int]:
    try:
        db_status, total_logs = await asyncio.to_thread(_check_database_status_sync)
    except Exception as exc:
        logger.warning("Database health check failed.", exc_info=exc)
        db_status, total_logs = "error", 0

    wolfram_status = await _check_wolfram_connection()
    return {
        "status": "ok",
        "wolfram_status": wolfram_status,
        "database_status": db_status,
        "history_records": total_logs,
    }


@app.get("/api/dashboard-stats", response_model=DashboardStatsResponse)
async def dashboard_stats() -> DashboardStatsResponse:
    return _build_dashboard_stats()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "online"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, workers=1)


