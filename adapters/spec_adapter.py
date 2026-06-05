"""
SpecAdapter — synthesize a working adapter from a markdown spec (ZERO Python).

A spec file (`adapters/specs/<framework>.md`) carries a YAML front-matter block
describing how to recognize tests and assertions for a framework. The registry
turns each spec into a fully functional `BaseAdapter` at runtime.

This is the scalability centerpiece: a BOSCH team can onboard a brand-new or
proprietary framework by dropping in one markdown file — no core changes, no
redeploy.

Example front-matter:

    ---
    name: robot
    language: robotframework
    file_globs: ["*.robot"]
    test_regex: '\\*\\*\\* Test Cases \\*\\*\\*(?P<body>[\\s\\S]+)'
    case_regex: '^(?P<name>\\S.+)$'
    assertions:
      - type: EQUAL
        pattern: 'Should Be Equal\\s+(?P<actual>\\S+)\\s+(?P<expected>\\S+)'
      - type: TRUE
        pattern: 'Should Be True\\s+(?P<actual>.+)'
    render_template: |
      {name}
          ${{result}}=    Call Method    {inputs}
          Should Be Equal    ${{result}}    {expected}
    ---
"""

from __future__ import annotations

import os
import re
from typing import Dict, Any, List

import yaml

from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.cir import CIRSuite, CIRTestCase, CIRAssertion, AssertionType, CIRInput


def parse_spec_markdown(path: str) -> Dict[str, Any]:
    """Read a markdown spec and return its YAML front-matter as a dict."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        raise ValueError(f"Spec {path} missing YAML front-matter delimited by '---'")
    spec = yaml.safe_load(m.group(1)) or {}
    spec["_doc"] = text[m.end():].strip()
    spec.setdefault("name", os.path.splitext(os.path.basename(path))[0])
    return spec


class SpecAdapter(BaseAdapter):
    """Generic, regex/template-driven adapter built from a markdown spec."""

    def __init__(self, spec: Dict[str, Any]) -> None:
        self.spec = spec
        self.capabilities = AdapterCapabilities(
            name=spec["name"].lower(),
            language=spec.get("language", "unknown"),
            file_globs=spec.get("file_globs", ["*"]),
            supports_coverage=bool(spec.get("supports_coverage", False)),
            supports_mocking=bool(spec.get("supports_mocking", False)),
            supports_xml_report=bool(spec.get("supports_xml_report", False)),
            description=spec.get("description", "Spec-driven adapter (markdown onboarded)"),
            maturity="spec-only",
        )

    # -- parse ---------------------------------------------------------- #
    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        suite = CIRSuite(framework_source=self.capabilities.name)
        case_re = self.spec.get("case_regex")
        assertion_specs = self.spec.get("assertions", []) or []
        for tf in test_files:
            if not os.path.exists(tf):
                continue
            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            chunks = self._split_cases(content, case_re)
            for idx, (name, body) in enumerate(chunks, start=1):
                assertions: List[CIRAssertion] = []
                for aspec in assertion_specs:
                    pat = aspec.get("pattern")
                    atype = aspec.get("type", "UNKNOWN")
                    if not pat:
                        continue
                    for am in re.finditer(pat, body):
                        gd = am.groupdict()
                        assertions.append(
                            CIRAssertion(
                                type=_safe_atype(atype),
                                expected=gd.get("expected"),
                                actual=gd.get("actual"),
                                raw=am.group(0).strip(),
                            )
                        )
                suite.test_cases.append(
                    CIRTestCase(
                        test_case_id=f"{self.capabilities.name}_{idx}_{name}",
                        method_under_test=name,
                        framework_source=self.capabilities.name,
                        assertions=assertions,
                        file=os.path.basename(tf),
                        raw_body=body.strip(),
                    )
                )
        return suite

    def _split_cases(self, content: str, case_re: str | None) -> List[tuple]:
        if not case_re:
            # whole file becomes a single "case"
            return [("suite", content)]
        matches = list(re.finditer(case_re, content, re.MULTILINE))
        if not matches:
            return [("suite", content)]
        cases = []
        for idx, m in enumerate(matches):
            name = (m.groupdict().get("name") or "case").strip()
            # body spans from this match to the start of the next (or EOF)
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            cases.append((name, content[m.start():end]))
        return cases

    # -- execute (spec adapters defer to the shared script runner) ------ #
    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        raise NotImplementedError(
            "Spec adapters describe parsing/rendering. Provide a build/test script "
            "via config to execute; the orchestrator's shared runner handles it."
        )

    # -- render --------------------------------------------------------- #
    def render_test(self, cir_test: CIRTestCase) -> str:
        tmpl = self.spec.get("render_template")
        if not tmpl:
            return cir_test.raw_body or f"# {cir_test.test_case_id}"
        expected = cir_test.assertions[0].expected if cir_test.assertions else ""
        inputs = ", ".join(f"{i.value}" for i in cir_test.inputs)
        try:
            return tmpl.format(
                name=cir_test.test_case_id,
                method=cir_test.method_under_test,
                expected=expected,
                inputs=inputs,
            )
        except Exception:
            return cir_test.raw_body or tmpl


def _safe_atype(value: str) -> AssertionType:
    try:
        return AssertionType(value.upper())
    except Exception:
        return AssertionType.UNKNOWN
