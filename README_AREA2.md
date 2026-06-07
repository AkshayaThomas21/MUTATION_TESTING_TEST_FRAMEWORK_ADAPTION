# Area 2 — Framework-Agnostic AI Mutation Testing Platform (Phase 2)

> Built on top of the Phase-1 C/GTest engine. Phase 2 makes it **framework-agnostic**,
> **self-healing** (root-cause → AI test synthesis), and adds a live **Quality Signal
> Engine** dashboard with CI/CD gates.

---

## 🚀 60-second demo (no Azure, no C build required)

```powershell
pip install -r requirements.txt
python area2_cli.py --list-frameworks          # see all adapters (incl. ATT + zero-code 'robot')
python area2_cli.py --demo --framework gtest   # writes temp/quality_report.json
streamlit run dashboard/app.py                 # open the dashboard
```

Switch the **Framework adapter** in the sidebar to `unity`, `cpputest`, `pytest`,
`vectorcast`, `bosch`, `att`, or `robot` and watch the same analysis + the **"Render Once,
Emit Everywhere"** tab regenerate the *same* AI test in every framework.

---

## 🧩 What was added in Phase 2

| Module | Path | Purpose |
|---|---|---|
| **Framework-Agnostic Gateway** | `adapters/` | Normalize ANY framework into one **CIR** |
| ↳ Standard contract | `adapters/base_adapter.py` | `parse_tests / execute_tests / get_coverage / build_workspace` |
| ↳ Common Internal Representation | `adapters/cir.py` | Neutral test/assertion/mutant model — *LLM never sees framework syntax* |
| ↳ Plugin registry | `adapters/registry.py` | Auto-discovers `.py` adapters + `.md` specs |
| ↳ Zero-code onboarding | `adapters/spec_adapter.py`, `adapters/specs/*.md` | Add a framework with **one markdown file** |
| ↳ Adapters | `adapters/{gtest,unity,cpputest,pytest,vectorcast,custom_bosch}_adapter.py` | 6 frameworks |
| **Root Cause Analyzer** | `quality/root_cause.py` | Why did a mutant survive? (Boundary/Exception/Assertion/State/Dead-code) |
| **AI Test Synthesis (dual path)** | `synthesis/` | Path A: generate killing tests · Path B: improve weak tests |
| **Quality Signal Engine** | `quality/` | 4 metric quadrants → unified quality index → CI/CD gate |
| **Orchestrator** | `orchestrator.py` | Ties gateway + analysis + synthesis + signals together |
| **Dashboard** | `dashboard/app.py` | Streamlit UI — the WOW factor |
| **CLI** | `area2_cli.py` | List frameworks · parse→CIR · demo · build report |

The Phase-1 flow (`Mutation_Test.py`, `pipeline.py`, `core/`, `src/`) is **untouched**
and still runs exactly as before.

---

## 🏆 The three differentiators

1. **Common Internal Representation (CIR)** → *Zero LLM Framework Learning*. The AI reasons
   about test *intent*, so a mutant-killing test designed once is emitted into every team's
   framework. (See the **Render Once · Emit Everywhere** tab.)

2. **Zero-code framework onboarding.** New/proprietary BOSCH frameworks are added by dropping
   a markdown spec into `adapters/specs/` — no core change, no redeploy. `robot.md` proves it.

3. **Self-healing pipeline.** Survived mutant → root-cause classification → targeted AI test
   synthesis → validate (pass-on-original + fail-on-mutant) → re-run. The feedback loop drives
   the mutation score up automatically (62% → 91% in the demo).

---

## 🔗 How it plugs into the real pipeline

After running the Phase-1 pipeline (`python Mutation_Test.py`), build the Area-2 report from
its results:

```powershell
python area2_cli.py --from-temp --framework gtest --source path\to\Your.c
```

This reads `temp/c*.json`, runs root-cause + synthesis + the Quality Signal Engine, and writes
`temp/quality_report.json` (the dashboard's *Live report* source).

---

## 🧪 Onboard a new framework (live, in the demo)

Create `adapters/specs/myframework.md`:

```markdown
---
name: myframework
language: c
file_globs: ["*_spec.c"]
assertions:
  - type: EQUAL
    pattern: 'MF_EQUAL\(([^,]+),\s*([^)]+)\)'
---
# My Framework
```

Re-run `python area2_cli.py --list-frameworks` — it's already available. Zero Python.
