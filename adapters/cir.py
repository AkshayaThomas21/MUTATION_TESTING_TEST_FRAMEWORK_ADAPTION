"""
Common Internal Representation (CIR)
====================================

The CIR is the heart of the Framework-Agnostic Gateway. Every supported test
framework is translated *into* these neutral structures, and every AI engine
(mutation, root-cause, synthesis) reads/writes *only* these structures.

Key innovation: the LLM never sees raw framework syntax (EXPECT_EQ, CHECK_EQUAL,
TEST_ASSERT_EQUAL, assertEqual, ...). It reasons over normalized intent, so a
mutant-killing test generated once can be *rendered* back into any framework.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AssertionType(str, Enum):
    """Framework-neutral assertion intents."""

    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NULL = "NULL"
    NOT_NULL = "NOT_NULL"
    GREATER = "GREATER"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS = "LESS"
    LESS_EQUAL = "LESS_EQUAL"
    NEAR = "NEAR"            # floating point comparison with tolerance
    THROWS = "THROWS"       # exception expected
    NO_THROW = "NO_THROW"
    CALLED = "CALLED"       # mock expectation
    STRING_EQUAL = "STRING_EQUAL"
    UNKNOWN = "UNKNOWN"


class CIRAssertion(BaseModel):
    """A single normalized assertion extracted from a test."""

    type: AssertionType = AssertionType.UNKNOWN
    expected: Optional[str] = None
    actual: Optional[str] = None
    tolerance: Optional[str] = None
    line: Optional[int] = None
    raw: Optional[str] = Field(
        default=None, description="Original framework-specific assertion text (debug only)"
    )


class CIRInput(BaseModel):
    """A normalized input/parameter binding for the unit under test."""

    param: str
    value: str
    type: Optional[str] = None


class CIRTestCase(BaseModel):
    """A normalized test case — the canonical unit the AI reasons about."""

    test_case_id: str
    method_under_test: str
    framework_source: str
    suite: Optional[str] = None
    assertions: List[CIRAssertion] = Field(default_factory=list)
    inputs: List[CIRInput] = Field(default_factory=list)
    file: Optional[str] = None
    line_number: Optional[int] = None
    raw_body: Optional[str] = Field(
        default=None, description="Original test body, kept for rendering / fallback"
    )
    tags: List[str] = Field(default_factory=list)

    def assertion_strength(self) -> float:
        """
        Heuristic 0-100 assertion-strength score used by the Quality Signal Engine.
        Strong: EQUAL / NEAR / THROWS / STRING_EQUAL with explicit expected value.
        Weak: bare TRUE / FALSE / UNKNOWN.
        """
        if not self.assertions:
            return 0.0
        weights = {
            AssertionType.EQUAL: 1.0,
            AssertionType.STRING_EQUAL: 1.0,
            AssertionType.NEAR: 1.0,
            AssertionType.THROWS: 0.95,
            AssertionType.NOT_EQUAL: 0.8,
            AssertionType.GREATER: 0.8,
            AssertionType.GREATER_EQUAL: 0.8,
            AssertionType.LESS: 0.8,
            AssertionType.LESS_EQUAL: 0.8,
            AssertionType.NOT_NULL: 0.6,
            AssertionType.NULL: 0.6,
            AssertionType.CALLED: 0.6,
            AssertionType.TRUE: 0.35,
            AssertionType.FALSE: 0.35,
            AssertionType.NO_THROW: 0.3,
            AssertionType.UNKNOWN: 0.2,
        }
        total = sum(weights.get(a.type, 0.2) for a in self.assertions)
        return round(min(100.0, (total / len(self.assertions)) * 100.0), 1)


class CIRSuite(BaseModel):
    """A normalized collection of test cases for one framework / module."""

    framework_source: str
    module: Optional[str] = None
    test_cases: List[CIRTestCase] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def by_method(self, method: str) -> List[CIRTestCase]:
        clean = method.split("(")[0].strip()
        return [
            tc
            for tc in self.test_cases
            if tc.method_under_test.split("(")[0].strip() == clean
        ]

    def to_json(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class CIRMutant(BaseModel):
    """Framework-neutral mutant record (mirrors src.data_classes.Mutant but enriched)."""

    mutant_id: int
    original_code: str
    mutated_code: str
    mutant_category: str = "Uncategorized"
    confidence_score: int = Field(
        default=50, ge=0, le=100, description="LLM confidence the mutant is non-equivalent"
    )
    status: str = "Unknown"  # Killed / Survived / Equivalent / Build-error / Unknown
    root_cause: Optional[str] = None
    method_under_test: Optional[str] = None
    explanation: Optional[str] = None
