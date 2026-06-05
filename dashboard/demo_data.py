"""
Self-contained demo / simulation data for the dashboard.

Lets the WHOLE platform be demoed (the 2-minute video) with ZERO Azure
credentials and no real C build — while using the *real* CIR, adapters,
root-cause analyzer, and quality engine code paths.
"""

from __future__ import annotations

from typing import Dict, Any, List

from adapters import get_registry
from adapters.cir import CIRTestCase, CIRAssertion, CIRInput, AssertionType
from quality.metrics import (
    MutationMetrics, TestQualityMetrics, AIPerformanceMetrics, ExecutionMetrics,
)
from quality.signal_engine import QualitySignalEngine
from quality.cicd_gate import CICDGate
from quality.root_cause import RootCauseAnalyzer


# A realistic embedded BOSCH-style function under test.
SAMPLE_SOURCE = {
    "CheckSpeedLimit": (
        "int CheckSpeedLimit(int speed, int limit) {\n"
        "    if (speed > limit) {\n"
        "        return STATUS_OVER_LIMIT;\n"
        "    }\n"
        "    if (speed < 0) {\n"
        "        return STATUS_INVALID;\n"
        "    }\n"
        "    return STATUS_OK;\n"
        "}"
    ),
    "ComputeTorque": (
        "float ComputeTorque(float rpm, float load) {\n"
        "    float t = (rpm * load) / 100.0f;\n"
        "    if (t > MAX_TORQUE) t = MAX_TORQUE;\n"
        "    return t;\n"
        "}"
    ),
}

SAMPLE_MUTANTS: Dict[str, List[dict]] = {
    "CheckSpeedLimit": [
        {"mutant_id": 1, "original_code": "if (speed > limit) {", "mutated_code": "if (speed >= limit) {",
         "mutant_category": "Relational Operator Replacement", "status": "Survived", "confidence_score": 88},
        {"mutant_id": 2, "original_code": "if (speed < 0) {", "mutated_code": "if (speed <= 0) {",
         "mutant_category": "Boundary", "status": "Survived", "confidence_score": 81},
        {"mutant_id": 3, "original_code": "return STATUS_OVER_LIMIT;", "mutated_code": "return STATUS_OK;",
         "mutant_category": "Return Value Change", "status": "Killed", "confidence_score": 92},
        {"mutant_id": 4, "original_code": "return STATUS_INVALID;", "mutated_code": "return STATUS_OK;",
         "mutant_category": "Return Value Change", "status": "Killed", "confidence_score": 90},
        {"mutant_id": 5, "original_code": "if (speed > limit) {", "mutated_code": "if (speed > limit + 1) {",
         "mutant_category": "Constant Replacement", "status": "Survived", "confidence_score": 79},
    ],
    "ComputeTorque": [
        {"mutant_id": 1, "original_code": "float t = (rpm * load) / 100.0f;", "mutated_code": "float t = (rpm + load) / 100.0f;",
         "mutant_category": "Arithmetic Operator Replacement", "status": "Killed", "confidence_score": 86},
        {"mutant_id": 2, "original_code": "if (t > MAX_TORQUE) t = MAX_TORQUE;", "mutated_code": "if (t >= MAX_TORQUE) t = MAX_TORQUE;",
         "mutant_category": "Relational Operator Replacement", "status": "Survived", "confidence_score": 83},
        {"mutant_id": 3, "original_code": "return t;", "mutated_code": "return t * 1.0f;",
         "mutant_category": "Equivalent", "status": "Equivalent", "confidence_score": 20},
    ],
}


def _sample_cir_tests() -> List[CIRTestCase]:
    return [
        CIRTestCase(
            test_case_id="SpeedSuite.OverLimit", method_under_test="CheckSpeedLimit",
            framework_source="gtest", suite="SpeedSuite",
            inputs=[CIRInput(param="speed", value="120"), CIRInput(param="limit", value="100")],
            assertions=[CIRAssertion(type=AssertionType.EQUAL, expected="STATUS_OVER_LIMIT",
                                     actual="CheckSpeedLimit(120, 100)")],
            raw_body="EXPECT_EQ(STATUS_OVER_LIMIT, CheckSpeedLimit(120, 100));",
        ),
        CIRTestCase(
            test_case_id="SpeedSuite.Valid", method_under_test="CheckSpeedLimit",
            framework_source="gtest", suite="SpeedSuite",
            inputs=[CIRInput(param="speed", value="50"), CIRInput(param="limit", value="100")],
            assertions=[CIRAssertion(type=AssertionType.TRUE, actual="CheckSpeedLimit(50, 100) == STATUS_OK")],
            raw_body="EXPECT_TRUE(CheckSpeedLimit(50, 100) == STATUS_OK);",  # intentionally weak
        ),
    ]


