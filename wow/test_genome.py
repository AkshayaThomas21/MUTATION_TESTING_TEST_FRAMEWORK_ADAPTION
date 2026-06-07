"""
Test Genome Engine.

Produces a 6-axis "DNA fingerprint" of *where* a test suite is blind, by bucketing
surviving mutants into weakness archetypes. Rendered as a radar in the briefing,
it lets a reviewer see the shape of the gap at a glance — boundary-blind,
exception-blind, assertion-weak, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# Radar axes (stable order) and the root causes that feed each.
_AXES = ["Boundary", "Exception", "Assertion", "State", "Logic", "Dead Code"]
_ROOTCAUSE_TO_AXIS = {
    "Boundary Gap": "Boundary",
    "Exception Gap": "Exception",
    "Missing Assertion": "Assertion",
    "Weak Assertion": "Assertion",
    "State Validation Gap": "State",
    "Dead Code": "Dead Code",
}
_CATEGORY_TO_AXIS = {
    "boundary": "Boundary",
    "relational operator replacement": "Boundary",
    "logical operator replacement": "Logic",
    "negation": "Logic",
    "arithmetic operator replacement": "Logic",
    "return value change": "Assertion",
    "constant replacement": "Boundary",
    "statement deletion": "State",
}


@dataclass
class TestGenome:
    axes: List[str] = field(default_factory=lambda: list(_AXES))
    values: List[int] = field(default_factory=lambda: [0] * len(_AXES))  # survivor count per axis
    dominant: str = ""                  # the weakest area
    fingerprint: str = ""               # short signature e.g. "B3-E1-A2"
    total_blind_spots: int = 0

    def normalized(self) -> List[float]:
        mx = max(self.values) or 1
        return [round(v / mx, 3) for v in self.values]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "axes": self.axes,
            "values": self.values,
            "normalized": self.normalized(),
            "dominant": self.dominant,
            "fingerprint": self.fingerprint,
            "total_blind_spots": self.total_blind_spots,
        }


class TestGenomeEngine:
    def build(self, report: Any) -> TestGenome:
        counts = {a: 0 for a in _AXES}
        survivors = report.stage4.survivors if report.stage4 else []
        for s in survivors:
            axis = _ROOTCAUSE_TO_AXIS.get(s.root_cause)
            if axis is None:
                axis = _CATEGORY_TO_AXIS.get((s.category or "").strip().lower(), "Logic")
            counts[axis] += 1

        values = [counts[a] for a in _AXES]
        total = sum(values)
        dominant = _AXES[values.index(max(values))] if total else "None"
        # compact signature: first letter of each non-zero axis + count
        sig = "-".join(f"{a[0]}{counts[a]}" for a in _AXES if counts[a] > 0) or "CLEAN"

        return TestGenome(
            axes=list(_AXES),
            values=values,
            dominant=dominant,
            fingerprint=sig,
            total_blind_spots=total,
        )
