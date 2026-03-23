"""
Parser layer: Playwright JSON reporter output → ParsedFailure[]

Reads test-results/results.json and extracts failed results as normalized
ParsedFailure objects. No AI logic. No file I/O beyond reading the input.

Assumptions about the current Playwright JSON shape:
  - Top-level "suites" list, one entry per test file.
  - Each suite has "specs" (flat tests) — no nested describe-block suites yet.
  - Each spec has "tests" (one per browser project) with "results" (one per retry).
  - Failed results have result["error"]["message"] and result["error"]["stack"].
  - error_type is inferred from message text; it is not a Playwright-native field.
  - To add describe-block support later, extend _extract_specs() to recurse into
    suite["suites"].
"""

import dataclasses
import json
import re
import sys

from analyzer.models import ErrorType, ParsedFailure

_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def _classify_error(message: str) -> ErrorType:
    """
    Infer error type from Playwright error message text.
    Order matters: more specific patterns are checked first.
    """
    msg = message.lower()

    if any(kw in msg for kw in ("net::", "err_connection", "econnrefused", "enotfound")):
        return "network"

    # assertion: Playwright always formats as "expect(...).someMethod() failed"
    if "expect(" in msg:
        return "assertion"

    # element_not_found: action-level timeout waiting for a locator to become interactable
    if "waiting for locator" in msg:
        return "element_not_found"

    if "timeout" in msg:
        return "timeout"

    return "unknown"


def _extract_specs(suite: dict) -> list[dict]:
    """
    Return all specs from a suite.
    Extend here to recurse into suite["suites"] for describe-block support.
    """
    return suite.get("specs", [])


def _build_failure(result: dict, spec: dict, browser: str) -> ParsedFailure:
    error = result.get("error", {})
    message = _strip_ansi(error.get("message", ""))
    stack = _strip_ansi(error.get("stack", ""))

    return ParsedFailure(
        test_id=spec["id"],
        test_title=spec["title"],
        file=spec.get("file", ""),
        error_type=_classify_error(message),
        error_message=message,
        stack_trace=stack,
        duration_ms=result.get("duration", 0),
        browser=browser,
        timestamp=result.get("startTime", ""),
    )


def _parse_suite(suite: dict) -> list[ParsedFailure]:
    failures = []
    for spec in _extract_specs(suite):
        if spec.get("ok", True):
            continue
        for test in spec.get("tests", []):
            browser = test.get("projectName", "unknown")
            for result in test.get("results", []):
                if result.get("status") == "failed":
                    failures.append(_build_failure(result, spec, browser))
    return failures


def parse(results_path: str) -> list[ParsedFailure]:
    with open(results_path) as f:
        data = json.load(f)

    failures = []
    for suite in data.get("suites", []):
        failures.extend(_parse_suite(suite))
    return failures


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "test-results/results.json"
    failures = parse(path)
    print(json.dumps([dataclasses.asdict(f) for f in failures], indent=2))


if __name__ == "__main__":
    main()
