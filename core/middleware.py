import os
import json
from typing import Tuple
from datetime import datetime
from core.function_extractor import extract_functions
from core.testcase_extractor import extract_testcases


def extract_functions_and_tests(function_file_path: str, test_directory: str) -> Tuple[dict, dict, dict]:
    extracted_funcs = extract_functions(function_file_path)
    functions_dict = {f["function_name"]: f["code"] for f in extracted_funcs}
    dependency_dict = functions_dict.copy()

    testcases_json = extract_testcases(function_file_path, test_directory)
    test_cases_dict = {}

    if testcases_json:
        file_key = os.path.basename(function_file_path)
        function_items = testcases_json.get(file_key, [])[0].get("functions", [])
        for func_entry in function_items:
            func_name = func_entry["function_name"]
            testcases_raw = func_entry.get("testcases", "")
            test_cases_dict[func_name] = testcases_raw

    return functions_dict, dependency_dict, test_cases_dict


def persist_all_mutants(all_mutants: dict, output_dir: str):
    structured_output = {}

    for func_name, mutants in all_mutants.items():
        grouped = []
        for idx, mutant in enumerate(mutants, start=1):
            if hasattr(mutant, "dict"):
                m_dict = mutant.dict()
            else:
                m_dict = mutant.copy() if isinstance(mutant, dict) else dict(mutant)

            if "original_code" in m_dict and isinstance(m_dict["original_code"], str):
                m_dict["original_code"] = m_dict["original_code"].strip()
            if "mutated_code" in m_dict and isinstance(m_dict["mutated_code"], str):
                m_dict["mutated_code"] = m_dict["mutated_code"].strip()

            m_dict.pop("id", None)
            m_dict.pop("function_name", None)
            m_dict["mutant_id"] = idx
            m_dict["mutant_category"] = m_dict.get("mutant_category", "Uncategorized")
            grouped.append(m_dict)

        structured_output[func_name] = grouped

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"mutants_{timestamp}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(structured_output, f, indent=2)

    return file_path
