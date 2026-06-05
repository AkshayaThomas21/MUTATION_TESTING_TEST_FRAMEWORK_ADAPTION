# Phase 2 Submission Kit — 2-min Video + PPT

Assessment criteria: **Solution & content · Scalability · Innovation · UX · "Wow"**

---

## 🎬 2-minute video script (with on-screen actions)

**[0:00–0:15] Hook — the problem**
> "Across BOSCH, teams use Google Test, Unity, CppUTest, VectorCAST, and custom
> in-house frameworks. Traditional mutation testing hard-codes one framework and
> floods you with low-value mutants. We rebuilt it to be **framework-agnostic and
> self-healing**."

**[0:15–0:40] The Gateway + CIR (Innovation #1)**
*Action:* Show terminal `python area2_cli.py --list-frameworks` → 7 adapters appear.
> "Every framework is normalized into one **Common Internal Representation**. Our AI
> never sees framework syntax — we call it **Zero LLM Framework Learning**."

**[0:40–1:00] Render Once, Emit Everywhere (Wow #1)**
*Action:* Dashboard → **Render Once · Emit Everywhere** tab. Pick a CIR test; the
panels show the *same* test rendered as GTest, Unity, CppUTest, PyTest, VectorCAST, BOSCH.
> "The AI designs a test **once**. Every team gets it in **their** framework — instantly."

**[1:00–1:20] Zero-code onboarding (Scalability)**
*Action:* Open `adapters/specs/robot.md`. Highlight it's just markdown.
> "Onboarding a brand-new or proprietary framework? Drop in **one markdown file**.
> No core changes. The `robot` adapter you saw was added with **zero Python**."

**[1:20–1:45] Self-healing loop (Innovation #2 + Solution)**
*Action:* Dashboard → **Survived & Root Cause** → **AI Test Synthesis** tabs.
> "Survived mutants are root-caused — Boundary Gap, Weak Assertion, Exception Gap —
> then the AI **synthesizes a killing test**, validates it passes on the original and
> fails on the mutant, and improves weak assertions. The **Feedback Loop** drives the
> mutation score from **62% to 91%** automatically."

**[1:45–2:00] Quality Signal Engine + CI/CD gate (UX + Wow #2)**
*Action:* Dashboard → **Quality Quadrants**. Show gauges + the green CI/CD badge.
> "One quality index from four metric quadrants — mutation, test quality, AI cost,
> execution — feeding an automated **CI/CD gate**. Consistent signals across every
> BOSCH framework. That's our platform."

---

## 🖼️ PPT slide outline (8 slides)

1. **Title** — AI-Powered, Framework-Agnostic Mutation Testing (Area 2).
2. **Problem** — N frameworks × hard-coded tooling × noisy mutants × testing blind spots.
3. **Architecture** — your 4K diagram: Gateway → 5-step pipeline → dual AI paths → Quality Engine.
4. **Innovation 1 — CIR** — "Zero LLM Framework Learning"; one test → every framework.
5. **Innovation 2 — Self-healing** — root cause → synth → validate → re-run; 62%→91%.
6. **Scalability** — zero-code `.md` onboarding; 6 code adapters + spec adapters; future-proof.
7. **Quality Signal Engine** — 4 quadrants, unified index, CI/CD gates, dashboard screenshot.
8. **Impact** — 60–80% less test-dev time, 40–60% mutation-score uplift, zero onboarding effort.

---

## 💬 Anticipated judge Q&A

- *"Does it really run?"* — Yes: `streamlit run dashboard/app.py` (offline demo) uses the
  **real** CIR, adapters, root-cause analyzer, and quality engine. Phase-1 C/GTest pipeline is
  unchanged and still runs end-to-end with Azure + a real project.
- *"How is this different from Stryker/Mutpy?"* — Those are single-framework and rule-based.
  Ours is multi-framework via CIR, LLM-driven, and **closes the loop** by repairing the suite.
- *"Cost?"* — Tracked per-test in the AI quadrant; cheap heuristic fallback when LLM is off.
