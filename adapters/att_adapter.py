"""ATT adapter for ASCET/ATT/RuBatch style XML reports and bundled zip outputs."""

from __future__ import annotations

import os
import re
import zipfile
from typing import List, Iterable
from xml.etree import ElementTree as ET

from adapters.base_adapter import BaseAdapter, AdapterCapabilities, ExecutionResult
from adapters.cir import CIRSuite, CIRTestCase, CIRAssertion, CIRInput, AssertionType

_TC_SUFFIX = re.compile(r"_TC\d+$", re.IGNORECASE)
_RUN_XML = re.compile(r"_run\d+\.xml$", re.IGNORECASE)


class ATTAdapter(BaseAdapter):
    capabilities = AdapterCapabilities(
        name="att",
        language="att/xml",
        file_globs=[
            "*.zip",
            "*ATT_Report.xml",
            "*reportcomplete.xml",
            "*_run*.xml",
            "*_ExcelToATT.xlsb",
        ],
        supports_coverage=False,
        supports_mocking=False,
        supports_xml_report=True,
        description="ATT / RuBatch XML reports and packaged simulation result bundles.",
        maturity="beta",
    )

    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        suite = CIRSuite(framework_source="att")
        seen_ids: set[str] = set()
        warnings: List[str] = []

        for tf in test_files:
            if not os.path.exists(tf):
                warnings.append(f"{os.path.basename(tf)}: file not found")
                continue

            lower = tf.lower()
            try:
                if lower.endswith(".zip"):
                    self._parse_zip(tf, suite, seen_ids, warnings)
                elif lower.endswith(".xml"):
                    self._parse_xml_file(tf, suite, seen_ids, warnings)
                elif lower.endswith(".xlsb"):
                    self._parse_xlsb(tf, suite, seen_ids, warnings)
                else:
                    warnings.append(f"{os.path.basename(tf)}: unsupported ATT artifact")
            except Exception as exc:  # keep parsing the remaining files
                warnings.append(f"{os.path.basename(tf)}: {type(exc).__name__}: {exc}")

        suite.metadata["test_files"] = [os.path.basename(f) for f in test_files]
        suite.metadata["parsed_cases"] = len(suite.test_cases)
        if warnings:
            suite.metadata["warnings"] = warnings
        return suite

    def _parse_zip(
        self, zip_path: str, suite: CIRSuite, seen_ids: set[str], warnings: List[str]
    ) -> None:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            xml_names = [n for n in names if n.lower().endswith(".xml")]
            xlsb_names = [n for n in names if n.lower().endswith(".xlsb")]
            # Prefer report-looking XMLs, but fall back to every XML in the bundle
            # so a differently-named simulation report is still picked up.
            report_like = [n for n in xml_names if self._is_report_name(n)]
            for name in (report_like or xml_names):
                try:
                    with zf.open(name) as fh:
                        text = fh.read().decode("utf-8", errors="ignore")
                    self._parse_xml_text(
                        text, suite, seen_ids, os.path.basename(name), warnings
                    )
                except Exception as exc:
                    warnings.append(f"{name}: {type(exc).__name__}: {exc}")
            # ExcelToATT authoring workbooks may be bundled alongside the report.
            for name in xlsb_names:
                try:
                    with zf.open(name) as fh:
                        data = fh.read()
                    self._parse_xlsb_bytes(
                        data, suite, seen_ids, os.path.basename(name), warnings
                    )
                except Exception as exc:
                    warnings.append(f"{name}: {type(exc).__name__}: {exc}")
            if not xml_names and not xlsb_names:
                warnings.append(
                    f"{os.path.basename(zip_path)}: no XML/xlsb report inside bundle"
                )

    @staticmethod
    def _is_report_name(name: str) -> bool:
        base = os.path.basename(name).lower()
        return (
            base.endswith("att_report.xml")
            or base.endswith("reportcomplete.xml")
            or "report" in base
            or bool(_RUN_XML.search(base))
        )

    def _parse_xml_file(
        self, path: str, suite: CIRSuite, seen_ids: set[str], warnings: List[str]
    ) -> None:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        self._parse_xml_text(text, suite, seen_ids, os.path.basename(path), warnings)

    def _parse_xml_text(
        self,
        text: str,
        suite: CIRSuite,
        seen_ids: set[str],
        source_name: str,
        warnings: List[str],
    ) -> None:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            warnings.append(f"{source_name}: malformed XML ({exc})")
            return

        tag = self._local(root.tag)
        before = len(suite.test_cases)
        if tag == "Report":
            self._parse_att_report(root, suite, seen_ids, source_name)
        elif tag == "RubasaOutput":
            self._parse_rubasa_output(root, suite, seen_ids, source_name)
        elif tag == "TCReport":
            self._parse_tc_report(root, suite, seen_ids, source_name)
        else:
            warnings.append(f"{source_name}: unrecognized ATT root <{tag}> (skipped)")
            return
        if len(suite.test_cases) == before:
            warnings.append(f"{source_name}: <{tag}> contained no test cases")


    def _parse_att_report(
        self, root: ET.Element, suite: CIRSuite, seen_ids: set[str], source_name: str
    ) -> None:
        class_name = self._text(root.find("./ReportHeader/ClassName")) or "ATTModule"
        suite.module = suite.module or class_name

        for module in root.findall("./TestModules/TestModule"):
            module_name = self._text(module.find("TestModuleName")) or class_name
            method = self._normalize_method(module_name, class_name)
            for case in module.findall("./TestCases/TestCase"):
                case_name = self._text(case.find("TestCaseName")) or method
                if case_name in seen_ids:
                    continue
                assertions = self._signal_assertions(case)
                verdict = self._text(case.find("TestCaseVerdict"))
                raw = f"Verdict={verdict or 'UNKNOWN'}; Signals={len(assertions)}"
                suite.test_cases.append(
                    CIRTestCase(
                        test_case_id=case_name,
                        method_under_test=method,
                        framework_source="att",
                        suite=module_name,
                        assertions=assertions,
                        file=source_name,
                        raw_body=raw,
                    )
                )
                seen_ids.add(case_name)

    def _parse_rubasa_output(
        self, root: ET.Element, suite: CIRSuite, seen_ids: set[str], source_name: str
    ) -> None:
        config_file = self._text(root.find("./Analysis/Info/RubasaCall/ConfigFile")) or source_name
        case_name = self._normalize_case_id(config_file)
        if case_name in seen_ids:
            return

        inputs: List[CIRInput] = []
        assertions: List[CIRAssertion] = []
        for info in root.findall(".//VariationInfo/Info"):
            name = self._text(info.find("Name"))
            value = self._text(info.find("Value"))
            kind = self._text(info.find("Type"))
            if not name or value is None:
                continue
            if name in {"BoundarySignal_upper", "BoundarySignal_lower", "evaluationRange"}:
                continue
            if name == "Signal":
                inputs.append(CIRInput(param=name, value=value, type=kind))
            elif name.startswith("expected_"):
                actual = self._strip_expected_name(name)
                assertions.append(
                    CIRAssertion(
                        type=AssertionType.EQUAL,
                        actual=actual,
                        expected=value,
                        raw=f"{actual} == {value}",
                    )
                )
            else:
                inputs.append(CIRInput(param=name, value=value, type=kind))

        verdict = self._text(root.find(".//OverallVerdict/v"))
        suite_name = self._derive_suite(case_name)
        suite.test_cases.append(
            CIRTestCase(
                test_case_id=case_name,
                method_under_test=self._normalize_method(suite_name, suite.module or suite_name),
                framework_source="att",
                suite=suite_name,
                inputs=inputs,
                assertions=assertions,
                file=source_name,
                raw_body=f"Verdict={verdict or 'UNKNOWN'}; Inputs={len(inputs)}; Assertions={len(assertions)}",
            )
        )
        seen_ids.add(case_name)

    def _parse_tc_report(
        self, root: ET.Element, suite: CIRSuite, seen_ids: set[str], source_name: str
    ) -> None:
        for source in root.findall(".//SingleReport/Declaration/Topic/Source/FileLink/Name"):
            case_name = self._text(source)
            if not case_name:
                continue
            case_name = self._normalize_case_id(case_name)
            if case_name in seen_ids:
                continue
            suite_name = self._derive_suite(case_name)
            suite.test_cases.append(
                CIRTestCase(
                    test_case_id=case_name,
                    method_under_test=self._normalize_method(suite_name, suite.module or suite_name),
                    framework_source="att",
                    suite=suite_name,
                    file=source_name,
                    raw_body="Verdict=UNKNOWN",
                )
            )
            seen_ids.add(case_name)

    def _signal_assertions(self, case: ET.Element) -> List[CIRAssertion]:
        assertions: List[CIRAssertion] = []
        for signal in case.findall(".//SignalDetails"):
            actual_name = self._text(signal.find("SignalName"))
            actual_value = self._text(signal.find("Signal"))
            expected = self._text(signal.find("Expected"))
            tolerance = self._text(signal.find("Tolerance"))
            if actual_name is None and actual_value is None and expected is None:
                continue
            atype = AssertionType.NEAR if self._has_tolerance(tolerance) else AssertionType.EQUAL
            assertions.append(
                CIRAssertion(
                    type=atype,
                    actual=actual_name or actual_value,
                    expected=expected,
                    tolerance=tolerance if atype == AssertionType.NEAR else None,
                    raw=f"{actual_name or 'signal'}={actual_value} expected={expected}",
                )
            )
        return assertions

    # ------------------------------------------------------------------ #
    # ExcelToATT (.xlsb) authoring-source parsing                        #
    # ------------------------------------------------------------------ #
    def _parse_xlsb(
        self, path: str, suite: CIRSuite, seen_ids: set[str], warnings: List[str]
    ) -> None:
        with open(path, "rb") as fh:
            data = fh.read()
        self._parse_xlsb_bytes(data, suite, seen_ids, os.path.basename(path), warnings)

    def _parse_xlsb_bytes(
        self,
        data: bytes,
        suite: CIRSuite,
        seen_ids: set[str],
        source_name: str,
        warnings: List[str],
    ) -> None:
        try:
            import pyxlsb  # type: ignore
        except ImportError:
            warnings.append(
                f"{source_name}: ExcelToATT workbook detected but 'pyxlsb' is not "
                "installed (pip install pyxlsb) — skipping authoring source."
            )
            return

        import io

        module = self._normalize_method(os.path.splitext(source_name)[0], source_name)
        suite.module = suite.module or module
        case_id = self._normalize_case_id(source_name)
        if case_id in seen_ids:
            return

        inputs: List[CIRInput] = []
        assertions: List[CIRAssertion] = []
        try:
            with pyxlsb.open_workbook(io.BytesIO(data)) as wb:
                for sheet_name in wb.sheets:
                    with wb.get_sheet(sheet_name) as sheet:
                        rows = [[c.v for c in row] for row in sheet.rows()]
                    self._harvest_excel_rows(rows, inputs, assertions)
        except Exception as exc:
            warnings.append(
                f"{source_name}: xlsb read failed ({type(exc).__name__}: {exc})"
            )
            return

        if not inputs and not assertions:
            warnings.append(
                f"{source_name}: no ATT signals / expected values detected in workbook"
            )

        suite.test_cases.append(
            CIRTestCase(
                test_case_id=case_id,
                method_under_test=self._normalize_method(module, module),
                framework_source="att",
                suite=self._derive_suite(case_id),
                inputs=inputs,
                assertions=assertions,
                file=source_name,
                raw_body=(
                    f"Source=ExcelToATT; Inputs={len(inputs)}; "
                    f"Expected={len(assertions)}"
                ),
            )
        )
        seen_ids.add(case_id)

    def _harvest_excel_rows(
        self, rows: List[List], inputs: List[CIRInput], assertions: List[CIRAssertion]
    ) -> None:
        """Tolerant ExcelToATT scan: pair a name cell with its adjacent value cell.

        Mirrors the RuBatch ``VariationInfo`` convention used elsewhere in this
        adapter — ``expected_*`` names become assertions, everything else an
        input. It scans each row for the first non-empty text cell (the name)
        and the next non-empty cell (its value), so it survives extra leading or
        layout columns in different ExcelToATT templates.
        """
        for row in rows:
            cells = [c for c in row if c is not None and str(c).strip() != ""]
            if len(cells) < 2:
                continue
            name = str(cells[0]).strip()
            value = str(cells[1]).strip()
            tolerance = str(cells[2]).strip() if len(cells) >= 3 else None
            low = name.lower()
            if low in {"signal", "name", "parameter", "input", "variable", "time"}:
                continue  # header label cell, not a real binding
            if low.startswith(("boundarysignal", "evaluationrange", "boundary")):
                continue
            if low.startswith("expected"):
                actual = self._strip_expected_name(name)
                atype = AssertionType.NEAR if self._has_tolerance(tolerance) else AssertionType.EQUAL
                assertions.append(
                    CIRAssertion(
                        type=atype,
                        actual=actual,
                        expected=value,
                        tolerance=tolerance if atype == AssertionType.NEAR else None,
                        raw=f"{actual} == {value}",
                    )
                )
            else:
                inputs.append(CIRInput(param=name, value=value))

    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        script_path = kwargs.get("script_path")
        if script_path:
            from orchestrator import run_script_in_workspace

            return run_script_in_workspace(
                workspace_path, script_path, kwargs.get("test_target"), framework="att"
            )
        raise NotImplementedError(
            "ATT execution requires a project-specific ATT/RuBatch script_path."
        )

    def render_test(self, cir_test) -> str:
        lines = [
            "<ATTTestCase>",
            f"  <Name>{cir_test.test_case_id}</Name>",
            f"  <Module>{cir_test.suite or cir_test.method_under_test}</Module>",
        ]
        if cir_test.inputs:
            lines.append("  <Inputs>")
            for item in cir_test.inputs:
                lines.append(f'    <Input name="{item.param}" value="{item.value}" />')
            lines.append("  </Inputs>")
        if cir_test.assertions:
            lines.append("  <ExpectedSignals>")
            for assertion in cir_test.assertions:
                attrs = [
                    f'name="{assertion.actual or "signal"}"',
                    f'expected="{assertion.expected or ""}"',
                ]
                if assertion.tolerance:
                    attrs.append(f'tolerance="{assertion.tolerance}"')
                lines.append(f"    <Signal {' '.join(attrs)} />")
            lines.append("  </ExpectedSignals>")
        lines.append("</ATTTestCase>")
        return "\n".join(lines)

    @staticmethod
    def _text(node: ET.Element | None) -> str | None:
        if node is None or node.text is None:
            return None
        value = node.text.strip()
        return value or None

    @staticmethod
    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _normalize_method(module_name: str, fallback: str) -> str:
        cleaned = _TC_SUFFIX.sub("", module_name or "").strip("_")
        cleaned = re.sub(r"^TM_", "", cleaned)
        return cleaned or fallback

    @staticmethod
    def _derive_suite(case_name: str) -> str:
        return _TC_SUFFIX.sub("", case_name)

    @staticmethod
    def _has_tolerance(value: str | None) -> bool:
        if value is None:
            return False
        normalized = value.replace(",", ".").strip()
        return normalized not in {"", "0", "0.0"}

    @staticmethod
    def _strip_expected_name(name: str) -> str:
        return name[len("expected_") :] if name.startswith("expected_") else name

    @staticmethod
    def _normalize_case_id(value: str) -> str:
        base = os.path.splitext(os.path.basename(value))[0]
        base = base.replace("_config", "")
        base = re.sub(r"_run\d+$", "", base, flags=re.IGNORECASE)
        return base
