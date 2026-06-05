"""
Main entry point — reads config.yaml, extracts functions, runs mutation pipeline.

Usage:
    python Mutation_Test.py
    python Mutation_Test.py --config path/to/config.yaml
"""

import os
import sys
import json
import argparse
import yaml
from pathlib import Path

from core.function_extractor import extract_functions
from core.gtest_runner import ensure_empty_dir
from pipeline import run_mutation_pipeline


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("mutation", {})


def extract_and_list_functions(source_file: str) -> list:
    if not source_file or not os.path.exists(source_file):
        print(f"[ERROR] Source file '{source_file}' not found.")
        sys.exit(1)

    funcs = extract_functions(source_file)
    return [fn.get("function_name", "").strip() for fn in funcs if fn.get("function_name", "").strip()]


def main():
    parser = argparse.ArgumentParser(description="Mutation Testing Tool (GTest, no UI)")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    config_path = args.config
    if not os.path.exists(config_path):
        print(f"[ERROR] Config file '{config_path}' not found.")
        sys.exit(1)

    mutation_cfg = load_config(config_path)

    project_path = mutation_cfg.get("project_path_folder", "")
    source_file = mutation_cfg.get("source_file", "")
    test_case_folder = mutation_cfg.get("test_case_folder", "")
    output_dir = mutation_cfg.get("output_dir", "mutants_output")
    recursion_limit = mutation_cfg.get("recursion_limit", 2)
    script_path = mutation_cfg.get("script_path", "")

    # Validate paths
    for label, path in [("project_path_folder", project_path),
                        ("source_file", source_file),
                        ("test_case_folder", test_case_folder),
                        ("script_path", script_path)]:
        if not path or not os.path.exists(path):
            print(f"[ERROR] '{label}' path does not exist: {path}")
            sys.exit(1)

    # Extract functions from source file
    print(f"[INFO] Extracting functions from: {source_file}")
    all_functions = extract_and_list_functions(source_file)
    print(f"[INFO] Found {len(all_functions)} functions:")
    print("-" * 40)
    for i, fn in enumerate(all_functions, start=1):
        print(f"  {i} : {fn}")
    print("-" * 40)

    # Let user select functions interactively
    selection = input("Enter function numbers to process (comma-separated, or 'all' for all): ").strip()
    if selection.lower() == "all" or selection == "":
        selected_functions = all_functions
        print(f"[INFO] Processing all {len(selected_functions)} functions.")
    else:
        chosen_indices = []
        for part in selection.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part)
                if 1 <= idx <= len(all_functions):
                    chosen_indices.append(idx)
                else:
                    print(f"[WARNING] Invalid number '{idx}', skipping.")
            else:
                print(f"[WARNING] Invalid input '{part}', skipping.")
        selected_functions = [all_functions[i - 1] for i in chosen_indices]
        if not selected_functions:
            print("[ERROR] No valid functions selected. Exiting.")
            sys.exit(1)
        print(f"[INFO] Selected functions: {selected_functions}")

    # Prepare runtime directories
    ensure_empty_dir("clones")
    ensure_empty_dir("logs")
    ensure_empty_dir("temp")
    os.makedirs("intermediate", exist_ok=True)

    # Build config dict for the graph
    graph_config = {
        "configurable": {
            "recursion_limit": recursion_limit,
        }
    }

    print("=" * 60)
    print("  MUTATION TESTING PIPELINE — GTEST")
    print("=" * 60)
    print(f"  Project:    {project_path}")
    print(f"  Source:     {source_file}")
    print(f"  Tests:      {test_case_folder}")
    print(f"  Script:     {script_path}")
    print(f"  Output:     {output_dir}")
    print(f"  Recursion:  {recursion_limit}")
    print(f"  Functions:  {selected_functions}")
    print("=" * 60)

    result = run_mutation_pipeline(
        function_file_path=source_file,
        test_directory=test_case_folder,
        output_dir=output_dir,
        config=graph_config,
        selected_functions=selected_functions,
        selected_c_file=source_file,
        script_path=script_path,
        project_path=project_path,
    )

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Mutants file:   {result.get('output_file', 'N/A')}")
    print(f"  Total mutants:  {result.get('num_mutants', 0)}")
    for fn, count in result.get("function_breakdown", {}).items():
        print(f"    {fn}: {count} mutants")
    print("-" * 60)
    print(f"  Survived:       {result.get('survived', 0)}")
    print(f"  Killed:         {result.get('killed', 0)}")
    print(f"  Build Error:    {result.get('build_error', 0)}")
    print(f"  Mutation Score: {result.get('mutation_score', 0)}%")
    print("-" * 60)
    print(f"  Results file:   {result.get('report_path', 'temp/mutation_report.html')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
