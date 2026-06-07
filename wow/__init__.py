"""
MutaSentinel — the "WOW" intelligence layer (Bosch Area 2).

Turns raw mutation results into decisions executives and safety engineers care about:

    safety_compliance  -> ISO 26262 ASIL certification readiness (functional safety)
    roi_engine         -> field-defect risk & cost mitigated, engineer hours saved (€)
    test_genome        -> a visual "DNA fingerprint" of where the suite is blind
    briefing           -> a self-contained, animated HTML executive briefing

No off-the-shelf mutation tool (Stryker / PIT / Mutmut) maps mutants to ASIL +
cost + an AI self-healing story. That combination is the differentiator.
"""

from wow.safety_compliance import (
    SafetyComplianceEngine,
    SafetyAssessment,
    ASIL,
)
from wow.roi_engine import ROIEngine, ROIAssessment
from wow.test_genome import TestGenomeEngine, TestGenome
from wow.briefing import generate_briefing, project_score

__all__ = [
    "SafetyComplianceEngine",
    "SafetyAssessment",
    "ASIL",
    "ROIEngine",
    "ROIAssessment",
    "TestGenomeEngine",
    "TestGenome",
    "generate_briefing",
    "project_score",
]
