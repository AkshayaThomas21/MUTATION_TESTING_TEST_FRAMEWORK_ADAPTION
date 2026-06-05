"""
QualitySignalEngine — aggregates the 4 quadrants into one quality index,
correlates signals, and emits actionable insights + recommendations.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any

from quality.metrics import (
    MutationMetrics,
    TestQualityMetrics,
    AIPerformanceMetrics,
    ExecutionMetrics,
    QualityReport,
)


class QualitySignalEngine:
    # Weighting of each quadrant in the unified 0-100 quality index.
    WEIGHTS = {"mutation": 0.45, "test_quality": 0.25, "ai": 0.15, "execution": 0.15}

    def aggregate(
        self,
        project: str,
        framework: str,
        mutation: MutationMetrics,
        test_quality: TestQualityMetrics,
        ai: AIPerformanceMetrics,
        execution: ExecutionMetrics,
        survived_mutants: List[Dict[str, Any]] | None = None,
    ) -> QualityReport:
        quality_index = self._quality_index(mutation, test_quality, ai, execution)
        report = QualityReport(
            project=project,
            framework=framework,
            mutation=mutation,
            test_quality=test_quality,
            ai=ai,
            execution=execution,
            quality_index=quality_index,
            star_rating=self._stars(quality_index),
            survived_mutants=survived_mutants or [],
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        report.insights = self._insights(report)
        report.recommendations = self._recommendations(report)
        return report

    # ------------------------------------------------------------------ #
    def _quality_index(self, m, tq, ai, ex) -> float:
        mutation_component = m.mutation_score
        tq_component = (
            0.4 * tq.effectiveness
            + 0.3 * tq.assertion_strength
            + 0.2 * max(0.0, 100 - tq.flakiness_rate * 10)
            + 0.1 * max(0.0, 100 - tq.redundancy)
        )
        ai_component = (
            0.5 * ai.acceptance_rate
            + 0.3 * ai.avg_confidence
            + 0.2 * max(0.0, 100 - ai.hallucination_rate * 10)
        )
        ex_component = 0.5 * ex.success_rate + 0.5 * ex.parallel_efficiency
        idx = (
            self.WEIGHTS["mutation"] * mutation_component
            + self.WEIGHTS["test_quality"] * tq_component
            + self.WEIGHTS["ai"] * ai_component
            + self.WEIGHTS["execution"] * ex_component
        )
        return round(min(100.0, max(0.0, idx)), 1)

    @staticmethod
    def _stars(idx: float) -> int:
        return max(1, min(5, int(round(idx / 20.0))))

    # ------------------------------------------------------------------ #
    def _insights(self, r: QualityReport) -> List[str]:
        out: List[str] = []
        m, tq, ai, ex = r.mutation, r.test_quality, r.ai, r.execution

        if m.coverage_delta > 0:
            out.append(f"Mutation score improved by +{m.coverage_delta}% this run.")
        elif m.coverage_delta < 0:
            out.append(f"Mutation score dropped by {m.coverage_delta}% — investigate new untested code.")

        # Cross-quadrant correlation (the 'brain' aspect).
        if ai.hallucination_rate > 5 and ai.acceptance_rate < 70:
            out.append("High hallucination rate is dragging down recommendation acceptance — tighten validation.")
        if tq.assertion_strength < 50 and m.survived > 0:
            out.append("Weak assertions correlate with surviving mutants — prioritize assertion strengthening.")
        if ex.parallel_efficiency < 70:
            out.append("Low parallel efficiency suggests resource contention — increase worker isolation.")
        if tq.flakiness_rate > 2:
            out.append(f"Flaky tests at {tq.flakiness_rate}% exceed the 2% trust threshold.")
        if not out:
            out.append("All quadrants within healthy thresholds.")
        return out

    def _recommendations(self, r: QualityReport) -> List[str]:
        recs: List[str] = []
        if r.mutation.survived > 0:
            recs.append(f"Generate {r.mutation.survived} new tests for surviving mutants.")
        if r.test_quality.assertion_strength < 70:
            recs.append("Strengthen weak assertions (EXPECT_TRUE -> EXPECT_EQ).")
        if r.test_quality.redundancy > 15:
            recs.append(f"Review ~{int(r.test_quality.redundancy)}% redundant tests to speed up the suite.")
        if r.ai.cost_per_test > 0.15:
            recs.append("Cost per test is high — route simple cases to a cheaper model.")
        if not recs:
            recs.append("No action required — suite is healthy.")
        return recs
