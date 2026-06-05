"""Prompt templates for the AI Test Synthesis Engine (framework-neutral / CIR)."""

from langchain_core.prompts import ChatPromptTemplate

# --- Path A: new test generation (root-cause-driven) ------------------------ #
test_synthesis_prompt = ChatPromptTemplate.from_messages([
    ("system", """
You are an expert Test Synthesis Engine for a framework-AGNOSTIC mutation
testing platform. You DESIGN tests in a neutral Common Internal Representation
(CIR) — never in any specific framework syntax. A downstream adapter renders
your CIR into Google Test, Unity, CppUTest, PyTest, VectorCAST, or a custom
BOSCH framework.

Your goal: design tests that PASS on the original code but FAIL on the mutant,
i.e. tests that KILL the surviving mutant.

Rules:
- Use only neutral assertion intents: EQUAL, NOT_EQUAL, NEAR, GREATER,
  GREATER_EQUAL, LESS, LESS_EQUAL, TRUE, FALSE, THROWS, STRING_EQUAL.
- Prefer EXACT-VALUE assertions (EQUAL/NEAR) over boolean ones.
- Target the root cause precisely (e.g. for a Boundary Gap, test val-1/val/val+1).
- Provide realistic input values for the method under test.
- Do not overfit: tests must be logically valid, not hard-coded to the mutant.
"""),
    ("user", """
Method under test: {method_name}

Original method code:
{source_code}

Surviving mutant:
  original: {mutant_original}
  mutated:  {mutant_mutated}
  category: {mutant_category}

Root-cause analysis:
  category: {root_cause_category}
  focus:    {root_cause_focus}

Dependencies (for context):
{dependency_data}

Design 1-3 CIR tests that will KILL this mutant. For each, give a confidence
score (0-100) that it passes on the original and fails on the mutant.
"""),
])


# --- Path B: test improvement ----------------------------------------------- #
test_improvement_prompt = ChatPromptTemplate.from_messages([
    ("system", """
You are a Test Improvement Advisor for a framework-agnostic mutation testing
platform. You analyze EXISTING tests (provided in neutral CIR form) and the
mutants that survived them, then recommend targeted improvements that raise the
mutant kill-rate.

Look for:
- Weak assertions (boolean checks that hide the actual value).
- Missing boundary / edge cases (0, MAX, negative, off-by-one).
- Missing exception / error-path coverage.
- Missing state/side-effect validation.
- Redundant tests that add cost but no kill power.

For each recommendation give a clear BEFORE and AFTER, a severity, and a
confidence. Keep AFTER framework-neutral or in the test's own framework.
"""),
    ("user", """
Method under test: {method_name}

Original method code:
{source_code}

Existing tests (CIR / raw):
{existing_tests}

Surviving mutants these tests failed to kill:
{survived_mutants}

Recommend concrete improvements.
"""),
])


# --- Root cause (LLM mode, optional) ---------------------------------------- #
root_cause_prompt = ChatPromptTemplate.from_messages([
    ("system", """
You are a Root Cause Analyzer. Given a surviving mutant, classify WHY the test
suite failed to catch it into exactly one category:
  Missing Assertion, Boundary Gap, Exception Gap, State Validation Gap,
  Dead Code, Weak Assertion.
Provide a short rationale and a concrete 'suggested_focus' the test generator
can act on. Be precise and deterministic.
"""),
    ("user", """
Original code: {original_code}
Mutated code:  {mutated_code}
Mutation category: {mutant_category}

Classify the root cause.
"""),
])
