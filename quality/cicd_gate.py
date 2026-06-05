"""
CI/CD Gate — turns the unified quality report into an automated merge decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from quality.metrics import QualityReport


@dataclass
class GateThresholds:
    min_mutation_score: float = 60.0       # block merge below this
    warn_mutation_score: float = 75.0      # warn below this
    max_flakiness: float = 2.0
    max_hallucination_rate: float = 5.0
    min_success_rate: float = 98.0
    critical_module: bool = False          # critical code demands >= 80

    def effective_min(self) -> float:
        return 80.0 if self.critical_module else self.min_mutation_score


@dataclass
class GateDecision:
    status: str            # PASS | WARN | FAIL
    passed: bool
    reasons: List[str] = field(default_factory=list)
    badge: str = ""

    def to_dict(self) -> dict:
        return {"status": self.status, "passed": self.passed, "reasons": self.reasons, "badge": self.badge}


class CICDGate:
    def __init__(self, thresholds: GateThresholds | None = None) -> None:
        self.t = thresholds or GateThresholds()

    def evaluate(self, report: QualityReport) -> GateDecision:
        reasons: List[str] = []
        score = report.mutation.mutation_score
        min_score = self.t.effective_min()

        hard_fail = False
        if score < min_score:
            reasons.append(f"Mutation score {score}% < required {min_score}%.")
            hard_fail = True
        if report.execution.success_rate < self.t.min_success_rate:
            reasons.append(
                f"Execution success rate {report.execution.success_rate}% < {self.t.min_success_rate}%."
            )
            hard_fail = True

        warn = False
        if not hard_fail and score < self.t.warn_mutation_score:
            reasons.append(f"Mutation score {score}% below target {self.t.warn_mutation_score}% (warning).")
            warn = True
        if report.test_quality.flakiness_rate > self.t.max_flakiness:
            reasons.append(f"Flakiness {report.test_quality.flakiness_rate}% > {self.t.max_flakiness}%.")
            warn = True
        if report.ai.hallucination_rate > self.t.max_hallucination_rate:
            reasons.append(
                f"AI hallucination rate {report.ai.hallucination_rate}% > {self.t.max_hallucination_rate}%."
            )
            warn = True

        if hard_fail:
            return GateDecision("FAIL", False, reasons, badge="❌ CI/CD GATE: FAILED — merge blocked")
        if warn:
            return GateDecision("WARN", True, reasons, badge="⚠️ CI/CD GATE: PASSED WITH WARNINGS")
        return GateDecision(
            "PASS", True, reasons or ["All quality thresholds met."],
            badge="✅ CI/CD GATE: PASSED — ready for merge",
        )
