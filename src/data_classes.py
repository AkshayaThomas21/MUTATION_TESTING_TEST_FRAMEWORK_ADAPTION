#data_classes.py
from typing import Literal, List, Optional
from pydantic import BaseModel, Field


class Mutant(BaseModel):
    id: int = Field(..., description="Unique ID for this mutant")
    original_code: str = Field(..., description="Original line/ part of the code which is to be mutated")
    mutated_code: str = Field(..., description="Mutated code line/part ")
    mutant_category: str  


class MutationAgentOutput(BaseModel):
    mutants: List[Mutant] = Field(..., description="List of Mutants created")


class Feedback(BaseModel):
    feedback: str = Field(..., description="A feedback message for Mutant Generator Agent if any improvement is required in the Mutants")


class GenTestCases(BaseModel):
    gen_test_cases: List[str] = None  


class Hint(BaseModel):
    hint: str = Field(description="Hints after Analyzing the testcases to help the Mutant Generator agent to make better Mutants.")


class Hints(BaseModel):
    hints: List[Hint] = None


class IsEquivalent(BaseModel):
    is_equivalent_mutant: Literal["Equivalent", "Not Equivalent"] = Field(
        ..., description="Generated Mutant is an Equivalent Mutant or not"
    )


class MutantGenAgentState(BaseModel):
    function_code: str
    mutation_result: Optional[MutationAgentOutput] = None
    feedback: Optional[Feedback] = None
    test_case_hints: Optional[Hints] = None
    test_case_data: List[str]  # raw string list
    super_step_count: int = 0
    survived_mutants: List[Mutant] = None
    killed_mutants: List[Mutant] = None
    ratings_summary: str
    dependency_data: dict = None
    context_summary: str = ""
    source_code: str = ""

class TestGenAgentState(BaseModel):
    function_code: str
    survived_mutants: List[Mutant]
    test_case_data: List[str]  # raw string
    generated_test_case: GenTestCases = None
    dependency_data: dict = None


class EquivalentCheckAgentState(BaseModel):
    function_code: str
    generated_mutants: List[Mutant]
    dependency_data: dict = None
    filtered_mutants: List[Mutant] = None


class EquivalentCheckerOutputModel(BaseModel):
    is_equivalent_mutant: Literal["Equivalent", "Not Equivalent"] = Field(
        ..., description="Determines if the mutant is semantically equivalent to the original function"
    )


class RankedMutant(BaseModel):
    original_code: str
    mutated_code: str
    status: str
    mutant_category: str
    rank: int
    reason: Optional[str] = ""  # provides the justification


class RankedMutantsOutput(BaseModel):
    ranked_mutants: List[RankedMutant]


# --- Structured output for Source Analyzer ---
class SourceAnalyzerOutputModel(BaseModel):
    context_summary: str


class HallucinationResult(BaseModel):
    is_hallucination: Literal["Hallucination", "No Hallucination"] = Field(
        ..., description="Marks whether the mutant appears to be a hallucination"
    )
    explanation: str = Field(..., description="Short explanation for the judgment")
