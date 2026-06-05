"""
Path B — TestImprover.

Analyzes existing (weak) tests in CIR form against surviving mutants and emits
human-reviewable improvement recommendations (stronger assertions, missing
boundaries, etc.). Low-confidence items are flagged for human-in-the-loop.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any

from adapters.cir import CIRSuite, CIRTestCase, AssertionType

log = logging.getLogger(__name__)

HUMAN_REVIEW_THRESHOLD = 75  # below this confidence -> needs developer approval


class TestImprover:
    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self._chain = None

    def _chain_lazy(self):
        if self._chain is None:
            from src.llm_runnable import create_runnable
            from synthesis.prompts_area2 import test_improvement_prompt
            from synthesis.synthesis_models import TestImprovementBatch

            self._chain = create_runnable(test_improvement_prompt).get_runnable_with_structured_output(
                TestImprovementBatch
            )
        return self._chain

    def improve(
        self,
        method_name: str,
        source_code: str,
        existing_tests: List[CIRTestCase],
        survived_mutants: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        if self.use_llm:
            recs = self._llm_improve(method_name, source_code, existing_tests, survived_mutants)
        if not recs:
            recs = self._heuristic_improve(existing_tests)
        for r in recs:
            r["needs_human_review"] = r.get("confidence", 0) < HUMAN_REVIEW_THRESHOLD
        return recs

    # ------------------------------------------------------------------ #
    def _llm_improve(self, method_name, source_code, existing_tests, survived) -> List[Dict[str, Any]]:
        try:
            chain = self._chain_lazy()
            tests_str = "\n\n".join(
                f"{t.test_case_id} (strength={t.assertion_strength()}):\n{t.raw_body or t.assertions}"
                for t in existing_tests
            ) or "No existing tests."
            survived_str = "\n".join(
                f"- {m.get('original_code','')} -> {m.get('mutated_code','')} [{m.get('mutant_category','')}]"
                for m in survived
            ) or "None."
            batch = chain.invoke(
                {
                    "method_name": method_name,
                    "source_code": source_code,
                    "existing_tests": tests_str,
                    "survived_mutants": survived_str,
                }
            )
            return [i.model_dump() for i in batch.improvements]
        except Exception as exc:
            log.warning("LLM test improvement failed (%s); using heuristic.", exc)
            return []

    def _heuristic_improve(self, existing_tests: List[CIRTestCase]) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        for t in existing_tests:
            for a in t.assertions:
                if a.type in (AssertionType.TRUE, AssertionType.FALSE, AssertionType.UNKNOWN):
                    recs.append(
                        {
                            "test_name": t.test_case_id,
                            "weakness": f"{a.type.value} assertion hides the actual value.",
                            "recommendation": "Replace boolean check with an exact-value (EQUAL) assertion.",
                            "before": a.raw or f"{a.type.value}({a.actual})",
                            "after": f"EXPECT_EQ(<expected>, {a.actual or '<call>'})",
                            "severity": "high",
                            "confidence": 80,
                        }
                    )
            if t.assertion_strength() < 50:
                recs.append(
                    {
                        "test_name": t.test_case_id,
                        "weakness": "Overall weak assertions; missing boundary cases.",
                        "recommendation": "Add boundary tests (0, MAX, off-by-one) with exact assertions.",
                        "before": t.test_case_id,
                        "after": "Add 2-3 boundary test cases.",
                        "severity": "medium",
                        "confidence": 70,
                    }
                )
        return recs
