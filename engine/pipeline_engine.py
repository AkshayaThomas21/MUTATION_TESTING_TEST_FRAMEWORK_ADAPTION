"""
MutationPipelineEngine — runs all five stages in order.

    Stage 1  Code Intelligence  -> structure, dep graph, test trace, coverage gaps
    Stage 2  LLM Mutation        -> score, filter, prioritize mutants
    Stage 3  Parallel Execution  -> isolated, scheduled, timed runs
    Stage 4  Result Analyzer     -> classify, time, pattern-detect survivors
    Stage 5  AI Test Synthesis   -> generate + validate + integrate killing tests

Designed to run fully OFFLINE (simulated execution + heuristic LLM paths) so the
whole pipeline is demonstrable without Azure or a C build, while transparently
using the real engines when `use_llm=True` and a real `runner` are supplied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable

from engine.code_intelligence import CodeIntelligenceEngine, CodeIntelligenceResult
from engine.mutation_engine import LLMMutationEngine, MutationBatch
from engine.execution_orchestrator import (
    ParallelExecutionOrchestrator,
    ExecutionJob,
    JobResult,
)
from engine.result_analyzer import ResultAnalyzer, AnalysisResult
from engine.synthesis_stage import AITestSynthesisStage, SynthesisResult


@dataclass
class PipelineReport:
    framework: str = ""
    stage1: Optional[CodeIntelligenceResult] = None
    stage2: Optional[MutationBatch] = None
    stage4: Optional[AnalysisResult] = None
    stage5: Optional[SynthesisResult] = None
    execution_results: List[JobResult] = field(default_factory=list)
    resource_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework,
            "stage1_code_intelligence": self.stage1.to_dict() if self.stage1 else None,
            "stage2_mutation": self.stage2.to_dict() if self.stage2 else None,
            "stage3_execution": {
                "resources": self.resource_summary,
                "results": [r.to_dict() for r in self.execution_results],
            },
            "stage4_analysis": self.stage4.to_dict() if self.stage4 else None,
            "stage5_synthesis": self.stage5.to_dict() if self.stage5 else None,
        }

    def headline(self) -> Dict[str, Any]:
        a = self.stage4
        return {
            "framework": self.framework,
            "methods_analyzed": len(self.stage1.methods) if self.stage1 else 0,
            "coverage_gaps": len(self.stage1.gaps) if self.stage1 else 0,
            "mutants_selected": len(self.stage2.selected) if self.stage2 else 0,
            "mutants_rejected": len(self.stage2.rejected) if self.stage2 else 0,
            "mutation_score": a.mutation_score if a else 0.0,
            "killed": a.killed if a else 0,
            "survived": a.survived if a else 0,
            "coverage_delta": a.coverage_delta if a else None,
            "total_time_s": a.total_time_s if a else 0.0,
            "tests_generated": len(self.stage5.tests) if self.stage5 else 0,
            "tests_accepted": len(self.stage5.accepted) if self.stage5 else 0,
        }


class MutationPipelineEngine:
    def __init__(
        self,
        framework: str = "gtest",
        use_llm: bool = False,
        max_workers: Optional[int] = None,
    ) -> None:
        self.framework = framework
        self.use_llm = use_llm
        self.stage1 = CodeIntelligenceEngine()
        self.stage2 = LLMMutationEngine()
        self.stage3 = ParallelExecutionOrchestrator(max_workers=max_workers)
        self.stage4 = ResultAnalyzer(use_llm=use_llm)
        self.stage5 = AITestSynthesisStage(framework=framework, use_llm=use_llm)

    def run(
        self,
        source_by_method: Dict[str, str],
        mutants_by_method: Dict[str, List[Dict[str, Any]]],
        cir_suite: Optional[Any] = None,
        raw_tests: Optional[Dict[str, str]] = None,
        runner: Optional[Callable[[ExecutionJob], JobResult]] = None,
        previous_score: Optional[float] = None,
        max_mutants: Optional[int] = None,
    ) -> PipelineReport:
        report = PipelineReport(framework=self.framework)

        # -- Stage 1 ---------------------------------------------------- #
        report.stage1 = self.stage1.analyze(
            source_by_method, cir_suite=cir_suite, raw_tests=raw_tests
        )

        # -- Stage 2 ---------------------------------------------------- #
        report.stage2 = self.stage2.process(mutants_by_method, max_total=max_mutants)

        # -- Stage 3 ---------------------------------------------------- #
        run_fn = runner or ParallelExecutionOrchestrator.simulated_runner
        selected = report.stage2.selected
        report.execution_results = self.stage3.run(selected, run_fn)
        report.resource_summary = self.stage3.resources.summary()

        # -- Stage 4 ---------------------------------------------------- #
        payloads = {(m.method, m.mutant_id): m.to_dict() for m in selected}
        report.stage4 = self.stage4.analyze(
            report.execution_results, payloads=payloads, previous_score=previous_score
        )

        # -- Stage 5 ---------------------------------------------------- #
        report.stage5 = self.stage5.synthesize(report.stage4.survivors, source_by_method)
        return report

    # -- offline demo ---------------------------------------------------- #
    def run_demo(self) -> PipelineReport:
        """Self-contained demo using the Phase-2 sample source + mutants."""
        from dashboard.demo_data import SAMPLE_SOURCE, SAMPLE_MUTANTS

        source_by_method = _coerce_source(SAMPLE_SOURCE)
        mutants_by_method = _coerce_mutants(SAMPLE_MUTANTS)
        return self.run(source_by_method, mutants_by_method, previous_score=62.0)


# --------------------------------------------------------------------- #
def _coerce_source(sample: Any) -> Dict[str, str]:
    if isinstance(sample, dict):
        return sample
    # SAMPLE_SOURCE may be one big string of multiple functions.
    import re

    out: Dict[str, str] = {}
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{", str(sample)):
        out[m.group(1)] = str(sample)
    return out or {"sample": str(sample)}


def _coerce_mutants(sample: Any) -> Dict[str, List[Dict[str, Any]]]:
    if isinstance(sample, dict):
        return sample
    out: Dict[str, List[Dict[str, Any]]] = {}
    for mut in (sample or []):
        method = (mut.get("function_name") or mut.get("method") or "sample").split("(")[0].strip()
        out.setdefault(method, []).append(mut)
    return out
