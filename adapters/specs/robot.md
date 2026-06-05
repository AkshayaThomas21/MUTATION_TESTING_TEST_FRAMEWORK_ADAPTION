---
name: robot
language: robotframework
file_globs: ["*.robot"]
supports_coverage: false
supports_mocking: false
description: "Robot Framework — onboarded with ZERO Python code, via this markdown spec only."
case_regex: '(?m)^(?P<name>[A-Z][\w ]+)$'
assertions:
  - type: EQUAL
    pattern: 'Should Be Equal(?:\s+As\s+\w+)?\s+(?P<actual>\S+)\s+(?P<expected>\S+)'
  - type: NOT_EQUAL
    pattern: 'Should Not Be Equal\s+(?P<actual>\S+)\s+(?P<expected>\S+)'
  - type: TRUE
    pattern: 'Should Be True\s+(?P<actual>.+)'
  - type: GREATER
    pattern: 'Should Be True\s+(?P<actual>\S+)\s*>\s*(?P<expected>\S+)'
render_template: |
  {name}
      ${{result}}=    Call Method    {method}    {inputs}
      Should Be Equal    ${{result}}    {expected}
---

# Robot Framework Adapter (spec-only)

This file demonstrates **zero-code framework onboarding**. By dropping this
markdown spec into `adapters/specs/`, the Mutation Testing platform instantly
gains the ability to:

- Parse `*.robot` test cases into the Common Internal Representation (CIR).
- Map Robot keywords (`Should Be Equal`, `Should Be True`, ...) to neutral
  assertion intents.
- Render AI-designed CIR tests back into Robot syntax.

No core pipeline change, no redeploy. This is how BOSCH onboards **any current
or future** framework with minimal engineering effort.
