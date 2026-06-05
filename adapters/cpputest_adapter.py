"""CppUTest adapter — C/C++ unit testing widely used in embedded BOSCH projects."""

from __future__ import annotations

import os
import re
from typing import List

from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.cir import CIRSuite, CIRTestCase, AssertionType
from adapters.assertion_rules import body_after, extract_assertions

_TEST_HEADER = re.compile(r"\bTEST\s*\(\s*(?P<suite>\w+)\s*,\s*(?P<name>\w+)\s*\)")


class CppUTestAdapter(BaseAdapter):
    capabilities = AdapterCapabilities(
        name="cpputest",
        language="cpp",
        file_globs=["*Test.cpp", "test_*.cpp", "*_test.cpp"],
        supports_coverage=True,
        supports_mocking=True,
        supports_xml_report=True,
        description="CppUTest / CppUMock for C and C++.",
        maturity="stable",
    )

    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        suite = CIRSuite(framework_source="cpputest")
        for tf in test_files:
            if not os.path.exists(tf):
                continue
            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for m in _TEST_HEADER.finditer(content):
                name, gsuite = m.group("name"), m.group("suite")
                body = body_after(content, m.end() - 1)
                suite.test_cases.append(
                    CIRTestCase(
                        test_case_id=f"{gsuite}.{name}",
                        method_under_test=self._guess_method(body) or name,
                        framework_source="cpputest",
                        suite=gsuite,
                        assertions=extract_assertions(body, "cpputest"),
                        file=os.path.basename(tf),
                        raw_body=body.strip(),
                    )
                )
        return suite

    @staticmethod
    def _guess_method(body: str) -> str:
        m = re.search(r"=\s*(\w+)\s*\(", body)
        return m.group(1) if m else ""

    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        from orchestrator import run_script_in_workspace

        return run_script_in_workspace(
            workspace_path, kwargs.get("script_path"), kwargs.get("test_target"), framework="cpputest"
        )

    def render_test(self, cir_test) -> str:
        suite = cir_test.suite or "MutationGroup"
        name = re.sub(r"\W+", "_", cir_test.test_case_id) or "GeneratedTest"
        lines = [f"TEST({suite}, {name}) {{"]
        for a in cir_test.assertions:
            lines.append("    " + self._render_assertion(a, cir_test.method_under_test))
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _render_assertion(a, method: str) -> str:
        actual = a.actual or f"{method}(/* args */)"
        mapping = {
            AssertionType.EQUAL: f"LONGS_EQUAL({a.expected}, {actual});",
            AssertionType.STRING_EQUAL: f"STRCMP_EQUAL({a.expected}, {actual});",
            AssertionType.NEAR: f"DOUBLES_EQUAL({a.expected}, {actual}, {a.tolerance or '0.001'});",
            AssertionType.TRUE: f"CHECK_TRUE({actual});",
            AssertionType.FALSE: f"CHECK_FALSE({actual});",
        }
        return mapping.get(a.type, f"CHECK_EQUAL({a.expected}, {actual});")
