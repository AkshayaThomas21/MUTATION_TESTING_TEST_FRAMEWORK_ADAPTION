"""
The four metric quadrants of the Quality Signal Engine.

Quadrant 1: Mutation Metrics        — is the test suite effective?
Quadrant 2: Test Quality Metrics    — are the individual tests healthy?
Quadrant 3: AI Performance Metrics  — is the LLM effective and cost-efficient?
Quadrant 4: Execution Metrics       — is the system fast and reliable?
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List


@dataclass
class MutationMetrics:
    killed: int = 0
    survived: int = 0
    equivalent: int = 0
    build_error: int = 0
    previous_score: float = 0.0  # for the coverage delta / trend

    @property
    def total(self) -> int:
        return self.killed + self.survived + self.equivalent + self.build_error

    @property
    def scored_total(self) -> int:
        # Equivalent + build-error mutants are excluded from the score.
        return self.killed + self.survived

    @property
    def mutation_score(self) -> float:
        return round((self.killed / self.scored_total) * 100, 2) if self.scored_total else 0.0

    @property
    def coverage_delta(self) -> float:
        return round(self.mutation_score - self.previous_score, 2)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.update(
            mutation_score=self.mutation_score,
            total=self.total,
            coverage_delta=self.coverage_delta,
        )
        return d


@dataclass
class TestQualityMetrics:
    coverage_impact: float = 0.0      # % coverage gained from AI tests
    effectiveness: float = 0.0        # avg mutants killed per test (0-100)
    flakiness_rate: float = 0.0       # % intermittently-failing tests (target < 2)
    redundancy: float = 0.0           # % overlapping tests
    assertion_strength: float = 0.0   # 0-100 from CIR assertion analysis

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIPerformanceMetrics:
    tests_generated: int = 0
    accepted: int = 0
    hallucinations: int = 0
    avg_confidence: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def acceptance_rate(self) -> float:
        return round((self.accepted / self.tests_generated) * 100, 1) if self.tests_generated else 0.0

    @property
    def hallucination_rate(self) -> float:
        return round((self.hallucinations / self.tests_generated) * 100, 1) if self.tests_generated else 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_per_test(self) -> float:
        return round(self.cost_usd / self.tests_generated, 4) if self.tests_generated else 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.update(
            acceptance_rate=self.acceptance_rate,
            hallucination_rate=self.hallucination_rate,
            total_tokens=self.total_tokens,
            cost_per_test=self.cost_per_test,
        )
        return d


@dataclass
class ExecutionMetrics:
    total_runs: int = 0
    total_time_s: float = 0.0
    parallel_efficiency: float = 0.0   # %
    cpu_utilization: float = 0.0       # %
    memory_utilization: float = 0.0    # %
    failed_runs: int = 0

    @property
    def success_rate(self) -> float:
        if not self.total_runs:
            return 0.0
        return round(((self.total_runs - self.failed_runs) / self.total_runs) * 100, 1)

    @property
    def total_time_min(self) -> float:
        return round(self.total_time_s / 60.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.update(success_rate=self.success_rate, total_time_min=self.total_time_min)
        return d


@dataclass
class QualityReport:
    """The unified output consumed by the dashboard and CI/CD gate."""

    project: str
    framework: str
    mutation: MutationMetrics = field(default_factory=MutationMetrics)
    test_quality: TestQualityMetrics = field(default_factory=TestQualityMetrics)
    ai: AIPerformanceMetrics = field(default_factory=AIPerformanceMetrics)
    execution: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    quality_index: float = 0.0
    star_rating: int = 0
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    survived_mutants: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "framework": self.framework,
            "timestamp": self.timestamp,
            "quality_index": self.quality_index,
            "star_rating": self.star_rating,
            "mutation": self.mutation.to_dict(),
            "test_quality": self.test_quality.to_dict(),
            "ai": self.ai.to_dict(),
            "execution": self.execution.to_dict(),
            "insights": self.insights,
            "recommendations": self.recommendations,
            "survived_mutants": self.survived_mutants,
        }
