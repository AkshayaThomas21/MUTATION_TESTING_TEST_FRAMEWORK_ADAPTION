"""
Combined mutation pipeline — GTest

"""

import os
import json
import logging
import glob
from datetime import datetime
from typing import List

log = logging.getLogger(__name__)

from core.middleware import extract_functions_and_tests, persist_all_mutants
from core.gtest_runner import GTestMutationRunner, ensure_empty_dir
from src.graph import create_mutant_gen_graph, run_mutant_gen_graph
from src.data_classes import (
    Mutant, EquivalentCheckAgentState, EquivalentCheckerOutputModel,
    HallucinationResult, SourceAnalyzerOutputModel
)
from src.prompts import (
    equivalent_checker_agent_prompt,
    hallucination_agent_prompt,
    source_analyzer_prompt,
)
from src.llm_runnable import create_runnable
from src.agents import EquivalentChecker, HallucinationChecker, SourceAnalyzerAgent
from types import SimpleNamespace


def get_context_summary(file_path: str, is_feedback_run: bool, run_idx: int, func_idx: int) -> str:
    """Run SourceAnalyzerAgent locally to get context summary."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read source file {file_path}: {e}")
        return ""

    ratings_data = None
    if is_feedback_run:
        func_dir = os.path.join("ranked", f"run{run_idx}", f"c{func_idx}")
        local_ratings_path = os.path.join(func_dir, "ratings.json")
        if os.path.exists(local_ratings_path):
            try:
                with open(local_ratings_path, "r", encoding="utf-8") as f:
                    ratings_data = json.load(f)
            except Exception as e:
                print(f"[WARNING] Failed loading {local_ratings_path}: {e}")
        if ratings_data is None:
            intermediate_ratings_path = os.path.join("intermediate", "ratings.json")
            if os.path.exists(intermediate_ratings_path):
                try:
                    with open(intermediate_ratings_path, "r", encoding="utf-8") as f:
                        ratings_data = json.load(f)
                except Exception as e:
                    print(f"[WARNING] Failed loading {intermediate_ratings_path}: {e}")
    else:
        intermediate_ratings_path = os.path.join("intermediate", "ratings.json")
        if os.path.exists(intermediate_ratings_path):
            try:
                with open(intermediate_ratings_path, "r", encoding="utf-8") as f:
                    ratings_data = json.load(f)
            except Exception as e:
                print(f"[WARNING] Failed loading {intermediate_ratings_path}: {e}")

    runnable_chain = (
        create_runnable(prompt=source_analyzer_prompt)
        .get_runnable_with_structured_output(SourceAnalyzerOutputModel)
    )
    agent = SourceAnalyzerAgent(runnable_chain)
    state = SimpleNamespace(function_code=code)
    config = {
        "configurable": {"ratings": ratings_data},
        "feedback_run": is_feedback_run
    }
    result = agent(state, config)
    context_summary = result.get("context_summary", "")

    os.makedirs("intermediate", exist_ok=True)
    with open("intermediate/source_context.json", "w", encoding="utf-8") as f:
        json.dump({"context_summary": context_summary}, f, indent=4)

    print("[INFO] Context summary generated locally.")
    return context_summary


def generate_mutants_locally(function_name, function_code, test_cases,
                             dependency_dict, config, is_feedback_run=False,
                             run_idx=1, func_idx=1):
    """Generate mutants using the LangGraph pipeline."""
    # Save user feedback for reflector agent ( feedback is not fully implemented )
    feedback_path = os.path.join("intermediate", "user_feedback.txt")
    user_fb = ""
    if os.path.exists(feedback_path):
        with open(feedback_path, "r", encoding="utf-8") as f:
            user_fb = f.read().strip()

    os.makedirs("intermediate", exist_ok=True)
    with open(os.path.join("intermediate", "user_feedback.txt"), "w", encoding="utf-8") as f:
        f.write(user_fb)

    if isinstance(test_cases, list):
        test_cases_str = "\n\n".join(test_cases)
    else:
        test_cases_str = str(test_cases)

    mutant_gen_graph = create_mutant_gen_graph()
    survived_mutants = []
    killed_mutants = []

    generated_mutants = run_mutant_gen_graph(
        graph=mutant_gen_graph,
        config=config,
        code=function_code,
        survived_mutants=survived_mutants,
        killed_mutants=killed_mutants,
        test_case_data=[test_cases_str],
        dependency_data=dependency_dict,
        is_feedback_run=is_feedback_run,
        run_idx=run_idx,
        func_idx=func_idx
    )

    # Convert to dicts for easier JSON serialization
    json_mutants = [m.__dict__ if hasattr(m, "__dict__") else (m.dict() if hasattr(m, "dict") else m) for m in generated_mutants]
    return json_mutants


def run_equivalent_checker_locally(function_code, generated_mutants, dependency_data):
    """Run EquivalentChecker agent locally."""
    runnable_chain = create_runnable(
        prompt=equivalent_checker_agent_prompt
    ).get_runnable_with_structured_output(EquivalentCheckerOutputModel)

    equivalent_checker_agent = EquivalentChecker(runnable_chain, "equivalents.json")

    # Convert dicts to Mutant objects if needed
    mutant_objects = []
    for m in generated_mutants:
        if isinstance(m, dict):
            mutant_objects.append(Mutant(**m))
        else:
            mutant_objects.append(m)

    state = EquivalentCheckAgentState(
        function_code=function_code,
        generated_mutants=mutant_objects,
        dependency_data=dependency_data
    )

    result = equivalent_checker_agent(state)
    return result


def run_hallucination_check_locally(function_code, generated_mutants, dependency_data):
    """Run HallucinationChecker agent locally."""
    runnable_chain = create_runnable(
        prompt=hallucination_agent_prompt
    ).get_runnable_with_structured_output(HallucinationResult)

    hallucination_agent = HallucinationChecker(runnable_chain, "hallucinations.json")

    mutant_objects = []
    for m in generated_mutants:
        if isinstance(m, dict):
            mutant_objects.append(Mutant(**m))
        else:
            mutant_objects.append(m)

    state = EquivalentCheckAgentState(
        function_code=function_code,
        generated_mutants=mutant_objects,
        dependency_data=dependency_data
    )

    result = hallucination_agent(state)
    return result


def run_mutation_pipeline(function_file_path: str,
                          test_directory: str,
                          output_dir: str,
                          config: dict,
                          selected_functions: List[str],
                          selected_c_file: str,
                          script_path: str,
                          project_path: str,
                          feedback_run: bool = False,
                          run_idx: int = 1,
                          func_idx: int = None):
    """
    Full mutation pipeline: generate mutants, check equivalence/hallucination,
    clone project, run tests, classify results, generate reports.
    """

    print("=== Extracting Functions and Test Cases ===")
    functions_dict, dependency_dict, test_cases_dict = extract_functions_and_tests(
        function_file_path, test_directory
    )

    feedback_path = os.path.join("intermediate", "user_feedback.txt")
    is_feedback_run = feedback_run or os.path.exists(feedback_path)

    folder = "intermediate" if is_feedback_run else "equivalents"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(folder, exist_ok=True)
    equivalent_file_path = os.path.join(folder, f"equivalents_{timestamp}.json")

    with open(equivalent_file_path, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=4)

    print(f"[INFO] Equivalent mutants file initialized at: {equivalent_file_path}")

    all_mutants_grouped = {}
    function_breakdown = {}
    halluc_files = []

    for idx, func_name in enumerate(selected_functions, start=1):
        actual_idx = func_idx if func_idx is not None else idx

        if func_name not in functions_dict:
            print(f"[WARNING] Function {func_name} not found. Skipping.")
            continue

        print(f"\n=== Processing Function: {func_name} ===")
        function_code = functions_dict[func_name]
        test_cases_raw = test_cases_dict.get(func_name, "")
        test_cases = [tc.strip() for tc in test_cases_raw.split("\n\n") if tc.strip()]
        other_deps = {n: c for n, c in dependency_dict.items() if n != func_name}

        try:
            context_summary = get_context_summary(
                function_file_path, is_feedback_run, run_idx, actual_idx
            )
        except Exception as e:
            print(f"[WARNING] could not get context summary: {e}")
            context_summary = ""

        local_config = dict(config) if config is not None else {}
        local_config["context_summary"] = context_summary

        # --- Generate mutants locally ---
        raw_mutants = generate_mutants_locally(
            function_name=func_name,
            function_code=function_code,
            test_cases=test_cases,
            dependency_dict=other_deps,
            config=local_config,
            is_feedback_run=is_feedback_run,
            run_idx=run_idx,
            func_idx=actual_idx
        )

        if not raw_mutants:
            print(f"[WARNING] No mutants for {func_name}.")
            continue

        print(f"[INFO] Raw mutants for {func_name}: {len(raw_mutants)}")

        # --- Equivalent checking locally ---
        result = run_equivalent_checker_locally(
            function_code=function_code,
            generated_mutants=raw_mutants,
            dependency_data=other_deps
        )

        non_equivalent_mutants = result.get("filtered_mutants", [])
        print(f"[INFO] Non-equivalent mutants for {func_name}: {len(non_equivalent_mutants)}")

        # --- Hallucination checking locally ---
        try:
            halluc_result = run_hallucination_check_locally(
                function_code=function_code,
                generated_mutants=non_equivalent_mutants,
                dependency_data=other_deps
            )
        except Exception as e:
            print(f"[ERROR] Hallucination detection failed for {func_name}: {e}")
            halluc_result = {"filtered_mutants": non_equivalent_mutants, "hallucinations": []}

        hallucinations = halluc_result.get("hallucinations", [])

        os.makedirs("intermediate", exist_ok=True)
        halluc_file = os.path.join("intermediate", f"hallucinations_{func_name}_{timestamp}.json")
        try:
            with open(halluc_file, "w", encoding="utf-8") as hf:
                json.dump({"function_name": func_name, "hallucinations": hallucinations}, hf, indent=2)
            halluc_files.append(halluc_file)
        except Exception as e:
            print(f"[WARNING] Could not save hallucination details: {e}")

        print("Hallucination check complete for %s" % func_name)

        # Convert Mutant objects back to dicts for persistence
        non_eq_dicts = []
        for m in non_equivalent_mutants:
            if hasattr(m, "dict"):
                non_eq_dicts.append(m.dict())
            elif isinstance(m, dict):
                non_eq_dicts.append(m)
            else:
                non_eq_dicts.append(dict(m))

        all_mutants_grouped[func_name] = non_eq_dicts
        function_breakdown[func_name] = len(non_eq_dicts)

    # --- Persist mutants ---
    total_mutants = sum(function_breakdown.values())
    output_path = persist_all_mutants(all_mutants_grouped, output_dir)

    if total_mutants == 0:
        print("[WARNING] No mutants generated for any function.")
        return {
            "output_file": output_path,
            "num_mutants": total_mutants,
            "function_breakdown": function_breakdown
        }

    print(f"\n=== Mutation JSON saved at: {output_path} ===\n")

    # --- Clone pipeline ---
    print("=== Running clone pipeline ===")
    test_target = f"UT_{os.path.splitext(os.path.basename(selected_c_file))[0]}"
    runner = GTestMutationRunner(
        project_path=project_path,
        script_path=script_path,
        test_target=test_target
    )

    runner.full_clone_pipeline(output_path, selected_c_file, rerun=is_feedback_run)

    print("=== Mutation pipeline completed successfully ===")

    # --- Aggregate test results from temp/ JSON reports ---
    total_survived = 0
    total_killed = 0
    total_build_error = 0
    temp_files = glob.glob(os.path.join("temp", "c*.json"))
    for tf in temp_files:
        try:
            with open(tf, "r", encoding="utf-8") as f:
                report = json.load(f)
            total_survived += report.get("survived", 0)
            total_killed += report.get("killed", 0)
            total_build_error += report.get("build_error", 0)
        except Exception as e:
            print(f"[WARNING] Could not read temp report {tf}: {e}")

    tested = total_killed + total_survived
    mutation_score = round((total_killed / tested) * 100, 2) if tested > 0 else 0.0

    report_path = os.path.join("temp", "mutation_report.html")

    return {
        "output_file": output_path,
        "num_mutants": total_mutants,
        "function_breakdown": function_breakdown,
        "survived": total_survived,
        "killed": total_killed,
        "build_error": total_build_error,
        "mutation_score": mutation_score,
        "report_path": report_path
    }
