"""
Stage 4 — Result Analyzer.

Turns raw execution results into insight: classification tallies, per-mutant and
per-stage timing, root-cause pattern detection for survivors, and the mutation
score delta versus a previous run.

Components:
    Classifier            -> Killed / Survived / Equivalent / Build-error counts
    ExecutionTimeTracker  -> per-mutant + aggregate timing (NEW surfaced)
    PatternDetector       -> reuse quality.RootCauseAnalyzer (Phase 2)
    CoverageDeltaCalc     -> score change vs baseline (NEW surfaced)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class SurvivorInsight:
    method: str
    mutant_id: Any
    original_code: str
    mutated_code: str
    category: str
    root_cause: str
    rationale: str
    suggested_focus: str
    confidence: int

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class AnalysisResult:
    total: int = 0
    killed: int = 0
    survived: int = 0
    equivalent: int = 0
    build_error: int = 0
    errors: int = 0
    mutation_score: float = 0.0
    previous_score: Optional[float] = None
    coverage_delta: Optional[float] = None
    total_time_s: float = 0.0
    avg_time_s: float = 0.0
    slowest: Optional[Dict[str, Any]] = None
    survivors: List[SurvivorInsight] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d["survivors"] = [s.to_dict() for s in self.survivors]
        return d


class ExecutionTimeTracker:
    def summarize(self, results: List[Any]) -> Dict[str, Any]:
        times = [(getattr(r, "duration_s", 0.0), r) for r in results]
        total = round(sum(t for t, _ in times), 4)
        avg = round(total / len(times), 4) if times else 0.0
        slowest = max(times, key=lambda t: t[0], default=(0.0, None))
        slow = None
        if slowest[1] is not None and slowest[0] > 0:
            r = slowest[1]
            slow = {"method": r.method, "mutant_id": r.mutant_id, "duration_s": slowest[0]}
        return {"total_time_s": total, "avg_time_s": avg, "slowest": slow}


class CoverageDeltaCalculator:
    def delta(self, current_score: float, previous_score: Optional[float]) -> Optional[float]:
        if previous_score is None:
            return None
        return round(current_score - previous_score, 2)


class ResultAnalyzer:
    """Stage 4 façade."""

    def __init__(self, use_llm: bool = False) -> None:
        self.timer = ExecutionTimeTracker()
        self.delta_calc = CoverageDeltaCalculator()
        # Lazy: only build the root-cause analyzer when first needed.
        self._use_llm = use_llm
        self._rca = None

    def _analyzer(self):
        if self._rca is None:
            from quality.root_cause import RootCauseAnalyzer

            self._rca = RootCauseAnalyzer(use_llm=self._use_llm)
        return self._rca

    def analyze(
        self,
        results: List[Any],                       # list[JobResult]
        payloads: Optional[Dict[Any, Dict[str, Any]]] = None,   # keyed by (method, mutant_id)
        previous_score: Optional[float] = None,
    ) -> AnalysisResult:
        out = AnalysisResult(total=len(results), previous_score=previous_score)
        payloads = payloads or {}

        for r in results:
            status = (r.status or "").lower()
            if status == "killed":
                out.killed += 1
            elif status == "survived":
                out.survived += 1
            elif status == "equivalent":
                out.equivalent += 1
            elif "build" in status:
                out.build_error += 1
            else:
                out.errors += 1

        denom = out.killed + out.survived
        out.mutation_score = round((out.killed / denom) * 100, 2) if denom else 0.0
        out.coverage_delta = self.delta_calc.delta(out.mutation_score, previous_score)

        timing = self.timer.summarize(results)
        out.total_time_s = timing["total_time_s"]
        out.avg_time_s = timing["avg_time_s"]
        out.slowest = timing["slowest"]

        # Pattern detection: explain every survivor.
        analyzer = self._analyzer()
        for r in results:
            if (r.status or "").lower() != "survived":
                continue
            p = payloads.get((r.method, r.mutant_id)) or payloads.get(r.mutant_id, {})
            original = p.get("original_code", "")
            mutated = p.get("mutated_code", "")
            category = p.get("category", p.get("mutant_category", ""))
            rc = analyzer.analyze(original, mutated, category)
            out.survivors.append(
                SurvivorInsight(
                    method=r.method,
                    mutant_id=r.mutant_id,
                    original_code=original,
                    mutated_code=mutated,
                    category=category,
                    root_cause=rc.category.value,
                    rationale=rc.rationale,
                    suggested_focus=rc.suggested_focus,
                    confidence=rc.confidence,
                )
            )
        return out
