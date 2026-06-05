from src.data_classes import (
    Hints,
    MutationAgentOutput,
    Mutant,
    Feedback
)
from typing import List
import json
import os
from src.data_classes import RankedMutant



def stringify_hints(hints_obj: Hints) -> str:
    if not hints_obj or not hints_obj.hints:
        return "Hints: None"

    output = "Hints:\n"
    for i, hint_obj in enumerate(hints_obj.hints, 1):
        output += f"{i}. {hint_obj.hint}\n"
    return output.strip()


def stringify_mutants(output: MutationAgentOutput) -> str:
    if not output or not output.mutants:
        return "No mutants generated."

    result = "List of Mutants:\n"
    for mutant in output.mutants:
        result += (
            f"Mutant ID: {mutant.id}\n"
            f"  Original Code:\n    {mutant.original_code.strip()}\n"
            f"  Mutated Code:\n    {mutant.mutated_code.strip()}\n"
            + "-" * 40 + "\n"
        )
    return result.strip()


def stringify_mutant_list(mutants: List[Mutant]) -> str:
    if not mutants:
        return "No mutants available."

    result = "Mutants:\n"
    for mutant in mutants:
        result += (
            f"Mutant ID: {mutant.id}\n"
            f"  Original Code:\n    {mutant.original_code.strip()}\n"
            f"  Mutated Code:\n    {mutant.mutated_code.strip()}\n"
            + "-" * 40 + "\n"
        )
    return result.strip()


def stringify_feedback(feedback_obj: Feedback) -> str:
    if not feedback_obj or not feedback_obj.feedback.strip():
        return "Feedback: None"

    return f"Feedback:\n{feedback_obj.feedback.strip()}"


def write_mutant_dict_to_json(global_mutant_dc, file_path: str):
    serializable_dict = {
        "Survived": [mutant.dict() for mutant,_ in global_mutant_dc.get("Survived", [])],
        "Killed": [mutant.dict() for mutant,_ in global_mutant_dc.get("Killed", [])]
    }
    with open(file_path, "w") as f:
        json.dump(serializable_dict, f, indent=4)


def stringify_function_dict(function_dict: dict[str, str]) -> str:
    function_dict.pop("RcvMESG", None)
    if not function_dict:
        return "No functions available."

    output = "Functions and their bodies:\n"
    for func_name, func_body in function_dict.items():
        output += f"\nFunction: {func_name}\n"
        output += f"Body:\n{func_body.strip()}\n"
        output += "-" * 40 + "\n"
    return output.strip()


def stringify_test_cases(test_cases) -> str:
    if isinstance(test_cases, list):
        return "\n\n".join(tc.strip() for tc in test_cases if tc.strip())
    elif isinstance(test_cases, str):
        return test_cases.strip()
    return "No test cases available."


def stringify_test_cases_list(test_cases: List[str]) -> list[str]:
    return [tc.strip() for tc in test_cases if tc.strip()]


def stringify_ranked_mutants(mutants: List[RankedMutant]) -> str:
    if not mutants:
        return "No ranked mutants available."

    result = "Ranked Mutants:\n"
    for idx, mutant in enumerate(mutants, 1):
        result += (
            f"\n--- Mutant #{idx} ---\n"
            f"Original Code:\n{mutant.original_code.strip()}\n\n"
            f"Mutated Code:\n{mutant.mutated_code.strip()}\n\n"
            f"Status: {mutant.status}\n"
            f"Category: {mutant.mutant_category}\n"
            f"Rank: {mutant.rank}\n"
            f"Reason:\n{mutant.reason.strip()}\n"
            + "-" * 50 + "\n"
        )
    return result.strip()
