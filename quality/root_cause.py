"""
Root Cause Analyzer (Area 2 — Module 5).

For every SURVIVED mutant, determine *why* the test suite missed it. The
category drives the AI Test Synthesis Engine: it tells the generator exactly
what kind of test to write (boundary, exception, state, assertion, ...).

Two modes:
  * heuristic  — fast, deterministic, no LLM (great for the live demo)
  * llm        — uses the existing Azure runnable for nuanced cases
"""

from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List


class RootCauseCategory(str, Enum):
    MISSING_ASSERTION = "Missing Assertion"
    BOUNDARY_GAP = "Boundary Gap"
    EXCEPTION_GAP = "Exception Gap"
    STATE_VALIDATION_GAP = "State Validation Gap"
    DEAD_CODE = "Dead Code"
    WEAK_ASSERTION = "Weak Assertion"
    UNCATEGORIZED = "Uncategorized"


@dataclass
class RootCause:
    category: RootCauseCategory
    rationale: str
    suggested_focus: str  # the concrete hint handed to the test generator
    confidence: int = 70


# Signals in the mutation diff that point to a category.
_BOUNDARY_SIGNS = [
    (r"[<>]=?", "relational/boundary operator changed"),
    (r"\b(\d+)\b", "numeric constant changed"),
    (r"\+\+|--", "increment/decrement changed"),
]
_LOGIC_SIGNS = [(r"&&|\|\|", "logical connector changed")]
_RETURN_SIGNS = [(r"\breturn\b", "return value changed")]
_EXCEPTION_SIGNS = [(r"\b(throw|assert|abort|exit|errno|NULL|nullptr)\b", "error/exception path changed")]
_STATE_SIGNS = [(r"=[^=]", "assignment / state change altered"), (r"\+\=|\-\=|\*\=", "compound state update altered")]


class RootCauseAnalyzer:
    def __init__(self, use_llm: bool = False) -> None:
        self.use_llm = use_llm

    def analyze(
        self,
        original_code: str,
        mutated_code: str,
        category: str = "",
        assertion_strength: float = 100.0,
    ) -> RootCause:
        if self.use_llm:
            llm = self._analyze_llm(original_code, mutated_code, category)
            if llm:
                return llm
        return self._analyze_heuristic(original_code, mutated_code, category, assertion_strength)

    # ------------------------------------------------------------------ #
    def _analyze_heuristic(
        self, original: str, mutated: str, category: str, assertion_strength: float
    ) -> RootCause:
        diff = self._char_diff(original, mutated)
        cat = (category or "").lower()

        if assertion_strength < 40:
            return RootCause(
                RootCauseCategory.WEAK_ASSERTION,
                "Existing assertions are weak (e.g. EXPECT_TRUE without expected value), "
                "so the mutated output is not observed.",
                "Replace boolean assertions with exact-value checks on the mutated output.",
                confidence=80,
            )

        if self._match(diff, _EXCEPTION_SIGNS) or "exception" in cat:
            return RootCause(
                RootCauseCategory.EXCEPTION_GAP,
                "Mutation altered an error/exception path that no test exercises.",
                "Add a test that drives the function into its error/exception branch.",
                confidence=78,
            )

        if self._match(diff, _BOUNDARY_SIGNS) or "boundary" in cat or "relational" in cat or "constant" in cat:
            val = self._extract_number(diff)
            focus = (
                f"Add boundary tests around {val} (val-1, val, val+1)."
                if val
                else "Add boundary/edge-value tests around the mutated condition."
            )
            return RootCause(
                RootCauseCategory.BOUNDARY_GAP,
                "Mutation shifted a boundary/relational condition; tests only cover the interior.",
                focus,
                confidence=82,
            )

        if self._match(diff, _RETURN_SIGNS) or "return" in cat:
            return RootCause(
                RootCauseCategory.MISSING_ASSERTION,
                "Mutation changed the returned value but no test asserts on it.",
                "Add an exact-equality assertion on the function's return value.",
                confidence=76,
            )

        if self._match(diff, _STATE_SIGNS) or "statement removal" in cat or "control flow" in cat:
            return RootCause(
                RootCauseCategory.STATE_VALIDATION_GAP,
                "Mutation changed internal state / a side effect that is never validated.",
                "Assert on the post-call state (output params, globals, struct fields).",
                confidence=72,
            )

        if not diff.strip():
            return RootCause(
                RootCauseCategory.DEAD_CODE,
                "Mutated region appears to be unreachable / dead code.",
                "Verify reachability; if dead, remove it rather than testing it.",
                confidence=60,
            )

        return RootCause(
            RootCauseCategory.MISSING_ASSERTION,
            "Mutated behaviour is not observed by any current assertion.",
            "Add a targeted assertion that distinguishes original vs mutated output.",
            confidence=55,
        )

    def _analyze_llm(self, original: str, mutated: str, category: str) -> Optional[RootCause]:
        try:
            from src.llm_runnable import create_runnable
            from synthesis.prompts_area2 import root_cause_prompt
            from synthesis.synthesis_models import RootCauseOutput

            chain = create_runnable(root_cause_prompt).get_runnable_with_structured_output(RootCauseOutput)
            resp = chain.invoke(
                {"original_code": original, "mutated_code": mutated, "mutant_category": category}
            )
            try:
                cat = RootCauseCategory(resp.category)
            except Exception:
                cat = RootCauseCategory.UNCATEGORIZED
            return RootCause(cat, resp.rationale, resp.suggested_focus, confidence=int(resp.confidence))
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    @staticmethod
    def _char_diff(a: str, b: str) -> str:
        from difflib import ndiff

        return "".join(
            ch[2:] for ch in ndiff(a.split(), b.split()) if ch.startswith("+ ") or ch.startswith("- ")
        )

    @staticmethod
    def _match(text: str, signs: List[tuple]) -> bool:
        return any(re.search(p, text) for p, _ in signs)

    @staticmethod
    def _extract_number(text: str) -> Optional[str]:
        m = re.search(r"\b(\d+)\b", text)
        return m.group(1) if m else None
