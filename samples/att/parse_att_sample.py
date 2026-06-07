"""Parse the bundled ATT example artifacts into the Common Internal Representation.

Usage:
    python samples/att/parse_att_sample.py

Drops any *.zip / *.xml / *.xlsb files placed in this folder through the
`att` adapter and prints the normalized CIRSuite plus parser warnings.
"""

from __future__ import annotations

import glob
import os
import sys

# Make the project root importable when run directly.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from adapters.att_adapter import ATTAdapter


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    test_files = sorted(
        f
        for f in glob.glob(os.path.join(here, "*"))
        if f.lower().endswith((".zip", ".xml", ".xlsb"))
    )

    if not test_files:
        print("No ATT artifacts found in samples/att/.")
        print("Copy the .zip / .xlsb example files here first (see README.md).")
        return 1

    print("Parsing ATT artifacts:")
    for f in test_files:
        print(f"  - {os.path.basename(f)}")
    print("-" * 60)

    suite = ATTAdapter().parse_tests(source_code="", test_files=test_files)

    print(f"Framework : {suite.framework_source}")
    print(f"Module    : {suite.module}")
    print(f"Test cases: {len(suite.test_cases)}")
    print("-" * 60)

    for tc in suite.test_cases:
        print(f"[{tc.test_case_id}]  method={tc.method_under_test}  suite={tc.suite}")
        print(f"    source file : {tc.file}")
        if tc.inputs:
            print(f"    inputs ({len(tc.inputs)}):")
            for i in tc.inputs[:12]:
                print(f"        {i.param} = {i.value}")
            if len(tc.inputs) > 12:
                print(f"        ... +{len(tc.inputs) - 12} more")
        if tc.assertions:
            print(f"    assertions ({len(tc.assertions)}):  "
                  f"strength={tc.assertion_strength()}")
            for a in tc.assertions[:12]:
                tol = f" (~{a.tolerance})" if a.tolerance else ""
                print(f"        {a.actual} {a.type.value} {a.expected}{tol}")
            if len(tc.assertions) > 12:
                print(f"        ... +{len(tc.assertions) - 12} more")
        print(f"    raw: {tc.raw_body}")
        print()

    warnings = suite.metadata.get("warnings")
    if warnings:
        print("-" * 60)
        print("Parser warnings:")
        for w in warnings:
            print(f"  ! {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
