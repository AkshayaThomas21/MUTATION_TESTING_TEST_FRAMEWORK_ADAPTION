"""
Quality Signal Engine (Area 2 — Module 7).

Aggregates four metric quadrants into a single, framework-agnostic quality
index, drives the developer dashboard, and powers automated CI/CD gates.
"""

from quality.metrics import (
    MutationMetrics,
    TestQualityMetrics,
    AIPerformanceMetrics,
    ExecutionMetrics,
    QualityReport,
)
from quality.root_cause import RootCauseAnalyzer, RootCauseCategory
from quality.signal_engine import QualitySignalEngine
from quality.cicd_gate import CICDGate, GateDecision, GateThresholds

__all__ = [
    "MutationMetrics",
    "TestQualityMetrics",
    "AIPerformanceMetrics",
    "ExecutionMetrics",
    "QualityReport",
    "RootCauseAnalyzer",
    "RootCauseCategory",
    "QualitySignalEngine",
    "CICDGate",
    "GateDecision",
    "GateThresholds",
]
