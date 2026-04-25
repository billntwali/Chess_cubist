from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    duration_ms: float
    data: dict = field(default_factory=dict)
