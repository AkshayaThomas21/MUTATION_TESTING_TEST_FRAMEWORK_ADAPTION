"""
AI-Powered Mutation Testing — Quality Signal Dashboard (Area 2)
==============================================================

Run:
    streamlit run dashboard/app.py

Works fully offline in DEMO mode (no Azure creds, no C build needed) and uses
the real CIR, adapters, root-cause analyzer and quality engine under the hood.
"""

from __future__ import annotations

import os
import sys
import json

# Make the project root importable when launched via `streamlit run`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:  # pragma: no cover
    HAS_PLOTLY = False

from adapters import get_registry
from adapters.cir import CIRTestCase
from dashboard.demo_data import build_demo_result

st.set_page_config(page_title="Mutation Testing — Quality Signal Engine", layout="wide", page_icon="🧬")

# --------------------------------------------------------------------------- #
# Styling                                                                     #
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #0b1220 0%, #0f2027 55%, #122b3a 100%); }
    .block-container { padding-top: 1.2rem; }
    h1, h2, h3, h4, p, span, label, div { color: #e8f1f5; }
    .hero { background: linear-gradient(90deg, rgba(0,180,216,.18), rgba(72,202,228,.06));
            border: 1px solid rgba(72,202,228,.35); border-radius: 16px; padding: 18px 24px; }
    .kpi { background: rgba(255,255,255,.04); border: 1px solid rgba(72,202,228,.25);
           border-radius: 14px; padding: 16px; text-align: center; }
    .kpi .v { font-size: 2.0rem; font-weight: 800; color: #48cae4; }
    .kpi .l { font-size: .8rem; opacity:.8; letter-spacing:.5px; text-transform:uppercase;}
    .pill { display:inline-block; padding:4px 12px; border-radius:999px; font-weight:700; font-size:.8rem;}
    .pass { background:#0f5132; color:#7ee787; border:1px solid #2ea043;}
    .warn { background:#5a4a00; color:#ffd966; border:1px solid #d4a017;}
    .fail { background:#5c1a1a; color:#ff8b8b; border:1px solid #e5534b;}
    .card { background: rgba(255,255,255,.035); border:1px solid rgba(72,202,228,.22);
            border-radius:14px; padding:16px 18px; margin-bottom:10px;}
    .codeblk { background:#06121c; border:1px solid #15394d; border-radius:10px; padding:12px;
               font-family: Consolas, monospace; white-space:pre-wrap; color:#9fe7ff; font-size:.85rem;}
    .tag { background: rgba(72,202,228,.15); border:1px solid rgba(72,202,228,.4); border-radius:8px;
           padding:2px 8px; font-size:.72rem; margin-right:6px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def gauge(value: float, title: str, target: float = 80.0):
    if not HAS_PLOTLY:
        st.metric(title, f"{value}%")
        return
    color = "#2ea043" if value >= target else ("#d4a017" if value >= target * 0.75 else "#e5534b")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%", "font": {"color": "#e8f1f5", "size": 30}},
        title={"text": title, "font": {"color": "#9fe7ff", "size": 15}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#9fe7ff"},
            "bar": {"color": color},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, target * 0.75], "color": "rgba(229,83,75,.25)"},
                {"range": [target * 0.75, target], "color": "rgba(212,160,23,.25)"},
                {"range": [target, 100], "color": "rgba(46,160,67,.25)"},
            ],
            "threshold": {"line": {"color": "#48cae4", "width": 3}, "value": target},
        },
    ))
    fig.update_layout(height=240, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")


def kpi(col, value, label):
    col.markdown(f"<div class='kpi'><div class='v'>{value}</div><div class='l'>{label}</div></div>",
                 unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar                                                                      #
# --------------------------------------------------------------------------- #
registry = get_registry()
framework_names = registry.names()

with st.sidebar:
    st.markdown("## 🧬 Mutation Testing\n### Quality Signal Engine")
    st.caption("BOSCH Hackathon · Area 2 · Framework-Agnostic")
    mode = st.radio("Data source", ["Demo (offline)", "Live report (temp/quality_report.json)"])
    framework = st.selectbox("Framework adapter", framework_names,
                             index=framework_names.index("gtest") if "gtest" in framework_names else 0)
    project = st.text_input("Project", "Powertrain ECU Module")
    run = st.button("▶ Run Analysis", width="stretch", type="primary")
    st.divider()
    st.caption(f"Adapters loaded: **{len(framework_names)}**")
    st.caption("Onboard a new framework by dropping a `.md` spec into `adapters/specs/` — zero code.")


@st.cache_data(show_spinner=False)
def _demo(fw, proj):
    return build_demo_result(fw, proj)


def load_live():
    path = os.path.join("temp", "quality_report.json")
    if not os.path.exists(path):
        st.warning("No live report found at temp/quality_report.json. Run the orchestrator first, or use Demo mode.")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


if mode.startswith("Demo"):
    data = _demo(framework, project)
else:
    data = load_live() or _demo(framework, project)

report = data["report"]
gate = data["gate"]
m = report["mutation"]
tq = report["test_quality"]
ai = report["ai"]
ex = report["execution"]

# --------------------------------------------------------------------------- #
# Hero                                                                         #
# --------------------------------------------------------------------------- #
stars = "★" * report["star_rating"] + "☆" * (5 - report["star_rating"])
gate_class = {"PASS": "pass", "WARN": "warn", "FAIL": "fail"}.get(gate["status"], "warn")
st.markdown(
    f"""
    <div class="hero">
      <h1 style="margin:0">AI-Powered Mutation Testing · Quality Signal Engine</h1>
      <p style="margin:.2rem 0 0 0; opacity:.85">
        Project: <b>{report['project']}</b> &nbsp;·&nbsp; Framework: <b>{report['framework'].upper()}</b>
        &nbsp;·&nbsp; {report['timestamp']}
      </p>
      <div style="margin-top:10px">
        <span style="font-size:2.4rem;font-weight:800;color:#48cae4">{report['quality_index']}/100</span>
        <span style="font-size:1.4rem;color:#ffd966;margin-left:10px">{stars}</span>
        <span class="pill {gate_class}" style="margin-left:18px">{gate['badge']}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs([
    "📊 Quality Quadrants", "🔴 Survived & Root Cause", "🤖 AI Test Synthesis",
    "🔧 Test Improvement", "🔌 Framework Onboarding", "🔁 Render Once · Emit Everywhere", "🔂 Feedback Loop",
])

# --- Tab 1: quadrants ------------------------------------------------------- #
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("① Mutation Metrics")
        gauge(m["mutation_score"], "Mutation Score", 80)
        k = st.columns(4)
        kpi(k[0], m["killed"], "Killed")
        kpi(k[1], m["survived"], "Survived")
        kpi(k[2], m["equivalent"], "Equivalent")
        delta = m["coverage_delta"]
        kpi(k[3], f"{'+' if delta>=0 else ''}{delta}%", "Δ Trend")
    with c2:
        st.subheader("② Test Quality Metrics")
        gauge(tq["assertion_strength"], "Assertion Strength", 80)
        k = st.columns(4)
        kpi(k[0], f"{tq['effectiveness']}%", "Effectiveness")
        kpi(k[1], f"{tq['flakiness_rate']}%", "Flakiness")
        kpi(k[2], f"{tq['redundancy']}%", "Redundancy")
        kpi(k[3], f"+{tq['coverage_impact']}%", "Coverage Impact")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("③ AI Performance Metrics")
        gauge(ai["acceptance_rate"], "Recommendation Acceptance", 70)
        k = st.columns(4)
        kpi(k[0], ai["tests_generated"], "Generated")
        kpi(k[1], f"{ai['hallucination_rate']}%", "Hallucination")
        kpi(k[2], f"${ai['cost_usd']}", "Token Cost")
        kpi(k[3], f"${ai['cost_per_test']}", "Cost / Test")
    with c4:
        st.subheader("④ Execution Metrics")
        gauge(ex["parallel_efficiency"], "Parallel Efficiency", 90)
        k = st.columns(4)
        kpi(k[0], f"{ex['total_time_min']}m", "Total Time")
        kpi(k[1], f"{ex['success_rate']}%", "Success Rate")
        kpi(k[2], ex["total_runs"], "Test Runs")
        kpi(k[3], f"{ex['cpu_utilization']}%", "CPU")

    st.divider()
    ci, cr = st.columns(2)
    with ci:
        st.markdown("#### 💡 Aggregator Insights")
        for ins in report["insights"]:
            st.markdown(f"- {ins}")
    with cr:
        st.markdown("#### ✅ Recommendations")
        for rec in report["recommendations"]:
            st.markdown(f"- {rec}")
    st.markdown("#### 🚦 CI/CD Gate")
    st.markdown(f"<span class='pill {gate_class}'>{gate['status']}</span>", unsafe_allow_html=True)
    for r in gate["reasons"]:
        st.caption(f"• {r}")

# --- Tab 2: survived + root cause ------------------------------------------ #
with tabs[1]:
    st.subheader("Surviving Mutants — Root Cause Analysis")
    sm = report.get("survived_mutants", [])
    if not sm:
        st.success("No surviving mutants 🎉")
    for s in sm:
        st.markdown(
            f"""<div class="card">
            <span class="tag">{s.get('method','')}</span>
            <span class="tag">{s.get('mutant_category','')}</span>
            <span class="tag">RCA: {s.get('root_cause','')} ({s.get('rca_confidence','')}%)</span>
            <div style="margin-top:8px" class="codeblk">- {s.get('original_code','')}
+ {s.get('mutated_code','')}</div>
            <p style="margin:.4rem 0 0 0"><b>Fix focus:</b> {s.get('root_cause_focus','')}</p>
            </div>""",
            unsafe_allow_html=True,
        )

# --- Tab 3: AI synthesis ---------------------------------------------------- #
with tabs[2]:
    st.subheader("AI Test Synthesis — Path A: New Tests (root-cause driven)")
    st.caption("Designed in neutral CIR, validated (pass-on-original + fail-on-mutant), rendered into your framework.")
    for s in data.get("synthesis", []):
        validated = "✅ validated" if s.get("validated") else "⏳ pending validation"
        st.markdown(
            f"""<div class="card">
            <span class="tag">{s.get('method','')}</span>
            <span class="tag">kills: {s.get('mutant',{}).get('mutant_category','')}</span>
            <span class="tag">{s.get('root_cause','')}</span>
            <span class="tag">conf {s.get('confidence','')}%</span>
            <span class="tag">{validated}</span>
            </div>""",
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='codeblk'>{s.get('rendered','')}</div>", unsafe_allow_html=True)
        a, b, _ = st.columns([1, 1, 6])
        a.button("Accept ✅", key=f"acc_{s.get('method')}_{s.get('mutant',{}).get('mutant_id')}")
        b.button("Reject ✋", key=f"rej_{s.get('method')}_{s.get('mutant',{}).get('mutant_id')}")

# --- Tab 4: improvement ----------------------------------------------------- #
with tabs[3]:
    st.subheader("AI Test Synthesis — Path B: Improve Weak Tests")
    for imp in data.get("improvements", []):
        flag = "🧑‍⚖️ needs review" if imp.get("needs_human_review") else "auto-applicable"
        st.markdown(
            f"""<div class="card">
            <span class="tag">{imp.get('test_name','')}</span>
            <span class="tag">severity: {imp.get('severity','')}</span>
            <span class="tag">conf {imp.get('confidence','')}%</span>
            <span class="tag">{flag}</span>
            <p style="margin:.4rem 0"><b>Weakness:</b> {imp.get('weakness','')}</p>
            <p style="margin:.2rem 0"><b>Recommendation:</b> {imp.get('recommendation','')}</p>
            </div>""",
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        cols[0].markdown(f"**Before**<div class='codeblk'>{imp.get('before','')}</div>", unsafe_allow_html=True)
        cols[1].markdown(f"**After**<div class='codeblk'>{imp.get('after','')}</div>", unsafe_allow_html=True)

# --- Tab 5: onboarding ------------------------------------------------------ #
with tabs[4]:
    st.subheader("Framework-Agnostic Gateway — Adapter Registry")
    st.caption("Every framework is normalized into one Common Internal Representation (CIR). "
               "The LLM never sees framework syntax → Zero LLM Framework Learning.")
    caps = data.get("frameworks") or [c.__dict__ for c in registry.capabilities()]
    cols = st.columns(3)
    for i, c in enumerate(caps):
        with cols[i % 3]:
            badge = {"stable": "🟢", "beta": "🟡", "spec-only": "🟣"}.get(c.get("maturity"), "⚪")
            st.markdown(
                f"""<div class="card">
                <h4 style="margin:0">{badge} {c.get('name','').upper()}</h4>
                <p style="margin:.2rem 0;opacity:.8">{c.get('description','')}</p>
                <span class="tag">{c.get('language','')}</span>
                <span class="tag">{'coverage' if c.get('supports_coverage') else 'no-cov'}</span>
                <span class="tag">{'mock' if c.get('supports_mocking') else 'no-mock'}</span>
                <span class="tag">{c.get('maturity','')}</span>
                </div>""",
                unsafe_allow_html=True,
            )
    st.info("🟣 **robot** was onboarded with **zero Python** — purely from `adapters/specs/robot.md`.")

# --- Tab 6: render once, emit everywhere ------------------------------------ #
with tabs[5]:
    st.subheader("One Test, Every Framework")
    st.caption("The killer differentiator: the AI designs a test ONCE in CIR; every adapter renders it natively.")
    cir_tests = [CIRTestCase(**t) for t in data.get("cir_tests", [])]
    if cir_tests:
        choice = st.selectbox("CIR test case", [t.test_case_id for t in cir_tests])
        selected = next(t for t in cir_tests if t.test_case_id == choice)
        st.markdown("**Common Internal Representation (neutral):**")
        st.json(selected.model_dump(mode="json"))
        st.markdown("**Rendered natively into each framework:**")
        cols = st.columns(2)
        for i, name in enumerate(framework_names):
            try:
                rendered = registry.get(name).render_test(selected)
            except Exception as exc:
                rendered = f"// {name}: {exc}"
            with cols[i % 2]:
                st.markdown(f"**{name.upper()}**<div class='codeblk'>{rendered}</div>", unsafe_allow_html=True)

# --- Tab 7: feedback loop --------------------------------------------------- #
with tabs[6]:
    st.subheader("Continuous Improvement Feedback Loop")
    loop = data.get("feedback_loop", [])
    if loop and HAS_PLOTLY:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[d["iteration"] for d in loop], y=[d["mutation_score"] for d in loop],
            mode="lines+markers+text", text=[f"{d['mutation_score']}%" for d in loop],
            textposition="top center", line=dict(color="#48cae4", width=4),
            marker=dict(size=12, color="#2ea043"), name="Mutation Score",
        ))
        fig.update_layout(
            height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e8f1f5"), xaxis_title="Iteration", yaxis_title="Mutation Score %",
            yaxis=dict(range=[50, 100]),
        )
        st.plotly_chart(fig, width="stretch")
    for d in loop:
        st.markdown(
            f"- **Iteration {d['iteration']}** — score **{d['mutation_score']}%**, "
            f"survived {d['survived']}, AI generated {d['generated']} tests"
        )
    if loop:
        st.success(f"🎯 Target reached: {loop[-1]['mutation_score']}% mutation score "
                   f"(+{loop[-1]['mutation_score'] - loop[0]['mutation_score']}% uplift).")
