"""
ISO 26262 ASIL Safety-Compliance Engine.

Mutation testing is recognised by ISO 26262-6 (Table 12) as a method for
evaluating the completeness of test cases for higher ASILs. This engine turns a
mutation run into a *certification readiness verdict*:

  * weights each mutant by how safety-relevant its category is,
  * computes a Safety Confidence Index (safety-weighted mutation coverage),
  * determines the highest ASIL the suite currently substantiates,
  * lists the safety-critical blind spots blocking the target ASIL.

The thresholds are a defensible, clearly-labelled heuristic — not a certification
authority — and are surfaced in the briefing so judges see the reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class ASIL(str, Enum):
    QM = "QM"   # Quality Management (no safety requirement)
    A = "A"
    B = "B"
    C = "C"
    D = "D"     # most stringent


# Highest ASIL substantiated requires this safety-weighted coverage (%).
# Aligned with the intent of ISO 26262-6 rigour rising with ASIL.
_ASIL_THRESHOLDS = [(ASIL.D, 95.0), (ASIL.C, 90.0), (ASIL.B, 80.0), (ASIL.A, 70.0), (ASIL.QM, 0.0)]
_ASIL_ORDER = {ASIL.QM: 0, ASIL.A: 1, ASIL.B: 2, ASIL.C: 3, ASIL.D: 4}

# How safety-relevant is each mutation category? (0 = cosmetic, 1 = critical)
_CATEGORY_SAFETY_WEIGHT = {
    "boundary": 0.95,
    "relational operator replacement": 0.90,
    "logical operator replacement": 0.90,
    "negation": 0.85,
    "arithmetic operator replacement": 0.85,
    "return value change": 0.80,
    "constant replacement": 0.70,
    "value replacement": 0.70,
    "statement deletion": 0.65,
    "control flow": 0.85,
    "equivalent": 0.05,
}
_DEFAULT_SAFETY_WEIGHT = 0.70

# Root-cause -> safety severity for surviving (undetected) mutants.
_ROOTCAUSE_SEVERITY = {
    "Exception Gap": "Critical",
    "Boundary Gap": "High",
    "Missing Assertion": "High",
    "State Validation Gap": "Medium",
    "Weak Assertion": "Medium",
    "Dead Code": "Low",
    "Uncategorized": "Medium",
}


@dataclass
class SafetyBlindSpot:
    method: str
    mutant_id: Any
    category: str
    root_cause: str
    severity: str
    safety_weight: float
    rationale: str
    suggested_focus: str

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class SafetyAssessment:
    target_asil: str
    achieved_asil: str
    certified: bool
    safety_confidence_index: float          # 0-100, safety-weighted coverage
    raw_mutation_score: float
    blind_spots: List[SafetyBlindSpot] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    per_method: Dict[str, float] = field(default_factory=dict)   # method -> SCI
    verdict: str = ""
    iso_clause: str = "ISO 26262-6:2018, Table 12 (mutation analysis)"

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d["blind_spots"] = [b.to_dict() for b in self.blind_spots]
        return d


def category_weight(category: str) -> float:
    return _CATEGORY_SAFETY_WEIGHT.get((category or "").strip().lower(), _DEFAULT_SAFETY_WEIGHT)


class SafetyComplianceEngine:
    def __init__(self, target_asil: ASIL = ASIL.D) -> None:
        self.target_asil = target_asil

    # ------------------------------------------------------------------ #
    def assess(self, report: Any, promoted_to_killed: Optional[set] = None) -> SafetyAssessment:
        """
        report = engine.pipeline_engine.PipelineReport

        promoted_to_killed: optional set of (method, mutant_id) survivor keys that
        should be counted as KILLED — used to project the safety state *after* the
        AI-generated tests are applied.
        """
        promoted = promoted_to_killed or set()
        results = report.execution_results
        # category lookup for every executed mutant
        cat_by_key: Dict[Any, str] = {}
        if report.stage2:
            for m in report.stage2.selected:
                cat_by_key[(m.method, m.mutant_id)] = m.category

        weighted_total = 0.0
        weighted_killed = 0.0
        per_method_tot: Dict[str, float] = {}
        per_method_kill: Dict[str, float] = {}

        for r in results:
            status = (r.status or "").lower()
            if status == "equivalent":
                continue  # equivalent mutants excluded, like mutation score
            key = (r.method, r.mutant_id)
            effective_killed = status == "killed" or key in promoted
            w = category_weight(cat_by_key.get(key, ""))
            weighted_total += w
            per_method_tot[r.method] = per_method_tot.get(r.method, 0.0) + w
            if effective_killed:
                weighted_killed += w
                per_method_kill[r.method] = per_method_kill.get(r.method, 0.0) + w

        sci = round(100.0 * weighted_killed / weighted_total, 1) if weighted_total else 0.0
        per_method = {
            m: round(100.0 * per_method_kill.get(m, 0.0) / tot, 1) if tot else 0.0
            for m, tot in per_method_tot.items()
        }

        achieved = self._highest_asil(sci)
        certified = _ASIL_ORDER[achieved] >= _ASIL_ORDER[self.target_asil]

        blind_spots: List[SafetyBlindSpot] = []
        if report.stage4:
            for s in report.stage4.survivors:
                if (s.method, s.mutant_id) in promoted:
                    continue  # this blind spot is now closed by an AI test
                sev = _ROOTCAUSE_SEVERITY.get(s.root_cause, "Medium")
                blind_spots.append(
                    SafetyBlindSpot(
                        method=s.method,
                        mutant_id=s.mutant_id,
                        category=s.category,
                        root_cause=s.root_cause,
                        severity=sev,
                        safety_weight=round(category_weight(s.category), 2),
                        rationale=s.rationale,
                        suggested_focus=s.suggested_focus,
                    )
                )
        blind_spots.sort(key=lambda b: (-_sev_rank(b.severity), -b.safety_weight))
        crit = sum(1 for b in blind_spots if b.severity == "Critical")
        high = sum(1 for b in blind_spots if b.severity == "High")

        verdict = self._verdict(achieved, certified, crit, high)
        raw_score = report.stage4.mutation_score if report.stage4 else 0.0

        return SafetyAssessment(
            target_asil=self.target_asil.value,
            achieved_asil=achieved.value,
            certified=certified,
            safety_confidence_index=sci,
            raw_mutation_score=raw_score,
            blind_spots=blind_spots,
            critical_count=crit,
            high_count=high,
            per_method=per_method,
            verdict=verdict,
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _highest_asil(sci: float) -> ASIL:
        for asil, thr in _ASIL_THRESHOLDS:
            if sci >= thr:
                return asil
        return ASIL.QM

    def _verdict(self, achieved: ASIL, certified: bool, crit: int, high: int) -> str:
        if certified:
            return (
                f"READY — test suite substantiates ASIL {achieved.value}. "
                f"Mutation analysis evidence satisfies the {self.target_asil.value} target."
            )
        gap = []
        if crit:
            gap.append(f"{crit} critical")
        if high:
            gap.append(f"{high} high-severity")
        gap_txt = " and ".join(gap) if gap else "residual"
        return (
            f"NOT READY for ASIL {self.target_asil.value} — currently substantiates "
            f"ASIL {achieved.value}. {gap_txt} safety blind spot(s) must be closed."
        )


def _sev_rank(sev: str) -> int:
    return {"Critical": 3, "High": 2, "Medium": 1, "Low": 0}.get(sev, 1)
