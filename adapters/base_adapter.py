"""
BaseAdapter — the standard plugin contract every framework adapter implements.

Onboarding a NEW framework = implement these four methods (or describe it in a
`.md` spec, see registry.py). The core pipeline never changes.

    parse_tests(source_code, test_files) -> CIRSuite
    execute_tests(workspace_path)        -> ExecutionResult
    get_coverage(workspace_path)         -> dict
    build_workspace(source_code, mutants)-> str   (isolated workspace path)

Plus framework-specific helpers used by the gateway:
    extract_functions(source_file)  -> list[dict]   (AST / structural parse)
    render_test(cir_test)           -> str          (CIR -> native test syntax)
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from adapters.cir import CIRSuite, CIRTestCase


@dataclass
class AdapterCapabilities:
    """Declares what an adapter supports — surfaced in the dashboard onboarding view."""

    name: str
    language: str
    file_globs: List[str]
    supports_coverage: bool = False
    supports_mocking: bool = False
    supports_xml_report: bool = False
    description: str = ""
    maturity: str = "stable"  # stable | beta | spec-only


@dataclass
class ExecutionResult:
    """Normalized result of running a test suite (original or mutated)."""

    passed: bool
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    coverage: float = 0.0
    duration_s: float = 0.0
    raw_log: str = ""
    per_test: Dict[str, str] = field(default_factory=dict)  # test_id -> PASS/FAIL

    @property
    def status(self) -> str:
        if self.failed > 0:
            return "FAIL"
        if self.succeeded > 0:
            return "PASS"
        return "UNKNOWN"


class BaseAdapter(abc.ABC):
    """Abstract framework adapter. Subclass + register to onboard a framework."""

    #: Override in subclasses. Used by the registry for auto-discovery.
    capabilities: AdapterCapabilities = AdapterCapabilities(
        name="base", language="", file_globs=[]
    )

    # ------------------------------------------------------------------ #
    # The four-method standard contract                                  #
    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    def parse_tests(self, source_code: str, test_files: List[str]) -> CIRSuite:
        """Extract test cases + assertions and normalize them into a CIRSuite."""
        raise NotImplementedError

    @abc.abstractmethod
    def execute_tests(self, workspace_path: str, **kwargs) -> ExecutionResult:
        """Build + run tests inside a workspace, return a normalized ExecutionResult."""
        raise NotImplementedError

    def get_coverage(self, workspace_path: str, **kwargs) -> Dict[str, Any]:
        """Return coverage data. Default: empty (override if supported)."""
        return {"line_coverage": 0.0, "branch_coverage": 0.0, "covered_lines": []}

    def build_workspace(self, source_code: str, mutants: List[dict], **kwargs) -> str:
        """
        Create an isolated execution environment for a set of mutants.
        Default delegates to the shared clone-based runner (see orchestrator).
        Adapters that need Docker / custom toolchains override this.
        """
        raise NotImplementedError(
            f"{self.capabilities.name} adapter uses the shared clone runner; "
            "call orchestrator.build_workspace instead."
        )

    # ------------------------------------------------------------------ #
    # Gateway helpers (have sensible defaults / framework specializations)#
    # ------------------------------------------------------------------ #
    def extract_functions(self, source_file: str) -> List[Dict[str, str]]:
        """Structural parse of the unit-under-test source. Default: C tree-sitter."""
        from core.function_extractor import extract_functions

        return extract_functions(source_file)

    @abc.abstractmethod
    def render_test(self, cir_test: CIRTestCase) -> str:
        """
        Render a CIR test case back into this framework's native syntax.
        This is what closes the loop: AI designs a test once (in CIR), and every
        adapter can emit it in the team's own framework.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Convenience                                                        #
    # ------------------------------------------------------------------ #
    def matches_file(self, path: str) -> bool:
        import fnmatch

        return any(fnmatch.fnmatch(path.lower(), g.lower()) for g in self.capabilities.file_globs)

    def __repr__(self) -> str:  # pragma: no cover
        c = self.capabilities
        return f"<Adapter {c.name} lang={c.language} maturity={c.maturity}>"
