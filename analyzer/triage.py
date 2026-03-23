"""
AI analysis layer: ParsedFailure → AnalysisResult

Loads prompt templates, calls the AI client, and maps the structured
JSON response back to an AnalysisResult. No parsing logic. No reporting.
"""

import dataclasses
import json
import sys
from pathlib import Path
from string import Template

from analyzer import ai_client
from analyzer.models import AnalysisResult, ParsedFailure

_PROMPTS = Path(__file__).parent.parent / "prompts"


def _load(filename: str) -> str:
    return (_PROMPTS / filename).read_text()


def _parse_response(text: str) -> dict:
    """Extract JSON from the model response, tolerating markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def analyze(failure: ParsedFailure) -> AnalysisResult:
    system = _load("triage_system.md")
    user = Template(_load("triage_user.md")).substitute(
        test_title=failure.test_title,
        file=failure.file,
        error_type=failure.error_type,
        browser=failure.browser,
        duration_ms=failure.duration_ms,
        error_message=failure.error_message,
        stack_trace=failure.stack_trace,
    )

    raw = ai_client.complete(system, user)
    data = _parse_response(raw)

    return AnalysisResult(
        failure=failure,
        probable_cause=data["probable_cause"],
        severity=data["severity"],
        business_impact=data["business_impact"],
        suggested_steps=data.get("suggested_steps", []),
        confidence=float(data["confidence"]),
    )


def main() -> None:
    from analyzer.parser import parse

    results_path = sys.argv[1] if len(sys.argv) > 1 else "test-results/results.json"
    failures = parse(results_path)

    if not failures:
        print("[]")
        return

    result = analyze(failures[0])
    print(json.dumps(dataclasses.asdict(result), indent=2))


if __name__ == "__main__":
    main()
