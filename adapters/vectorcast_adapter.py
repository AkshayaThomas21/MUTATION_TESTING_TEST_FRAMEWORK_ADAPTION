"""
VectorCAST adapter — widely used at BOSCH for embedded C/C++ certification testing.

VectorCAST test scripts (.tst) are key/value blocks rather than C code. This
adapter normalizes those blocks (TEST.VALUE / TEST.EXPECTED) into CIR.
"""

from __future__ import annotations

import os
import re
from typing import List

from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.cir import CIRSuite, CIRTestCase, CIRAssertion, CIRInput, AssertionType

_TEST_BLOCK = re.compile(r"TEST\.NEW(?P<body>.*?)TEST\.END", re.DOTALL)
_NAME = re.compile(r"TEST\.NAME:(?P<name>.+)")
_SUBPROG = re.compile(r"TEST\.SUBPROGRAM:(?P<sub>.+)")
_VALUE = re.compile(r"TEST\.VALUE:(?P<param>[^:]+):(?P<value>.+)")
_EXPECTED = re.compile(r"TEST\.EXPECTED:(?P<param>[^:]+):(?P<value>.+)")


class VectorCASTAdapter(BaseAdapter):
    capabilities = AdapterCapabilities(
        name="vectorcast",
        language="c/c++",
        file_globs=["*.tst"],
        supports_coverage=True,
        supports_mocking=True,
        supports_xml_report=True,
        description="VectorCAST .tst scripts for certified embedded testing.",
        maturity="beta",
    )

    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        suite = CIRSuite(framework_source="vectorcast")
        for tf in test_files:
            if not os.path.exists(tf):
                continue
            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for idx, m in enumerate(_TEST_BLOCK.finditer(content), start=1):
                body = m.group("body")
                name_m = _NAME.search(body)
                sub_m = _SUBPROG.search(body)
                name = (name_m.group("name").strip() if name_m else f"vc_test_{idx}")
                method = (sub_m.group("sub").strip() if sub_m else name)
                inputs = [
                    CIRInput(param=vm.group("param").strip(), value=vm.group("value").strip())
                    for vm in _VALUE.finditer(body)
                ]
                assertions = [
                    CIRAssertion(
                        type=AssertionType.EQUAL,
                        actual=em.group("param").strip(),
                        expected=em.group("value").strip(),
                        raw=em.group(0).strip(),
                    )
                    for em in _EXPECTED.finditer(body)
                ]
                suite.test_cases.append(
                    CIRTestCase(
                        test_case_id=name,
                        method_under_test=method,
                        framework_source="vectorcast",
                        inputs=inputs,
                        assertions=assertions,
                        file=os.path.basename(tf),
                        raw_body=body.strip(),
                    )
                )
        return suite

    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        from orchestrator import run_script_in_workspace

        return run_script_in_workspace(
            workspace_path, kwargs.get("script_path"), kwargs.get("test_target"), framework="vectorcast"
        )

    def render_test(self, cir_test) -> str:
        lines = ["TEST.NEW", f"TEST.NAME:{cir_test.test_case_id}", f"TEST.SUBPROGRAM:{cir_test.method_under_test}"]
        for i in cir_test.inputs:
            lines.append(f"TEST.VALUE:{i.param}:{i.value}")
        for a in cir_test.assertions:
            lines.append(f"TEST.EXPECTED:{a.actual or 'return'}:{a.expected}")
        lines.append("TEST.END")
        return "\n".join(lines)
