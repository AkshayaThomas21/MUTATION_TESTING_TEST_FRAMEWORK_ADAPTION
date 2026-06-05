"""Structured (Pydantic) outputs for the AI Test Synthesis Engine."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class GeneratedAssertion(BaseModel):
    type: str = Field(description="Neutral assertion intent, e.g. EQUAL, NEAR, THROWS, GREATER")
    expected: Optional[str] = Field(default=None, description="Expected value")
    actual: Optional[str] = Field(default=None, description="Expression under test, e.g. calc_speed(100)")
    tolerance: Optional[str] = None


class GeneratedCIRTest(BaseModel):
    """A framework-neutral test the AI designs to kill a specific mutant."""

    test_name: str = Field(description="Concise, descriptive test name")
    method_under_test: str
    rationale: str = Field(description="Why this test kills the mutant")
    inputs: List[str] = Field(default_factory=list, description="Input values, in call order")
    assertions: List[GeneratedAssertion] = Field(default_factory=list)
    confidence: int = Field(default=70, ge=0, le=100)


class GeneratedTestBatch(BaseModel):
    tests: List[GeneratedCIRTest] = Field(default_factory=list)


class TestImprovement(BaseModel):
    test_name: str
    weakness: str = Field(description="What is weak: e.g. 'EXPECT_TRUE hides the value', 'no boundary case'")
    recommendation: str = Field(description="Concrete, human-readable improvement")
    before: str = Field(description="Current assertion / snippet")
    after: str = Field(description="Improved assertion / snippet (neutral or native)")
    severity: str = Field(default="medium", description="low | medium | high")
    confidence: int = Field(default=70, ge=0, le=100)


class TestImprovementBatch(BaseModel):
    improvements: List[TestImprovement] = Field(default_factory=list)


class RootCauseOutput(BaseModel):
    category: str = Field(
        description="One of: Missing Assertion, Boundary Gap, Exception Gap, "
        "State Validation Gap, Dead Code, Weak Assertion"
    )
    rationale: str
    suggested_focus: str
    confidence: int = Field(default=70, ge=0, le=100)