def build_demo_result(framework: str = "gtest", project: str = "Powertrain ECU Module") -> Dict[str, Any]:
    """Run the REAL engines on simulated mutation results -> full dashboard payload."""
    registry = get_registry()
    try:
        adapter = registry.get(framework)
    except KeyError:
        adapter = registry.get("gtest")

    engine = QualitySignalEngine()
    gate = CICDGate()
    rca = RootCauseAnalyzer(use_llm=False)
    cir_tests = _sample_cir_tests()

    mutation = MutationMetrics(previous_score=62.0)
    survived_records: List[Dict[str, Any]] = []
    synthesis: List[Dict[str, Any]] = []

    for method, mutants in SAMPLE_MUTANTS.items():
        strength = (
            round(sum(t.assertion_strength() for t in cir_tests if t.method_under_test == method)
                  / max(1, len([t for t in cir_tests if t.method_under_test == method])), 1)
        )
        for mut in mutants:
            status = mut["status"].lower()
            if status == "killed":
                mutation.killed += 1
            elif status == "survived":
                mutation.survived += 1
                rc = rca.analyze(mut["original_code"], mut["mutated_code"], mut["mutant_category"], strength)
                survived_records.append({**mut, "method": method, "root_cause": rc.category.value,
                                         "root_cause_focus": rc.suggested_focus, "rca_confidence": rc.confidence})
                synthesis.append(_demo_synthesis_for(adapter, method, mut, rc))
            elif status == "equivalent":
                mutation.equivalent += 1
            else:
                mutation.build_error += 1

    # bump killed to reflect "after AI generation" headline number
    mutation.killed = 7  # 5 original kills + 2 newly generated kills, illustrative

    test_quality = TestQualityMetrics(
        coverage_impact=15.0, effectiveness=82.0, flakiness_rate=1.8,
        redundancy=12.0, assertion_strength=round(
            sum(t.assertion_strength() for t in cir_tests) / len(cir_tests), 1),
    )
    ai = AIPerformanceMetrics(
        tests_generated=150, accepted=117, hallucinations=5, avg_confidence=84.0,
        input_tokens=1_900_000, output_tokens=500_000, cost_usd=12.50,
    )
    execution = ExecutionMetrics(
        total_runs=5000, total_time_s=510.0, parallel_efficiency=92.0,
        cpu_utilization=78.0, memory_utilization=65.0, failed_runs=40,
    )

    report = engine.aggregate(project, adapter.capabilities.name, mutation, test_quality, ai, execution,
                              survived_mutants=survived_records)
    decision = gate.evaluate(report)

    improvements = [
        {"test_name": "SpeedSuite.Valid", "weakness": "EXPECT_TRUE hides the returned status value.",
         "recommendation": "Use exact equality on the status and add boundary cases.",
         "before": "EXPECT_TRUE(CheckSpeedLimit(50, 100) == STATUS_OK);",
         "after": "EXPECT_EQ(STATUS_OK, CheckSpeedLimit(50, 100));\nEXPECT_EQ(STATUS_OK, CheckSpeedLimit(100, 100));",
         "severity": "high", "confidence": 88, "needs_human_review": False},
        {"test_name": "SpeedSuite.OverLimit", "weakness": "No boundary case at speed == limit.",
         "recommendation": "Add the exact-boundary case to kill the '>' -> '>=' mutant.",
         "before": "EXPECT_EQ(STATUS_OVER_LIMIT, CheckSpeedLimit(120, 100));",
         "after": "EXPECT_EQ(STATUS_OK, CheckSpeedLimit(100, 100));  // boundary",
         "severity": "high", "confidence": 90, "needs_human_review": False},
    ]

    feedback_loop = [
        {"iteration": 0, "mutation_score": 62, "survived": 380, "generated": 0},
        {"iteration": 1, "mutation_score": 79, "survived": 210, "generated": 45},
        {"iteration": 2, "mutation_score": 86, "survived": 140, "generated": 28},
        {"iteration": 3, "mutation_score": 91, "survived": 90, "generated": 15},
    ]

    return {
        "report": report.to_dict(),
        "gate": decision.to_dict(),
        "synthesis": synthesis,
        "improvements": improvements,
        "feedback_loop": feedback_loop,
        "cir_tests": [t.model_dump(mode="json") for t in cir_tests],
        "frameworks": [c.__dict__ for c in registry.capabilities()],
        "source": SAMPLE_SOURCE,
    }


def _demo_synthesis_for(adapter, method: str, mut: dict, rc) -> Dict[str, Any]:
    """Render an AI-designed killing test into the chosen framework (real render path)."""
    import re
    num = None
    m = re.search(r"\b(\d+)\b", mut["original_code"])
    if m:
        num = m.group(1)

    if method == "CheckSpeedLimit" and ">" in mut["mutated_code"]:
        test = CIRTestCase(
            test_case_id=f"{method}_Boundary_Kill", method_under_test=method,
            framework_source=adapter.capabilities.name, suite=f"{method}Suite",
            inputs=[CIRInput(param="speed", value="100"), CIRInput(param="limit", value="100")],
            assertions=[CIRAssertion(type=AssertionType.EQUAL, expected="STATUS_OK",
                                     actual=f"{method}(100, 100)")],
        )
    else:
        test = CIRTestCase(
            test_case_id=f"{method}_Kill", method_under_test=method,
            framework_source=adapter.capabilities.name, suite=f"{method}Suite",
            assertions=[CIRAssertion(type=AssertionType.EQUAL, expected=num or "EXPECTED",
                                     actual=f"{method}(/* args */)")],
        )
    return {
        "method": method, "mutant": mut, "root_cause": rc.category.value,
        "root_cause_focus": rc.suggested_focus,
        "rendered": adapter.render_test(test),
        "cir_test": test.model_dump(mode="json"),
        "framework": adapter.capabilities.name,
        "confidence": mut.get("confidence_score", 80),
        "validated": True,  # passed-on-original + failed-on-mutant
    }
