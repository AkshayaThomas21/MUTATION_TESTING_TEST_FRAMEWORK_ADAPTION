"""
AI Test Synthesis Engine (Area 2 — Module 6).

Dual path:
  Path A — TestGenerator: generate NEW tests that kill survived mutants,
           guided by root-cause analysis. Output is framework-neutral (CIR),
           then rendered by the chosen adapter.
  Path B — TestImprover: recommend targeted improvements to weak existing
           tests (stronger assertions, missing boundaries) with human-in-loop.
"""

from synthesis.synthesis_models import (
    GeneratedCIRTest,
    GeneratedTestBatch,
    TestImprovement,
    TestImprovementBatch,
    RootCauseOutput,
)
from synthesis.test_generator import TestGenerator
from synthesis.test_improver import TestImprover

__all__ = [
    "GeneratedCIRTest",
    "GeneratedTestBatch",
    "TestImprovement",
    "TestImprovementBatch",
    "RootCauseOutput",
    "TestGenerator",
    "TestImprover",
]
