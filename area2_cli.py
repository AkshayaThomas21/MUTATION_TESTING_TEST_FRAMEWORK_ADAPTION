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
import sys
import json
import argparse

# Windows consoles default to cp1252 and crash on box-drawing / star glyphs.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

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


def cmd_pipeline(framework: str, use_llm: bool) -> None:
    """Run the full 5-stage AI-Powered Mutation Testing Pipeline (offline demo)."""
    from engine import MutationPipelineEngine

    engine = MutationPipelineEngine(framework=framework, use_llm=use_llm)
    report = engine.run_demo()
    h = report.headline()
    s1, s2, s4, s5 = report.stage1, report.stage2, report.stage4, report.stage5

    bar = "=" * 70
    print(bar)
    print(f"  AI-POWERED MUTATION TESTING PIPELINE — {framework.upper()}")
    print(bar)
    print("  STAGE 1 · Code Intelligence Engine")
    print(f"    methods           : {len(s1.methods)}  ({', '.join(list(s1.methods)[:4])})")
    print(f"    dependency edges  : {sum(len(v) for v in s1.graph.edges.values())}")
    print(f"    coverage gaps     : {len(s1.gaps)}")
    for g in s1.gaps[:4]:
        print(f"        - {g.method}: {g.reason} (branches={g.branches}, tests={g.covering_tests})")
    print("  STAGE 2 · LLM Mutation Engine")
    print(f"    generated         : {len(s2.mutants) + len(s2.rejected)}")
    print(f"    selected (valid)  : {len(s2.selected)}   rejected (halluc): {len(s2.rejected)}")
    top = s2.selected[:3]
    for m in top:
        print(f"        #{m.priority_rank} {m.method} [{m.category}] conf={m.confidence}")
    print("  STAGE 3 · Parallel Execution Orchestrator")
    print(f"    workers           : {report.resource_summary.get('max_workers')} "
          f"(cpu={report.resource_summary.get('cpu_count')})")
    print(f"    jobs executed     : {len(report.execution_results)}")
    print("  STAGE 4 · Result Analyzer")
    print(f"    mutation score    : {s4.mutation_score}%  "
          f"(killed={s4.killed} survived={s4.survived} equiv={s4.equivalent})")
    print(f"    coverage delta    : {s4.coverage_delta}   exec time: {s4.total_time_s}s")
    for sv in s4.survivors[:4]:
        print(f"        survivor {sv.method}#{sv.mutant_id} -> {sv.root_cause}")
    print("  STAGE 5 · AI Test Synthesis Engine")
    print(f"    tests generated   : {len(s5.tests)}   accepted: {len(s5.accepted)}   "
          f"needs review: {sum(1 for t in s5.tests if t.needs_review)}")
    print(f"    integrated file   : {s5.integrated_path}")
    print(bar)
    print(f"  HEADLINE  score={h['mutation_score']}%  gaps={h['coverage_gaps']}  "
          f"new-tests={h['tests_accepted']}/{h['tests_generated']}")
    print(bar)

    os.makedirs("temp", exist_ok=True)
    out = os.path.join("temp", "pipeline_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"  Wrote {out}")
    print(bar)


def cmd_wow(framework: str, project: str, target_asil: str, use_llm: bool, no_open: bool) -> None:
    """Run the full pipeline, then generate + open the MutaSentinel briefing."""
    from engine import MutationPipelineEngine
    from wow import generate_briefing

    engine = MutationPipelineEngine(framework=framework, use_llm=use_llm)
    report = engine.run_demo()
    out = generate_briefing(report, project=project, target_asil=target_asil)
    s = out["safety"]
    sb = out["safety_before"]

    bar = "=" * 70
    print(bar)
    print("  \u25c8 MUTASENTINEL \u2014 ASIL-Aware Mutation Intelligence")
    print(bar)
    print(f"  Project        : {project}  [{framework.upper()}]")
    print(f"  Mutation score : {out['baseline_score']}%  ->  {out['projected_score']}%  (after AI self-heal)")
    print(f"  Safety (SCI)   : {sb['safety_confidence_index']}%  ->  {s['safety_confidence_index']}%   "
          f"target ASIL {s['target_asil']}")
    print(f"  ASIL readiness : {sb['achieved_asil']}  ->  {s['achieved_asil']}  (after AI self-heal)")
    print(f"  Verdict        : {s['verdict']}")
    print(f"  Blind spots    : {len(s['blind_spots'])}  "
          f"({s['critical_count']} critical, {s['high_count']} high)")
    print(f"  Risk mitigated : EUR {out['roi']['risk_mitigated_eur']:,.0f}   "
          f"net value EUR {out['roi']['net_value_eur']:,.0f}   payback {out['roi']['payback_ratio']}x")
    print(f"  Test genome    : {out['genome']['fingerprint']}  (dominant: {out['genome']['dominant']})")
    print(bar)
    print(f"  Briefing       : {out['path']}")
    print(bar)

    if not no_open:
        import webbrowser
        webbrowser.open("file:///" + out["path"].replace(chr(92), "/"))
        print("  Opened in your browser.")


def cmd_all(framework: str, project: str, target_asil: str, use_llm: bool, no_open: bool) -> None:
    """Run EVERY offline pipeline end-to-end in a single command.

    Sequence: list adapters -> quality report (--demo) -> 5-stage pipeline
    (--pipeline) -> MutaSentinel ASIL/ROI briefing (--wow).
    """
    bar = "#" * 70
    print(bar)
    print(f"  RUN-ALL  |  framework={framework.upper()}  llm={'on' if use_llm else 'off'}")
    print(bar)

    print("\n>>> [1/4] Framework-Agnostic Gateway\n")
    cmd_list_frameworks()

    print("\n>>> [2/4] Quality Report (offline demo)\n")
    cmd_demo(framework, project)

    print("\n>>> [3/4] Full 5-Stage AI Pipeline\n")
    cmd_pipeline(framework, use_llm)

    print("\n>>> [4/4] MutaSentinel ASIL/ROI Briefing\n")
    cmd_wow(framework, project, target_asil, use_llm, no_open)

    print("\n" + bar)
    print("  RUN-ALL COMPLETE  ->  temp/quality_report.json, temp/pipeline_report.json")
    print("  View the dashboard:  streamlit run dashboard/app.py")
    print(bar)


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
    p.add_argument("--pipeline", action="store_true",
                   help="run the full 5-stage AI-powered mutation testing pipeline (offline)")
    p.add_argument("--wow", action="store_true",
                   help="run the pipeline + generate the MutaSentinel ASIL/ROI briefing (HTML)")
    p.add_argument("--all", action="store_true",
                   help="run EVERY offline pipeline in one go (gateway + demo + 5-stage + briefing)")
    p.add_argument("--target-asil", default="D", choices=["A", "B", "C", "D"],
                   help="ISO 26262 ASIL target for the safety verdict (default D)")
    p.add_argument("--no-open", action="store_true", help="do not auto-open the briefing in a browser")
    p.add_argument("--framework", default="gtest")
    p.add_argument("--tests", nargs="*", default=[])
    p.add_argument("--source", default="")
    p.add_argument("--project", default="Demo Project")
    p.add_argument("--no-llm", action="store_true", help="disable LLM (heuristic only)")
    args = p.parse_args()

    if args.all:
        cmd_all(args.framework, args.project, args.target_asil, not args.no_llm, args.no_open)
    elif args.list_frameworks:
        cmd_list_frameworks()
    elif args.parse:
        cmd_parse(args.framework, args.tests, args.source)
    elif args.pipeline:
        cmd_pipeline(args.framework, not args.no_llm)
    elif args.wow:
        cmd_wow(args.framework, args.project, args.target_asil, not args.no_llm, args.no_open)
    elif args.from_temp:
        cmd_from_temp(args.framework, args.source, args.project, not args.no_llm)
    elif args.demo:
        cmd_demo(args.framework, args.project)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
