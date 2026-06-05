"""
Path A — TestGenerator.

Designs NEW tests (in CIR) to kill surviving mutants, guided by root-cause
analysis, then renders them into the team's framework via the adapter. The
actual compile/run validation (pass-on-original + fail-on-mutant) is performed
by the orchestrator using the same adapter.execute_tests path.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

from adapters.base_adapter import BaseAdapter
from adapters.cir import CIRTestCase, CIRAssertion, CIRInput, AssertionType
from quality.root_cause import RootCauseAnalyzer, RootCause

log = logging.getLogger(__name__)


class TestGenerator:
    def __init__(self, adapter: BaseAdapter, use_llm: bool = True) -> None:
        self.adapter = adapter
        self.use_llm = use_llm
        self.rca = RootCauseAnalyzer(use_llm=False)
        self._chain = None

    def _chain_lazy(self):
        if self._chain is None:
            from src.llm_runnable import create_runnable
            from synthesis.prompts_area2 import test_synthesis_prompt
            from synthesis.synthesis_models import GeneratedTestBatch

            self._chain = create_runnable(test_synthesis_prompt).get_runnable_with_structured_output(
                GeneratedTestBatch
            )
        return self._chain

    def generate_for_mutant(
        self,
        method_name: str,
        source_code: str,
        mutant: Dict[str, Any],
        dependency_data: Optional[dict] = None,
        assertion_strength: float = 100.0,
    ) -> Dict[str, Any]:
        """Returns {root_cause, cir_tests, rendered, confidence}."""
        rc: RootCause = self.rca.analyze(
            mutant.get("original_code", ""),
            mutant.get("mutated_code", ""),
            mutant.get("mutant_category", ""),
            assertion_strength,
        )

        cir_tests: List[CIRTestCase] = []
        if self.use_llm:
            cir_tests = self._llm_generate(method_name, source_code, mutant, rc, dependency_data or {})
        if not cir_tests:
            cir_tests = [self._heuristic_test(method_name, mutant, rc)]

        rendered = [self.adapter.render_test(t) for t in cir_tests]
        confidences = [_test_confidence(t, rc.confidence) for t in cir_tests]
        avg_conf = round(sum(confidences) / len(confidences), 1) if confidences else float(rc.confidence)
        return {
            "method": method_name,
            "root_cause": rc.category.value,
            "root_cause_focus": rc.suggested_focus,
            "cir_tests": [t.model_dump(mode="json") for t in cir_tests],
            "rendered": rendered,
            "framework": self.adapter.capabilities.name,
            "confidence": avg_conf,
        }

    # ------------------------------------------------------------------ #
    def _llm_generate(self, method_name, source_code, mutant, rc, deps) -> List[CIRTestCase]:
        try:
            from src.utils import stringify_function_dict

            chain = self._chain_lazy()
            batch = chain.invoke(
                {
                    "method_name": method_name,
                    "source_code": source_code,
                    "mutant_original": mutant.get("original_code", ""),
                    "mutant_mutated": mutant.get("mutated_code", ""),
                    "mutant_category": mutant.get("mutant_category", ""),
                    "root_cause_category": rc.category.value,
                    "root_cause_focus": rc.suggested_focus,
                    "dependency_data": stringify_function_dict(dict(deps)) if deps else "None",
                }
            )
            out: List[CIRTestCase] = []
            for g in batch.tests:
                out.append(
                    CIRTestCase(
                        test_case_id=g.test_name,
                        method_under_test=g.method_under_test or method_name,
                        framework_source=self.adapter.capabilities.name,
                        suite=f"{method_name}_MutationKill",
                        inputs=[CIRInput(param=f"arg{i}", value=v) for i, v in enumerate(g.inputs)],
                        assertions=[
                            CIRAssertion(
                                type=_safe_atype(a.type),
                                expected=a.expected,
                                actual=a.actual,
                                tolerance=a.tolerance,
                            )
                            for a in g.assertions
                        ],
                        tags=[f"confidence:{g.confidence}", f"root_cause:{rc.category.value}"],
                    )
                )
            return out
        except Exception as exc:
            log.warning("LLM test generation failed (%s); using heuristic.", exc)
            return []

    def _heuristic_test(self, method_name, mutant, rc) -> CIRTestCase:
        import re

        num = None
        m = re.search(r"\b(\d+)\b", mutant.get("original_code", ""))
        if m:
            num = m.group(1)
        assertions = [
            CIRAssertion(type=AssertionType.EQUAL, expected=num or "EXPECTED", actual=f"{method_name}(/* args */)")
        ]
        return CIRTestCase(
            test_case_id=f"Kill_{method_name}_{rc.category.name}",
            method_under_test=method_name,
            framework_source=self.adapter.capabilities.name,
            suite=f"{method_name}_MutationKill",
            assertions=assertions,
            tags=[f"root_cause:{rc.category.value}", "heuristic"],
        )


def _safe_atype(value: str) -> AssertionType:
    try:
        return AssertionType(str(value).upper())
    except Exception:
        return AssertionType.EQUAL


def _test_confidence(test: CIRTestCase, default: int) -> float:
    """Read the LLM-assigned 'confidence:NN' tag, else fall back to root-cause confidence."""
    for tag in test.tags:
        if tag.startswith("confidence:"):
            try:
                return float(tag.split(":", 1)[1])
            except (ValueError, IndexError):
                pass
    return float(default)
