"""
Custom BOSCH adapter — template for proprietary in-house test macros.

Many BOSCH units wrap GTest/Unity with custom macros (e.g. BOSCH_CHECK_EQ,
BT_ASSERT_EQUAL). This adapter shows how a team extends the platform: declare
the custom macro->CIR mapping and you are done. It also accepts mixed macro
styles via the 'bosch' ruleset.
"""

from __future__ import annotations

import os
import re
from typing import List

from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.cir import CIRSuite, CIRTestCase, CIRAssertion, AssertionType
from adapters.assertion_rules import body_after, extract_assertions

# Custom BOSCH-style test declaration + macros
_BOSCH_HEADER = re.compile(r"\bBT_TEST\s*\(\s*(?P<suite>\w+)\s*,\s*(?P<name>\w+)\s*\)")
_BOSCH_MACROS = [
    (r"BOSCH_CHECK_EQ\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.EQUAL, 1, 2),
    (r"BT_ASSERT_EQUAL\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.EQUAL, 1, 2),
    (r"BOSCH_CHECK_TRUE\s*\(\s*([^;]+?)\s*\)", AssertionType.TRUE, None, 1),
    (r"BOSCH_CHECK_NEAR\s*\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.NEAR, 1, 2),
]


class CustomBoschAdapter(BaseAdapter):
    capabilities = AdapterCapabilities(
        name="bosch",
        language="c/c++",
        file_globs=["*bt_test*.cpp", "*bosch_test*.c", "*BoschTest*.cpp"],
        supports_coverage=True,
        supports_mocking=True,
        supports_xml_report=True,
        description="Custom BOSCH in-house test macros (BT_TEST / BOSCH_CHECK_*).",
        maturity="beta",
    )

    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        suite = CIRSuite(framework_source="bosch")
        for tf in test_files:
            if not os.path.exists(tf):
                continue
            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for m in _BOSCH_HEADER.finditer(content):
                name, gsuite = m.group("name"), m.group("suite")
                body = body_after(content, m.end() - 1)
                assertions = self._bosch_assertions(body) + extract_assertions(body, "bosch")
                suite.test_cases.append(
                    CIRTestCase(
                        test_case_id=f"{gsuite}.{name}",
                        method_under_test=name,
                        framework_source="bosch",
                        suite=gsuite,
                        assertions=assertions,
                        file=os.path.basename(tf),
                        raw_body=body.strip(),
                    )
                )
        return suite

    @staticmethod
    def _bosch_assertions(body: str) -> List[CIRAssertion]:
        out: List[CIRAssertion] = []
        for pattern, atype, exp_g, act_g in _BOSCH_MACROS:
            for mm in re.finditer(pattern, body):
                exp = mm.group(exp_g).strip() if exp_g and exp_g <= (mm.lastindex or 0) else None
                act = mm.group(act_g).strip() if act_g and act_g <= (mm.lastindex or 0) else None
                out.append(CIRAssertion(type=atype, expected=exp, actual=act, raw=mm.group(0).strip()))
        return out

    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        from orchestrator import run_script_in_workspace

        return run_script_in_workspace(
            workspace_path, kwargs.get("script_path"), kwargs.get("test_target"), framework="bosch"
        )

    def render_test(self, cir_test) -> str:
        suite = cir_test.suite or "BoschSuite"
        name = re.sub(r"\W+", "_", cir_test.test_case_id) or "GeneratedTest"
        lines = [f"BT_TEST({suite}, {name}) {{"]
        for a in cir_test.assertions:
            actual = a.actual or f"{cir_test.method_under_test}(/* args */)"
            if a.type == AssertionType.EQUAL:
                lines.append(f"    BOSCH_CHECK_EQ({a.expected}, {actual});")
            elif a.type == AssertionType.NEAR:
                lines.append(f"    BOSCH_CHECK_NEAR({a.expected}, {actual}, {a.tolerance or '0.001'});")
            else:
                lines.append(f"    BOSCH_CHECK_TRUE({actual});")
        lines.append("}")
        return "\n".join(lines)
