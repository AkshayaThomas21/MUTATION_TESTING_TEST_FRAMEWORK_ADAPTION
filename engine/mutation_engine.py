"""
Stage 2 — LLM Mutation Engine.

Generates mutants (real LangGraph generator when available, otherwise consumes a
pre-supplied list), then scores, filters, and prioritizes them.

Components:
    Generator           -> reuse src LangGraph mutant generator (optional, LLM)
    ConfidenceScorer    -> 0-100 likelihood the mutant is a useful, valid change (NEW)
    HallucinationFilter -> syntactic sanity + optional LLM checker (NEW heuristic)
    SmartSelector       -> prioritize high-value, diverse mutants (NEW)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Category -> base confidence that the mutant is a meaningful, killable change.
_CATEGORY_WEIGHT = {
    "relational operator replacement": 90,
    "arithmetic operator replacement": 85,
    "logical operator replacement": 88,
    "boundary": 92,
    "boundary condition": 92,
    "conditional boundary": 90,
    "constant replacement": 78,
    "value replacement": 75,
    "return value": 80,
    "statement deletion": 70,
    "negation": 82,
}
_DEFAULT_WEIGHT = 65


@dataclass
class ScoredMutant:
    method: str
    mutant_id: Any
    original_code: str
    mutated_code: str
    category: str
    confidence: int = 0            # 0-100
    is_hallucination: bool = False
    hallucination_reason: str = ""
    priority_rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class MutationBatch:
    mutants: List[ScoredMutant] = field(default_factory=list)
    rejected: List[ScoredMutant] = field(default_factory=list)   # hallucinations

    @property
    def selected(self) -> List[ScoredMutant]:
        return [m for m in self.mutants if not m.is_hallucination]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected": [m.to_dict() for m in self.selected],
            "rejected": [m.to_dict() for m in self.rejected],
            "total_generated": len(self.mutants) + len(self.rejected),
        }


class ConfidenceScorer:
    """Heuristic 0-100 score from mutation category and the size/shape of the change."""

    def score(self, original: str, mutated: str, category: str) -> int:
        base = _CATEGORY_WEIGHT.get((category or "").strip().lower(), _DEFAULT_WEIGHT)
        o, m = original.strip(), mutated.strip()

        # No-op or trivially-equivalent change -> low confidence.
        if o == m:
            return 5
        # Tiny, surgical edits are the most reliable, killable mutants.
        ratio = _similarity(o, m)
        if ratio > 0.95:
            base += 6
        elif ratio < 0.4:
            base -= 18           # large rewrites are riskier / more likely equivalent
        # Whole-line/structure deletion is noisier.
        if not m:
            base -= 25
        return max(0, min(100, base))


class HallucinationFilter:
    """
    Cheap syntactic sanity check (balanced brackets, non-empty, plausible token
    change). An LLM checker can be plugged in via `llm_checker(original, mutated)`.
    """

    def __init__(self, llm_checker: Optional[Any] = None) -> None:
        self.llm_checker = llm_checker

    def check(self, original: str, mutated: str) -> tuple[bool, str]:
        m = mutated.strip()
        if not m:
            return True, "empty mutation"
        # Mutants are line fragments, so an opening brace without its close is
        # normal. Flag only when the mutation CHANGES the bracket balance versus
        # the original (a real structural corruption / hallucination).
        for open_c, close_c in [("(", ")"), ("{", "}"), ("[", "]")]:
            o_delta = original.count(open_c) - original.count(close_c)
            m_delta = m.count(open_c) - m.count(close_c)
            if o_delta != m_delta:
                return True, f"changed '{open_c}{close_c}' balance"
        # Identical to original is not a hallucination, just useless (handled by scorer).
        if self.llm_checker is not None:
            try:
                verdict = self.llm_checker(original, mutated)
                if str(verdict).lower().startswith("halluc"):
                    return True, "llm flagged hallucination"
            except Exception:
                pass
        return False, ""


class SmartSelector:
    """
    Prioritizes mutants: highest confidence first, while keeping category diversity
    so the suite is probed from multiple angles. Optionally caps the batch size.
    """

    def select(self, mutants: List[ScoredMutant], max_total: Optional[int] = None) -> List[ScoredMutant]:
        valid = [m for m in mutants if not m.is_hallucination]
        valid.sort(key=lambda m: m.confidence, reverse=True)

        # Round-robin by category to avoid flooding with one mutation type.
        buckets: Dict[str, List[ScoredMutant]] = {}
        for m in valid:
            buckets.setdefault(m.category or "uncategorized", []).append(m)
        ordered: List[ScoredMutant] = []
        while any(buckets.values()):
            for cat in list(buckets.keys()):
                if buckets[cat]:
                    ordered.append(buckets[cat].pop(0))
        if max_total:
            ordered = ordered[:max_total]
        for i, m in enumerate(ordered, start=1):
            m.priority_rank = i
        return ordered


class LLMMutationEngine:
    """Stage 2 façade."""

    def __init__(self, llm_checker: Optional[Any] = None) -> None:
        self.scorer = ConfidenceScorer()
        self.filter = HallucinationFilter(llm_checker=llm_checker)
        self.selector = SmartSelector()

    def process(
        self,
        mutants_by_method: Dict[str, List[Dict[str, Any]]],
        max_total: Optional[int] = None,
    ) -> MutationBatch:
        """
        Takes raw mutants ({method: [{original_code, mutated_code, mutant_category, ...}]})
        and returns a scored, filtered, prioritized batch.
        """
        batch = MutationBatch()
        for method, mutants in mutants_by_method.items():
            for mut in mutants:
                original = mut.get("original_code", "")
                mutated = mut.get("mutated_code", "")
                category = mut.get("mutant_category", mut.get("category", "uncategorized"))
                halluc, reason = self.filter.check(original, mutated)
                sm = ScoredMutant(
                    method=method.split("(")[0].strip(),
                    mutant_id=mut.get("mutant_id", mut.get("id", "N/A")),
                    original_code=original,
                    mutated_code=mutated,
                    category=category,
                    confidence=self.scorer.score(original, mutated, category),
                    is_hallucination=halluc,
                    hallucination_reason=reason,
                )
                if halluc:
                    batch.rejected.append(sm)
                else:
                    batch.mutants.append(sm)
        batch.mutants = self.selector.select(batch.mutants, max_total=max_total)
        return batch


def _similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, re.sub(r"\s+", "", a), re.sub(r"\s+", "", b)).ratio()
