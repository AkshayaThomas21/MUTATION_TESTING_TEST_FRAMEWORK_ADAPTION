"""
Area-2 CLI — framework-agnostic mutation quality analysis.

Two ways to run:

  # 1. Offline demo (no Azure, no build) — writes temp/quality_report.json
  python area2_cli.py --demo --framework gtest

  # 2. Inspect the gateway: list adapters and normalize tests into CIR
  python area2_cli.py --list-frameworks
  python area2_cli.py --parse --framework gtest --tests path/to/tests.cpp --source path/to/src.c

  # 3. Build a quality report from existing base-pipeline results (temp/c*.json)
  python area2_cli.py --from-temp --framework gtest --source path/to/src.c
"""

from __future__ import annotations

import os
import json
import argparse

from adapters import get_registry


def cmd_list_frameworks() -> None:
    reg = get_registry()
    print(f"\nFramework-Agnostic Gateway — {len(reg.names())} adapters:\n" + "-" * 60)
    for cap in reg.capabilities():
        flags = []
        if cap.supports_coverage:
            flags.append("coverage")
        if cap.supports_mocking:
            flags.append("mock")
        print(f"  {cap.name:<12} [{cap.maturity:<9}] {cap.language:<10} "
              f"{'|'.join(flags):<18} {cap.description}")
    print("-" * 60)
    print("Onboard a new framework: drop a `.md` spec into adapters/specs/ (zero code).\n")


def cmd_parse(framework: str, tests: list, source: str) -> None:
    reg = get_registry()
    adapter = reg.resolve(framework, tests)
    src_code = ""
    if source and os.path.exists(source):
        with open(source, "r", encoding="utf-8", errors="ignore") as f:
            src_code = f.read()
    suite = adapter.parse_tests(src_code, tests)
    print(f"\nNormalized {len(suite.test_cases)} test(s) from '{adapter.capabilities.name}' into CIR:\n")
    print(json.dumps(suite.to_json(), indent=2))


def cmd_demo(framework: str, project: str) -> None:
    from dashboard.demo_data import build_demo_result

    result = build_demo_result(framework, project)
    os.makedirs("temp", exist_ok=True)
    with open(os.path.join("temp", "quality_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    r, g = result["report"], result["gate"]
    print("=" * 64)
    print(f"  QUALITY REPORT — {r['project']} [{r['framework'].upper()}]")
    print("=" * 64)
    print(f"  Quality Index : {r['quality_index']}/100  ({'★'*r['star_rating']})")
    print(f"  Mutation Score: {r['mutation']['mutation_score']}%  "
          f"(killed={r['mutation']['killed']} survived={r['mutation']['survived']} "
          f"equiv={r['mutation']['equivalent']})")
    print(f"  AI Acceptance : {r['ai']['acceptance_rate']}%  | Halluc: {r['ai']['hallucination_rate']}%  "
          f"| Cost: ${r['ai']['cost_usd']}")
    print(f"  Execution     : {r['execution']['total_time_min']}m  | "
          f"parallel {r['execution']['parallel_efficiency']}%  | success {r['execution']['success_rate']}%")
    print("-" * 64)
    print(f"  CI/CD GATE    : {g['badge']}")
    print("-" * 64)
    print("  Insights:")
    for i in r["insights"]:
        print(f"    • {i}")
    print("  Recommendations:")
    for i in r["recommendations"]:
        print(f"    • {i}")
    print("=" * 64)
    print("  Wrote temp/quality_report.json  →  view with: streamlit run dashboard/app.py")
    print("=" * 64)


def cmd_from_temp(framework: str, source: str, project: str, use_llm: bool) -> None:
    from orchestrator import run_area2_from_temp
    from core.function_extractor import extract_functions

    source_by_method = {}
    src_code = ""
    if source and os.path.exists(source):
        with open(source, "r", encoding="utf-8", errors="ignore") as f:
            src_code = f.read()
        for fn in extract_functions(source):
            source_by_method[fn["function_name"]] = fn["code"]
    result = run_area2_from_temp(framework, source_by_method, [], src_code, project, use_llm)
    print(json.dumps(result["report"], indent=2))
    print("\nCI/CD:", result["gate"]["badge"])


def main() -> None:
    p = argparse.ArgumentParser(description="Area-2 framework-agnostic mutation quality CLI")
    p.add_argument("--list-frameworks", action="store_true")
    p.add_argument("--parse", action="store_true")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--from-temp", action="store_true")
    p.add_argument("--framework", default="gtest")
    p.add_argument("--tests", nargs="*", default=[])
    p.add_argument("--source", default="")
    p.add_argument("--project", default="Demo Project")
    p.add_argument("--no-llm", action="store_true", help="disable LLM (heuristic only)")
    args = p.parse_args()

    if args.list_frameworks:
        cmd_list_frameworks()
    elif args.parse:
        cmd_parse(args.framework, args.tests, args.source)
    elif args.from_temp:
        cmd_from_temp(args.framework, args.source, args.project, not args.no_llm)
    elif args.demo:
        cmd_demo(args.framework, args.project)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
