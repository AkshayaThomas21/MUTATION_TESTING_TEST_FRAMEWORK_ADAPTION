"""
AI-Powered Mutation Testing Pipeline (Area 2).

Five explicit, composable stages that map 1:1 to the Phase-1 architecture:

    Stage 1  CodeIntelligenceEngine        engine/code_intelligence.py
    Stage 2  LLMMutationEngine             engine/mutation_engine.py
    Stage 3  ParallelExecutionOrchestrator engine/execution_orchestrator.py
    Stage 4  ResultAnalyzer                engine/result_analyzer.py
    Stage 5  AITestSynthesisStage          engine/synthesis_stage.py

    MutationPipelineEngine  (runs all 5)   engine/pipeline_engine.py

Every stage works fully OFFLINE (no Azure, no C build) so the whole pipeline is
demonstrable, while reusing the real Phase-1 / Phase-2 engines when available.
"""

from engine.code_intelligence import (
    CodeIntelligenceEngine,
    CodeIntelligenceResult,
    DependencyGraph,
    TestTrace,
    CoverageGap,
)
from engine.mutation_engine import (
    LLMMutationEngine,
    ScoredMutant,
    MutationBatch,
)
from engine.execution_orchestrator import (
    ParallelExecutionOrchestrator,
    ExecutionJob,
    JobResult,
    ResourceManager,
)
from engine.result_analyzer import ResultAnalyzer, AnalysisResult
from engine.synthesis_stage import AITestSynthesisStage, SynthesisResult
from engine.pipeline_engine import MutationPipelineEngine, PipelineReport

__all__ = [
    "CodeIntelligenceEngine",
    "CodeIntelligenceResult",
    "DependencyGraph",
    "TestTrace",
    "CoverageGap",
    "LLMMutationEngine",
    "ScoredMutant",
    "MutationBatch",
    "ParallelExecutionOrchestrator",
    "ExecutionJob",
    "JobResult",
    "ResourceManager",
    "ResultAnalyzer",
    "AnalysisResult",
    "AITestSynthesisStage",
    "SynthesisResult",
    "MutationPipelineEngine",
    "PipelineReport",
]
