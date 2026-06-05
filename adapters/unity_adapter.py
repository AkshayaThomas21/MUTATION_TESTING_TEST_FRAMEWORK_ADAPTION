"""Unity (ThrowTheSwitch) adapter — embedded C unit testing."""

from __future__ import annotations

import os
import re
from typing import List

from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.cir import CIRSuite, CIRTestCase, AssertionType
from adapters.assertion_rules import find_balanced_blocks, extract_assertions

_UNITY_HEADER = re.compile(r"\bvoid\s+(?P<name>test_\w+)\s*\(\s*void\s*\)")


class UnityAdapter(BaseAdapter):
    capabilities = AdapterCapabilities(
        name="unity",
        language="c",
        file_globs=["test_*.c", "*_test.c", "*unity*.c"],
        supports_coverage=True,
        supports_mocking=True,  # via CMock
        supports_xml_report=False,
        description="Unity test framework for embedded C (ThrowTheSwitch).",
        maturity="stable",
    )

    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        suite = CIRSuite(framework_source="unity")
        for tf in test_files:
            if not os.path.exists(tf):
                continue
            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for name, body in find_balanced_blocks(content, _UNITY_HEADER):
                suite.test_cases.append(
                    CIRTestCase(
                        test_case_id=name,
                        method_under_test=self._guess_method(body) or name.replace("test_", ""),
                        framework_source="unity",
                        assertions=extract_assertions(body, "unity"),
                        file=os.path.basename(tf),
                        raw_body=body.strip(),
                    )
                )
        return suite

    @staticmethod
    def _guess_method(body: str) -> str:
        m = re.search(r"=\s*(\w+)\s*\(", body) or re.search(r"\b(\w+)\s*\([^)]*\)\s*;", body)
        return m.group(1) if m else ""

    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        from orchestrator import run_script_in_workspace

        return run_script_in_workspace(
            workspace_path, kwargs.get("script_path"), kwargs.get("test_target"), framework="unity"
        )

    def render_test(self, cir_test) -> str:
        name = cir_test.test_case_id if cir_test.test_case_id.startswith("test_") else f"test_{cir_test.test_case_id}"
        name = re.sub(r"\W+", "_", name)
        lines = [f"void {name}(void) {{"]
        for a in cir_test.assertions:
            lines.append("    " + self._render_assertion(a, cir_test.method_under_test))
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _render_assertion(a, method: str) -> str:
        actual = a.actual or f"{method}(/* args */)"
        mapping = {
            AssertionType.EQUAL: f"TEST_ASSERT_EQUAL({a.expected}, {actual});",
            AssertionType.NOT_EQUAL: f"TEST_ASSERT_NOT_EQUAL({a.expected}, {actual});",
            AssertionType.STRING_EQUAL: f"TEST_ASSERT_EQUAL_STRING({a.expected}, {actual});",
            AssertionType.NEAR: f"TEST_ASSERT_FLOAT_WITHIN({a.tolerance or '0.001'}, {a.expected}, {actual});",
            AssertionType.GREATER: f"TEST_ASSERT_GREATER_THAN({a.expected}, {actual});",
            AssertionType.TRUE: f"TEST_ASSERT_TRUE({actual});",
            AssertionType.FALSE: f"TEST_ASSERT_FALSE({actual});",
            AssertionType.NULL: f"TEST_ASSERT_NULL({actual});",
            AssertionType.NOT_NULL: f"TEST_ASSERT_NOT_NULL({actual});",
        }
        return mapping.get(a.type, f"TEST_ASSERT_EQUAL({a.expected}, {actual});")
