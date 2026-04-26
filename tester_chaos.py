# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
"""
ADDIX Scholars — Tester Mode QA Protocol
=========================================
Stress-tests the backend `/api/solve` endpoint specifically
for Tester Mode (engine_mode: "tester") responses.

Assertions:
  1. Response must return exactly 3 questions.
  2. Every question must have options A, B, C, and D.
  3. Color-coded [PASS] / [FAIL] terminal report.

Usage:
  python tester_chaos.py
"""

import json
import time
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────
ENDPOINT = "http://localhost:8000/api/solve"
PAYLOAD = {
    "query": "Thermodynamics Laws",
    "engine_mode": "tester"
}
TIMEOUT = 15  # seconds
REQUIRED_QUESTION_COUNT = 3
REQUIRED_OPTION_LETTERS = {"A", "B", "C", "D"}

# ── ANSI Color Codes ──────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def tag_pass(): return f"{GREEN}{BOLD}[PASS]{RESET}"
def tag_fail(): return f"{RED}{BOLD}[FAIL]{RESET}"
def tag_warn(): return f"{YELLOW}{BOLD}[WARN]{RESET}"

# ── Helpers ───────────────────────────────────────────────────────────────────
def post_json(url: str, payload: dict, timeout: int = 15):
    """Send a JSON POST request and return (status_code, response_body)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, body
    except urllib.error.URLError as e:
        return None, str(e.reason)


def extract_questions(body: str):
    """
    Attempts to extract a list of question objects from the response body.
    Tries JSON parse first; falls back to scanning for bracket arrays.
    Returns list[dict] or None on failure.
    """
    # Try direct JSON parse
    try:
        parsed = json.loads(body)
        # The API may return {"questions": [...]} or a direct list
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("questions", "data", "result", "response"):
                if isinstance(parsed.get(key), list):
                    return parsed[key]
    except json.JSONDecodeError:
        pass

    # Try finding a JSON array inside an SSE or plain-text stream
    try:
        match_start = body.find("[{")
        match_end = body.rfind("}]")
        if match_start != -1 and match_end != -1:
            candidate = body[match_start:match_end + 2]
            return json.loads(candidate)
    except Exception:
        pass

    return None


# ── Test Runners ──────────────────────────────────────────────────────────────
results = []

def run_test(name: str, test_fn):
    """Execute a test, record result, print status."""
    print(f"\n  Running: {CYAN}{name}{RESET}")
    start = time.time()
    try:
        passed, detail = test_fn()
        elapsed = (time.time() - start) * 1000
        status = tag_pass() if passed else tag_fail()
        print(f"  {status} ({elapsed:.0f} ms)")
        print(f"    {detail}")
        results.append((name, passed))
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        print(f"  {tag_fail()} ({elapsed:.0f} ms)")
        print(f"    Exception: {exc}")
        results.append((name, False))


# ── Test 1: Endpoint Reachability ─────────────────────────────────────────────
def test_reachability():
    status, body = post_json(ENDPOINT, PAYLOAD, TIMEOUT)
    if status is None:
        return False, f"Connection failed — {body}"
    if status == 200:
        return True, f"status={status} — endpoint reachable"
    return False, f"status={status} — unexpected response code"


# ── Test 2: Question Count ────────────────────────────────────────────────────
def test_question_count():
    status, body = post_json(ENDPOINT, PAYLOAD, TIMEOUT)
    if status is None:
        return False, f"Connection failed — {body}"

    questions = extract_questions(body)
    if questions is None:
        return False, f"Could not parse questions from response. Raw (truncated): {body[:300]}"

    count = len(questions)
    if count == REQUIRED_QUESTION_COUNT:
        return True, f"Returned exactly {count} question(s) ✓"
    return False, f"Expected {REQUIRED_QUESTION_COUNT} questions, got {count}."


# ── Test 3: Options Completeness ──────────────────────────────────────────────
def test_options_completeness():
    status, body = post_json(ENDPOINT, PAYLOAD, TIMEOUT)
    if status is None:
        return False, f"Connection failed — {body}"

    questions = extract_questions(body)
    if questions is None:
        return False, f"Could not parse questions. Raw (truncated): {body[:300]}"

    failures = []
    for i, q in enumerate(questions):
        options = q.get("options", {})
        if isinstance(options, dict):
            present = set(options.keys())
        elif isinstance(options, list):
            # Handle list format: [{"label": "A", "text": "..."}, ...]
            present = {o.get("label", "").upper() for o in options}
        else:
            present = set()

        missing = REQUIRED_OPTION_LETTERS - present
        if missing:
            failures.append(f"Q{i+1} missing options: {sorted(missing)}")

    if not failures:
        return True, f"All {len(questions)} question(s) have options A, B, C, D ✓"
    return False, "Option completeness failures — " + "; ".join(failures)


# ── Test 4: Answer Key Presence ───────────────────────────────────────────────
def test_answer_key_presence():
    status, body = post_json(ENDPOINT, PAYLOAD, TIMEOUT)
    if status is None:
        return False, f"Connection failed — {body}"

    questions = extract_questions(body)
    if questions is None:
        return False, f"Could not parse questions."

    missing_answers = []
    for i, q in enumerate(questions):
        answer = q.get("answer") or q.get("correct") or q.get("correct_answer")
        if not answer:
            missing_answers.append(f"Q{i+1}")

    if not missing_answers:
        return True, f"All {len(questions)} question(s) include an answer key ✓"
    return False, f"Missing answer key in: {', '.join(missing_answers)}"


# ── Main Report ───────────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}{CYAN}-------------------------------------------------{RESET}")
    print(f"{BOLD}{CYAN}  ADDIX SCHOLARS -- TESTER MODE QA PROTOCOL{RESET}")
    print(f"{BOLD}{CYAN}-------------------------------------------------{RESET}")
    print(f"  Target  : {ENDPOINT}")
    print(f"  Payload : {json.dumps(PAYLOAD)}")
    print(f"  Timeout : {TIMEOUT}s")

    run_test("1. Endpoint Reachability",    test_reachability)
    run_test("2. Question Count (= 3)",     test_question_count)
    run_test("3. Options Completeness",     test_options_completeness)
    run_test("4. Answer Key Presence",      test_answer_key_presence)

    # ── Summary ───────────────────────────────────────────────────────────────
    total  = len(results)
    passed = sum(1 for _, ok in results if ok)
    failed = total - passed

    print(f"\n{BOLD}{'-' * 49}{RESET}")
    if failed == 0:
        print(f"  {GREEN}{BOLD}[OK] ALL {total} TESTS PASSED -- TESTER ENGINE NOMINAL{RESET}")
    else:
        print(f"  {RED}{BOLD}[!!] {failed}/{total} TESTS FAILED -- REVIEW ABOVE ERRORS{RESET}")
    print(f"{BOLD}{'-' * 49}{RESET}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
