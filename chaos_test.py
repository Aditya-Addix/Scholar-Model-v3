from __future__ import annotations

import concurrent.futures
import json
import time
from dataclasses import dataclass
from typing import Any

import requests

BASE_URL ="https://scholar-model-v3.onrender.com"
SOLVE_URL = f"{BASE_URL}/api/solve"
TIMEOUT_SECONDS = 45
TINY_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Zf9kAAAAASUVORK5CYII="


class ConsoleColor:
    RESET = "\033[0m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str
    elapsed_ms: int


def _build_payload(prompt: str, image_base64: str | None = None) -> dict[str, Any]:
    return {
        "messages": [{"role": "user", "content": prompt}],
        "prompt": prompt,
        "query": prompt,
        "socratic_mode": False,
        "is_tester_mode": False,
        "exam_context": "JEE Advanced",
        "image_base64": image_base64,
    }


def _post_solve(payload: dict[str, Any]) -> tuple[int, bool, str, dict[str, Any] | None]:
    response = requests.post(
        SOLVE_URL,
        json=payload,
        timeout=TIMEOUT_SECONDS,
        stream=True,
        headers={"Accept": "text/event-stream"},
    )
    status_code = response.status_code
    content_type = str(response.headers.get("content-type", "")).lower()
    if "application/json" in content_type:
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:400]}
        return status_code, False, "json-response", data

    saw_result_event = False
    chunks: list[str] = []
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = str(raw_line)
        if line.startswith("event: result"):
            saw_result_event = True
        if line.startswith("data:"):
            chunks.append(line[:220])
        if saw_result_event and len(chunks) >= 2:
            break
    return status_code, saw_result_event, "sse-response", {"preview": chunks[:4]}


def _format_result(result: TestResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    color = ConsoleColor.GREEN if result.passed else ConsoleColor.RED
    return (
        f"{color}{status}{ConsoleColor.RESET} "
        f"{ConsoleColor.BOLD}{result.name}{ConsoleColor.RESET} "
        f"({result.elapsed_ms} ms)\n    {result.detail}"
    )


def _run_test(name: str, test_fn: Any) -> TestResult:
    started = time.perf_counter()
    try:
        passed, detail = test_fn()
    except Exception as exc:
        passed = False
        detail = f"Unhandled exception: {exc}"
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return TestResult(name=name, passed=passed, detail=detail, elapsed_ms=elapsed_ms)


def test_text_engine() -> tuple[bool, str]:
    status, saw_result, mode, payload = _post_solve(_build_payload("What is 2+2?"))
    passed = status == 200 and saw_result and mode == "sse-response"
    return passed, f"status={status}, mode={mode}, result_event={saw_result}, payload={payload}"


def test_vision_engine() -> tuple[bool, str]:
    status, saw_result, mode, payload = _post_solve(
        _build_payload("Read this tiny image and confirm processing.", image_base64=TINY_PNG_BASE64)
    )
    passed = status == 200 and saw_result and mode == "sse-response"
    return passed, f"status={status}, mode={mode}, result_event={saw_result}, payload={payload}"


def test_bad_image_handling() -> tuple[bool, str]:
    status, saw_result, mode, payload = _post_solve(
        _build_payload("This image is intentionally corrupted.", image_base64="%%%INVALID%%%BASE64%%%")
    )
    is_error_json = mode == "json-response" and isinstance(payload, dict) and bool(payload.get("error"))
    passed = status in (400, 500) and is_error_json and not saw_result
    return passed, f"status={status}, mode={mode}, result_event={saw_result}, payload={payload}"


def _single_load_request(index: int) -> tuple[bool, str]:
    status, saw_result, mode, _ = _post_solve(_build_payload(f"Quick load test #{index}: what is 10+{index}?"))
    ok = status == 200 and saw_result and mode == "sse-response"
    return ok, f"req#{index}: status={status}, mode={mode}, result_event={saw_result}"


def test_rate_limit_load() -> tuple[bool, str]:
    workers = 5
    results: list[tuple[bool, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_single_load_request, index) for index in range(workers)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    success_count = sum(1 for ok, _ in results if ok)
    passed = success_count >= 1
    return passed, f"successful={success_count}/{workers}; details={results}"


def main() -> None:
    print(f"{ConsoleColor.CYAN}{ConsoleColor.BOLD}ADDIX SCHOLARS CHAOS TEST SUITE{ConsoleColor.RESET}")
    print(f"Target: {SOLVE_URL}\n")

    tests = [
        ("Test 1 (Text Engine)", test_text_engine),
        ("Test 2 (Vision Engine)", test_vision_engine),
        ("Test 3 (Bad Image Error Handling)", test_bad_image_handling),
        ("Test 4 (Rate Limit / Concurrent Load)", test_rate_limit_load),
    ]
    results = [_run_test(name, fn) for name, fn in tests]
    for result in results:
        print(_format_result(result))

    passed_total = sum(1 for item in results if item.passed)
    print("\n" + "-" * 72)
    if passed_total == len(results):
        print(f"{ConsoleColor.GREEN}{ConsoleColor.BOLD}SYSTEMS NOMINAL: {passed_total}/{len(results)} tests passed.{ConsoleColor.RESET}")
    else:
        print(f"{ConsoleColor.YELLOW}{ConsoleColor.BOLD}DEGRADED: {passed_total}/{len(results)} tests passed.{ConsoleColor.RESET}")


if __name__ == "__main__":
    main()
