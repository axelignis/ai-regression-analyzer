from dataclasses import dataclass, field
from typing import Literal

ErrorType = Literal[
    "assertion",
    "element_not_found",
    "timeout",
    "network",
    "unknown",
]

Severity = Literal["critical", "high", "medium", "low"]


@dataclass
class ParsedFailure:
    test_id: str
    test_title: str
    file: str
    error_type: ErrorType
    error_message: str
    stack_trace: str
    duration_ms: int
    browser: str
    timestamp: str


@dataclass
class AnalysisResult:
    failure: ParsedFailure
    probable_cause: str
    severity: Severity
    business_impact: str
    confidence: float  # 0.0 – 1.0
    suggested_steps: list[str] = field(default_factory=list)
