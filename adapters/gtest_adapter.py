"""Google Test adapter — wraps the existing GTest pipeline behind the CIR contract."""

from __future__ import annotations

import os
import re
from typing import List, Dict, Any

from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.cir import CIRSuite, CIRTestCase, AssertionType
from adapters.assertion_rules import body_after, extract_assertions

_TEST_HEADER = re.compile(r"\bTEST(?:_F|_P)?\s*\(\s*(?P<suite>\w+)\s*,\s*(?P<name>\w+)\s*\)")


class GTestAdapter(BaseAdapter):
    capabilities = AdapterCapabilities(
        name="gtest",
        language="cpp",
        file_globs=["*.cpp", "*test*.cc", "*_test.cc"],
        supports_coverage=True,
        supports_mocking=True,
        supports_xml_report=True,
        description="Google Test / Google Mock for C/C++ (reference adapter).",
        maturity="stable",
    )

    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        suite = CIRSuite(framework_source="gtest")
        for tf in test_files:
            if not os.path.exists(tf):
                continue
            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for m in _TEST_HEADER.finditer(content):
                name, gsuite = m.group("name"), m.group("suite")
                body = body_after(content, m.end() - 1)
                mut = self._guess_method(body) or name
                suite.test_cases.append(
                    CIRTestCase(
                        test_case_id=f"{gsuite}.{name}",
                        method_under_test=mut,
                        framework_source="gtest",
                        suite=gsuite,
                        assertions=extract_assertions(body, "gtest"),
                        file=os.path.basename(tf),
                        raw_body=body.strip(),
                    )
                )
        return suite

    @staticmethod
    def _guess_method(body: str) -> str:
        m = re.search(r"EXPECT_\w+\s*\([^,]*?\b(\w+)\s*\(", body) or re.search(r"=\s*(\w+)\s*\(", body)
        return m.group(1) if m else ""

    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        from orchestrator import run_script_in_workspace  # late import avoids cycle

        return run_script_in_workspace(
            workspace_path,
            kwargs.get("script_path"),
            kwargs.get("test_target"),
            framework="gtest",
        )

    def get_coverage(self, workspace_path: str, **kwargs) -> Dict[str, Any]:
        return {"line_coverage": 0.0, "branch_coverage": 0.0, "covered_lines": []}

    def render_test(self, cir_test) -> str:
        suite = cir_test.suite or "MutationSuite"
        name = re.sub(r"\W+", "_", cir_test.test_case_id) or "GeneratedTest"
        lines = [f"TEST_F({suite}, {name}) {{"]
        for a in cir_test.assertions:
            lines.append("    " + self._render_assertion(a, cir_test.method_under_test))
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _render_assertion(a, method: str) -> str:
        actual = a.actual or f"{method}(/* args */)"
        mapping = {
            AssertionType.EQUAL: f"EXPECT_EQ({a.expected}, {actual});",
            AssertionType.NOT_EQUAL: f"EXPECT_NE({a.expected}, {actual});",
            AssertionType.STRING_EQUAL: f"EXPECT_STREQ({a.expected}, {actual});",
            AssertionType.NEAR: f"EXPECT_NEAR({a.expected}, {actual}, {a.tolerance or '1e-6'});",
            AssertionType.GREATER: f"EXPECT_GT({actual}, {a.expected});",
            AssertionType.GREATER_EQUAL: f"EXPECT_GE({actual}, {a.expected});",
            AssertionType.LESS: f"EXPECT_LT({actual}, {a.expected});",
            AssertionType.LESS_EQUAL: f"EXPECT_LE({actual}, {a.expected});",
            AssertionType.TRUE: f"EXPECT_TRUE({actual});",
            AssertionType.FALSE: f"EXPECT_FALSE({actual});",
            AssertionType.THROWS: f"EXPECT_ANY_THROW({actual});",
        }
        return mapping.get(a.type, f"EXPECT_EQ({a.expected}, {actual});")
