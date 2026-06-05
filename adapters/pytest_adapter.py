"""PyTest adapter — Python unit testing (also covers plain assert-style tests)."""

from __future__ import annotations

import ast
import os
from typing import List

from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.cir import CIRSuite, CIRTestCase, CIRAssertion, AssertionType


class PyTestAdapter(BaseAdapter):
    capabilities = AdapterCapabilities(
        name="pytest",
        language="python",
        file_globs=["test_*.py", "*_test.py"],
        supports_coverage=True,
        supports_mocking=True,
        supports_xml_report=True,
        description="PyTest / unittest for Python.",
        maturity="stable",
    )

    def extract_functions(self, source_file: str) -> List[dict]:
        """Python AST parse (overrides the default C tree-sitter parser)."""
        with open(source_file, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read()
        funcs = []
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return funcs
        lines = src.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seg = "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])
                funcs.append({"function_name": node.name, "code": seg})
        return funcs

    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        suite = CIRSuite(framework_source="pytest")
        for tf in test_files:
            if not os.path.exists(tf):
                continue
            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                src = f.read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            lines = src.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                    body = "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])
                    suite.test_cases.append(
                        CIRTestCase(
                            test_case_id=node.name,
                            method_under_test=self._guess_method(node),
                            framework_source="pytest",
                            assertions=self._extract_assertions(node),
                            file=os.path.basename(tf),
                            line_number=node.lineno,
                            raw_body=body,
                        )
                    )
        return suite

    @staticmethod
    def _guess_method(node: ast.FunctionDef) -> str:
        for n in ast.walk(node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                if n.func.id not in {"assert", "pytest", "len", "isinstance"}:
                    return n.func.id
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                return n.func.attr
        return node.name.replace("test_", "")

    def _extract_assertions(self, node: ast.FunctionDef) -> List[CIRAssertion]:
        out: List[CIRAssertion] = []
        for n in ast.walk(node):
            if isinstance(n, ast.Assert):
                out.append(self._classify_assert(n))
        return out

    @staticmethod
    def _classify_assert(node: ast.Assert) -> CIRAssertion:
        test = node.test
        try:
            if isinstance(test, ast.Compare) and test.ops:
                op = test.ops[0]
                left = ast.unparse(test.left)
                right = ast.unparse(test.comparators[0])
                mapping = {
                    ast.Eq: AssertionType.EQUAL,
                    ast.NotEq: AssertionType.NOT_EQUAL,
                    ast.Gt: AssertionType.GREATER,
                    ast.GtE: AssertionType.GREATER_EQUAL,
                    ast.Lt: AssertionType.LESS,
                    ast.LtE: AssertionType.LESS_EQUAL,
                }
                atype = mapping.get(type(op), AssertionType.UNKNOWN)
                return CIRAssertion(type=atype, actual=left, expected=right, raw=ast.unparse(node))
            return CIRAssertion(type=AssertionType.TRUE, actual=ast.unparse(test), raw=ast.unparse(node))
        except Exception:
            return CIRAssertion(type=AssertionType.UNKNOWN, raw="assert")

    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        import sys
        import subprocess
        import time

        start = time.time()
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", workspace_path],
            capture_output=True, text=True, check=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        import re as _re
        m = _re.search(r"(\d+) passed", out)
        f = _re.search(r"(\d+) failed", out)
        succeeded = int(m.group(1)) if m else 0
        failed = int(f.group(1)) if f else 0
        return ExecutionResult(
            passed=failed == 0 and succeeded > 0,
            total=succeeded + failed,
            succeeded=succeeded,
            failed=failed,
            duration_s=round(time.time() - start, 2),
            raw_log=out,
        )

    def render_test(self, cir_test) -> str:
        import re

        name = cir_test.test_case_id if cir_test.test_case_id.startswith("test") else f"test_{cir_test.test_case_id}"
        name = re.sub(r"\W+", "_", name)
        lines = [f"def {name}():"]
        if not cir_test.assertions:
            lines.append("    pass")
        for a in cir_test.assertions:
            actual = a.actual or f"{cir_test.method_under_test}()"
            mapping = {
                AssertionType.EQUAL: f"    assert {actual} == {a.expected}",
                AssertionType.NOT_EQUAL: f"    assert {actual} != {a.expected}",
                AssertionType.GREATER: f"    assert {actual} > {a.expected}",
                AssertionType.GREATER_EQUAL: f"    assert {actual} >= {a.expected}",
                AssertionType.LESS: f"    assert {actual} < {a.expected}",
                AssertionType.TRUE: f"    assert {actual}",
                AssertionType.FALSE: f"    assert not {actual}",
                AssertionType.NEAR: f"    assert abs({actual} - {a.expected}) < {a.tolerance or '1e-6'}",
            }
            lines.append(mapping.get(a.type, f"    assert {actual} == {a.expected}"))
        return "\n".join(lines)
