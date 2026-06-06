"""
Stage 1 — Code Intelligence Engine.

Parses source into structure, maps relationships, traces which tests cover which
methods, and finds coverage gaps. Works on a plain {method: code} dict so it runs
offline; falls back to the tree-sitter / AST extractors when given raw files.

Components:
    ASTParser / MethodExtractor   -> reuse core.function_extractor (C) + ast (py)
    DependencyGraphBuilder        -> call-edge graph between methods (NEW)
    TestTracer                    -> method -> covering tests map (NEW)
    CoverageAnalyzer              -> untested methods + weakly-tested branches (NEW)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any

# Words that look like calls but are control-flow / keywords, not methods.
_NON_CALLS = {
    "if", "for", "while", "switch", "return", "sizeof", "case", "do", "else",
    "and", "or", "not", "assert", "print", "len", "range", "int", "float",
    "char", "void", "static", "const", "struct", "enum", "typedef",
}
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_BRANCH_RE = re.compile(r"\b(if|else\s+if|for|while|case|\?\s*:|&&|\|\|)\b")


@dataclass
class DependencyGraph:
    """Directed call graph: edges[a] = {callees of a}; reverse[b] = {callers of b}."""

    nodes: List[str] = field(default_factory=list)
    edges: Dict[str, List[str]] = field(default_factory=dict)        # caller -> callees
    reverse: Dict[str, List[str]] = field(default_factory=dict)      # callee -> callers

    def callees(self, method: str) -> List[str]:
        return self.edges.get(method, [])

    def callers(self, method: str) -> List[str]:
        return self.reverse.get(method, [])

    def fan_out(self, method: str) -> int:
        return len(self.edges.get(method, []))

    def fan_in(self, method: str) -> int:
        return len(self.reverse.get(method, []))

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": self.nodes, "edges": self.edges, "reverse": self.reverse}


@dataclass
class TestTrace:
    """Which tests exercise which methods (and the inverse)."""

    method_to_tests: Dict[str, List[str]] = field(default_factory=dict)
    test_to_methods: Dict[str, List[str]] = field(default_factory=dict)

    def covering_tests(self, method: str) -> List[str]:
        return self.method_to_tests.get(method, [])

    def to_dict(self) -> Dict[str, Any]:
        return {"method_to_tests": self.method_to_tests, "test_to_methods": self.test_to_methods}


@dataclass
class CoverageGap:
    method: str
    reason: str            # "untested" | "weak-branch-coverage" | "no-assertion"
    branches: int = 0
    covering_tests: int = 0
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class CodeIntelligenceResult:
    methods: Dict[str, str]
    graph: DependencyGraph
    trace: TestTrace
    gaps: List[CoverageGap]
    branch_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "methods": list(self.methods.keys()),
            "dependency_graph": self.graph.to_dict(),
            "test_trace": self.trace.to_dict(),
            "coverage_gaps": [g.to_dict() for g in self.gaps],
            "branch_counts": self.branch_counts,
        }


class DependencyGraphBuilder:
    """Builds a call graph by scanning each method body for calls to other methods."""

    def build(self, methods: Dict[str, str]) -> DependencyGraph:
        names = set(methods.keys())
        # Normalize keys so "foo(int a)" and "foo" both resolve to "foo".
        short = {n.split("(")[0].strip(): n for n in names}
        graph = DependencyGraph(nodes=sorted(short.keys()))
        for caller, code in methods.items():
            caller_s = caller.split("(")[0].strip()
            callees: Set[str] = set()
            for m in _CALL_RE.finditer(code):
                callee = m.group(1)
                if callee in _NON_CALLS or callee == caller_s:
                    continue
                if callee in short:
                    callees.add(callee)
            graph.edges[caller_s] = sorted(callees)
            for c in callees:
                graph.reverse.setdefault(c, [])
                if caller_s not in graph.reverse[c]:
                    graph.reverse[c].append(caller_s)
        for n in graph.nodes:
            graph.edges.setdefault(n, [])
            graph.reverse.setdefault(n, [])
        return graph


class TestTracer:
    """
    Maps tests to the methods they exercise. Accepts either a CIR suite (preferred,
    uses method_under_test) or raw test code snippets (scans for method names).
    """

    def trace(
        self,
        methods: Dict[str, str],
        cir_suite: Optional[Any] = None,
        raw_tests: Optional[Dict[str, str]] = None,
    ) -> TestTrace:
        short_names = {n.split("(")[0].strip() for n in methods}
        trace = TestTrace()

        if cir_suite is not None and getattr(cir_suite, "test_cases", None):
            for tc in cir_suite.test_cases:
                mut = (tc.method_under_test or "").split("(")[0].strip()
                hit = {mut} if mut in short_names else set()
                # also catch helper calls referenced in the body
                if tc.raw_body:
                    for m in _CALL_RE.finditer(tc.raw_body):
                        if m.group(1) in short_names:
                            hit.add(m.group(1))
                trace.test_to_methods[tc.test_case_id] = sorted(hit)
                for h in hit:
                    trace.method_to_tests.setdefault(h, []).append(tc.test_case_id)

        if raw_tests:
            for test_id, code in raw_tests.items():
                hit = {n for n in short_names if re.search(rf"\b{re.escape(n)}\s*\(", code)}
                trace.test_to_methods.setdefault(test_id, [])
                trace.test_to_methods[test_id] = sorted(set(trace.test_to_methods[test_id]) | hit)
                for h in hit:
                    trace.method_to_tests.setdefault(h, []).append(test_id)

        for n in short_names:
            trace.method_to_tests.setdefault(n, [])
        return trace


class CoverageAnalyzer:
    """Finds coverage gaps: untested methods and methods whose branches outnumber tests."""

    def analyze(
        self, methods: Dict[str, str], trace: TestTrace
    ) -> tuple[List[CoverageGap], Dict[str, int]]:
        gaps: List[CoverageGap] = []
        branch_counts: Dict[str, int] = {}
        for full, code in methods.items():
            name = full.split("(")[0].strip()
            branches = len(_BRANCH_RE.findall(code))
            branch_counts[name] = branches
            covering = len(trace.covering_tests(name))
            if covering == 0:
                gaps.append(CoverageGap(name, "untested", branches, 0, severity="high"))
            elif branches >= 2 and covering < max(2, branches // 2):
                gaps.append(
                    CoverageGap(name, "weak-branch-coverage", branches, covering, severity="medium")
                )
        return gaps, branch_counts


class CodeIntelligenceEngine:
    """Stage 1 façade — runs the four sub-components and returns one result."""

    def __init__(self) -> None:
        self.dep_builder = DependencyGraphBuilder()
        self.tracer = TestTracer()
        self.coverage = CoverageAnalyzer()

    # -- AST / Method extraction (file-based, optional) ----------------- #
    @staticmethod
    def extract_methods_from_file(source_file: str, language: str = "c") -> Dict[str, str]:
        """Use the real AST extractors. Lazy imports keep the offline path light."""
        if language == "python":
            import ast

            with open(source_file, "r", encoding="utf-8", errors="ignore") as f:
                src = f.read()
            out: Dict[str, str] = {}
            lines = src.splitlines()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[node.name] = "\n".join(
                        lines[node.lineno - 1 : (node.end_lineno or node.lineno)]
                    )
            return out
        from core.function_extractor import extract_functions

        return {fn["function_name"]: fn["code"] for fn in extract_functions(source_file)}

    # -- main entry ----------------------------------------------------- #
    def analyze(
        self,
        methods: Dict[str, str],
        cir_suite: Optional[Any] = None,
        raw_tests: Optional[Dict[str, str]] = None,
    ) -> CodeIntelligenceResult:
        graph = self.dep_builder.build(methods)
        trace = self.tracer.trace(methods, cir_suite=cir_suite, raw_tests=raw_tests)
        gaps, branch_counts = self.coverage.analyze(methods, trace)
        return CodeIntelligenceResult(
            methods=methods, graph=graph, trace=trace, gaps=gaps, branch_counts=branch_counts
        )
