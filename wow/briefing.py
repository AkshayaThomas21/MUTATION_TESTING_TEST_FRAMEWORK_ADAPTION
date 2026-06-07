"""
MutaSentinel Briefing — a self-contained, animated HTML executive report.

No server, no external assets, no internet. One double-clickable .html file that
tells the whole story: the safety verdict, the score climbing after AI self-healing,
the test-genome radar, the € risk mitigated, and the auto-generated tests.

Built with placeholder replacement (not f-strings) so the inline CSS/JS braces
stay intact.
"""

from __future__ import annotations

import os
import html as _html
import math
from datetime import datetime
from typing import Any, Dict, List, Tuple

from wow.safety_compliance import SafetyComplianceEngine, SafetyAssessment, ASIL
from wow.roi_engine import ROIEngine, ROIAssessment
from wow.test_genome import TestGenomeEngine, TestGenome

CODENAME = "MUTASENTINEL"
TAGLINE = "ASIL-Aware Mutation Intelligence"


def project_score(report: Any) -> Tuple[float, float, int]:
    """Returns (baseline_score, projected_after_AI, survivors_now_killable)."""
    s4 = report.stage4
    if not s4:
        return 0.0, 0.0, 0
    killed, survived = s4.killed, s4.survived
    denom = killed + survived
    baseline = round(killed / denom * 100, 1) if denom else 0.0
    accepted = report.stage5.accepted if report.stage5 else []
    killable = {(t.method, t.mutant_id) for t in accepted}
    new_kills = sum(1 for sv in s4.survivors if (sv.method, sv.mutant_id) in killable)
    projected = round((killed + new_kills) / denom * 100, 1) if denom else 0.0
    return baseline, projected, new_kills


# --------------------------------------------------------------------- #
def _radar_svg(genome: TestGenome) -> str:
    cx, cy, R = 175, 165, 120
    n = len(genome.axes)
    norm = genome.normalized()
    ang = lambda i: -math.pi / 2 + i * (2 * math.pi / n)

    grid = []
    for ring in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(
            f"{cx + R*ring*math.cos(ang(i)):.1f},{cy + R*ring*math.sin(ang(i)):.1f}"
            for i in range(n)
        )
        grid.append(f'<polygon points="{pts}" class="grid" />')
    spokes, labels = [], []
    for i, axis in enumerate(genome.axes):
        x, y = cx + R * math.cos(ang(i)), cy + R * math.sin(ang(i))
        spokes.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" class="spoke" />')
        lx, ly = cx + (R + 22) * math.cos(ang(i)), cy + (R + 16) * math.sin(ang(i))
        anchor = "middle"
        if lx < cx - 5:
            anchor = "end"
        elif lx > cx + 5:
            anchor = "start"
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" class="axislbl">'
            f'{_html.escape(axis)} ({genome.values[i]})</text>'
        )
    data_pts = " ".join(
        f"{cx + R*norm[i]*math.cos(ang(i)):.1f},{cy + R*norm[i]*math.sin(ang(i)):.1f}"
        for i in range(n)
    )
    dots = "".join(
        f'<circle cx="{cx + R*norm[i]*math.cos(ang(i)):.1f}" '
        f'cy="{cy + R*norm[i]*math.sin(ang(i)):.1f}" r="3.5" class="dot" />'
        for i in range(n)
    )
    return (
        f'<svg viewBox="0 0 350 340" class="radar">'
        + "".join(grid) + "".join(spokes)
        + f'<polygon points="{data_pts}" class="genome" />'
        + dots + "".join(labels)
        + "</svg>"
    )


def _kpi(value: str, target: float, label: str, sub: str, accent: str,
         prefix: str = "", suffix: str = "", decimals: int = 0) -> str:
    return (
        f'<div class="kpi {accent}">'
        f'<div class="kpi-val num" data-target="{target}" data-prefix="{prefix}" '
        f'data-suffix="{suffix}" data-dec="{decimals}">{prefix}0{suffix}</div>'
        f'<div class="kpi-label">{_html.escape(label)}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )


def _eur(x: float) -> str:
    return f"{x:,.0f}"


# --------------------------------------------------------------------- #
def generate_briefing(
    report: Any,
    project: str = "Demo Project",
    out_path: str = os.path.join("temp", "mutasentinel_briefing.html"),
    target_asil: str = "D",
) -> Dict[str, Any]:
    eng = SafetyComplianceEngine(ASIL(target_asil))
    safety_before = eng.assess(report)
    # survivors that an accepted AI test now kills -> project the post-AI safety state
    accepted = report.stage5.accepted if report.stage5 else []
    promoted = {(t.method, t.mutant_id) for t in accepted}
    safety = eng.assess(report, promoted_to_killed=promoted)   # the AFTER state (headline)
    roi = ROIEngine().assess(report)
    genome = TestGenomeEngine().build(report)
    baseline, projected, new_kills = project_score(report)

    framework = (report.framework or "gtest").upper()
    ts = datetime.now().strftime("%d %b %Y, %H:%M")

    verdict_ok = safety.certified
    banner_class = "ok" if verdict_ok else ("warn" if safety.achieved_asil != "QM" else "bad")
    asil_badge = "ASIL " + safety.achieved_asil if safety.achieved_asil != "QM" else "QM only"

    # KPI row
    kpis = "".join([
        _kpi("", projected, "Mutation Score", f"climbed from {baseline}%", "teal",
             suffix="%", decimals=1),
        _kpi("", safety.safety_confidence_index, "Safety Confidence", "ISO 26262-weighted",
             "violet", suffix="%", decimals=1),
        _kpi("", len(safety.blind_spots), "Safety Blind Spots",
             f"{safety.critical_count} critical · {safety.high_count} high", "amber"),
        _kpi("", len(report.stage5.accepted) if report.stage5 else 0, "AI Tests Synthesised",
             f"of {len(report.stage5.tests) if report.stage5 else 0} generated", "green"),
        _kpi("", roi.risk_mitigated_eur, "Field-Risk Mitigated", "vs manual review", "rose",
             prefix="€"),
    ])

    # Score climb bars
    climb = (
        f'<div class="climb">'
        f'<div class="climb-row"><span>Before AI</span>'
        f'<div class="bar"><div class="fill base" style="--w:{baseline}%"></div>'
        f'<b>{baseline}%</b></div></div>'
        f'<div class="climb-row"><span>After AI self-heal</span>'
        f'<div class="bar"><div class="fill after" style="--w:{projected}%"></div>'
        f'<b>{projected}%</b></div></div>'
        f'<div class="climb-note">+{new_kills} surviving mutant(s) now killed by '
        f'auto-generated tests &nbsp;→&nbsp; <strong>+{round(projected-baseline,1)} pts</strong></div>'
        f'</div>'
    )

    # ASIL panel: per-method bars + verdict + blind spots
    method_bars = "".join(
        f'<div class="mrow"><span class="mname">{_html.escape(m)}</span>'
        f'<div class="bar small"><div class="fill mfill" style="--w:{sci}%"></div></div>'
        f'<span class="mpct">{sci}%</span></div>'
        for m, sci in sorted(safety.per_method.items(), key=lambda kv: kv[1])
    )
    sev_class = {"Critical": "sev-crit", "High": "sev-high", "Medium": "sev-med", "Low": "sev-low"}
    spots = "".join(
        f'<li class="{sev_class.get(b.severity,"sev-med")}">'
        f'<span class="sev">{b.severity}</span>'
        f'<span class="spot-method">{_html.escape(b.method)}</span>'
        f'<span class="spot-rc">{_html.escape(b.root_cause)}</span>'
        f'<span class="spot-fix">{_html.escape(b.suggested_focus)}</span></li>'
        for b in safety.blind_spots[:8]
    ) or '<li class="sev-low"><span class="sev">None</span>No safety blind spots — clean suite.</li>'

    asil_panel = (
        f'<div class="panel">'
        f'<h3>🛡️ ISO 26262 Safety Certification</h3>'
        f'<div class="asil-head">'
        f'<div class="asil-climb">'
        f'<div class="asil-dial bad small"><div class="asil-grade">{safety_before.achieved_asil}</div>'
        f'<div class="asil-cap">before AI</div></div>'
        f'<div class="asil-to">→</div>'
        f'<div class="asil-dial {banner_class}"><div class="asil-grade">{safety.achieved_asil}</div>'
        f'<div class="asil-cap">after AI</div></div></div>'
        f'<div class="asil-meta"><div>Target: <strong>ASIL {safety.target_asil}</strong></div>'
        f'<div>SCI: <strong>{safety_before.safety_confidence_index}% → {safety.safety_confidence_index}%</strong></div>'
        f'<div class="asil-clause">{_html.escape(safety.iso_clause)}</div></div></div>'
        f'<div class="verdict {banner_class}">{_html.escape(safety.verdict)}</div>'
        f'<h4>Per-function safety coverage (post-AI)</h4>{method_bars}'
        f'<h4>Residual safety blind spots</h4><ul class="spots">{spots}</ul>'
        f'</div>'
    )

    # Genome panel
    genome_panel = (
        f'<div class="panel">'
        f'<h3>🧬 Test Genome — weakness fingerprint</h3>'
        f'{_radar_svg(genome)}'
        f'<div class="genome-meta">Dominant gap: <strong>{_html.escape(genome.dominant)}</strong>'
        f' &nbsp;·&nbsp; Signature <code>{_html.escape(genome.fingerprint)}</code></div>'
        f'</div>'
    )

    # ROI panel
    roi_panel = (
        f'<div class="panel roi">'
        f'<h3>💶 Return on Investment</h3>'
        f'<div class="roi-grid">'
        f'<div class="roi-cell big"><div class="num" data-target="{roi.net_value_eur}" '
        f'data-prefix="€" data-dec="0">€0</div><span>Net value created</span></div>'
        f'<div class="roi-cell"><div class="num" data-target="{roi.payback_ratio}" '
        f'data-suffix="×" data-dec="0">0×</div><span>Return per €1 of AI spend</span></div>'
        f'<div class="roi-cell"><div class="num" data-target="{roi.defects_prevented}" '
        f'data-dec="2">0</div><span>Expected field defects prevented</span></div>'
        f'<div class="roi-cell"><div class="num" data-target="{roi.engineer_hours_saved}" '
        f'data-dec="1">0</div><span>Engineer hours saved</span></div>'
        f'<div class="roi-cell"><div class="num" data-target="{roi.ai_cost_eur}" '
        f'data-prefix="€" data-dec="3">€0</div><span>Total AI cost</span></div>'
        f'<div class="roi-cell"><div class="num" data-target="{roi.manual_days_saved}" '
        f'data-dec="1">0</div><span>Manual analysis days saved</span></div>'
        f'</div>'
        f'<div class="assump">Assumptions: €{_eur(roi.model["field_defect_cost_eur"])}/escaped defect · '
        f'{int(roi.model["escape_base_probability"]*100)}% base escape prob · '
        f'€{roi.model["engineer_rate_eur_h"]}/h · {int(roi.model["manual_test_minutes"])} min/test manual.</div>'
        f'</div>'
    )

    # Pipeline timeline
    stages = [
        ("1", "Code Intelligence", f"{len(report.stage1.methods)} fns · {len(report.stage1.gaps)} gaps"),
        ("2", "LLM Mutation", f"{len(report.stage2.selected)} mutants · {len(report.stage2.rejected)} filtered"),
        ("3", "Parallel Execution", f"{len(report.execution_results)} runs · {report.resource_summary.get('max_workers')} workers"),
        ("4", "Result Analysis", f"{report.stage4.killed} killed · {report.stage4.survived} survived"),
        ("5", "AI Test Synthesis", f"{len(report.stage5.accepted)} tests integrated"),
    ]
    timeline = "".join(
        f'<div class="stage" style="--d:{i*0.12}s"><div class="stage-no">{no}</div>'
        f'<div class="stage-name">{_html.escape(name)}</div>'
        f'<div class="stage-sub">{_html.escape(sub)}</div></div>'
        + ('<div class="stage-arrow">→</div>' if i < len(stages) - 1 else "")
        for i, (no, name, sub) in enumerate(stages)
    )

    # Generated tests
    test_cards = ""
    for t in (report.stage5.accepted if report.stage5 else [])[:6]:
        test_cards += (
            f'<div class="test-card"><div class="tc-head">'
            f'<span class="tc-method">{_html.escape(t.method)}</span>'
            f'<span class="tc-rc">{_html.escape(t.root_cause)}</span>'
            f'<span class="tc-conf">conf {t.confidence}</span></div>'
            f'<pre class="tc-code">{_html.escape(t.rendered.strip())}</pre></div>'
        )
    if not test_cards:
        test_cards = '<div class="test-card"><em>No survivors required synthesis.</em></div>'

    body = (
        f'<header class="hero {banner_class}">'
        f'<div class="brand"><span class="logo">◈</span> {CODENAME}'
        f'<span class="tag">{TAGLINE}</span></div>'
        f'<div class="hero-mid"><div class="verdict-badge {banner_class}">{asil_badge}</div>'
        f'<div class="hero-verdict">{ "CERTIFICATION READY" if verdict_ok else "ACTION REQUIRED" }</div></div>'
        f'<div class="meta"><div><strong>{_html.escape(project)}</strong></div>'
        f'<div class="chip">{framework}</div><div>{ts}</div></div>'
        f'</header>'
        f'<section class="kpis">{kpis}</section>'
        f'<section class="climb-wrap"><h3>📈 AI self-healing impact</h3>{climb}</section>'
        f'<section class="cols"><div class="col">{asil_panel}</div>'
        f'<div class="col side">{genome_panel}{roi_panel}</div></section>'
        f'<section class="timeline-wrap"><h3>⚙️ 5-Stage AI Pipeline</h3>'
        f'<div class="timeline">{timeline}</div></section>'
        f'<section class="tests-wrap"><h3>🤖 Auto-generated tests that close the gaps</h3>'
        f'<div class="tests">{test_cards}</div></section>'
        f'<footer>Generated by {CODENAME} · {TAGLINE} · {ts} · '
        f'Offline · No data left this machine.</footer>'
    )

    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{CODENAME} — {_html.escape(project)}</title>"
        + _STYLE + "</head><body>" + body + _SCRIPT + "</body></html>"
    )

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)

    return {
        "path": os.path.abspath(out_path),
        "safety": safety.to_dict(),
        "safety_before": safety_before.to_dict(),
        "roi": roi.to_dict(),
        "genome": genome.to_dict(),
        "baseline_score": baseline,
        "projected_score": projected,
    }


# ===================================================================== #
_STYLE = """<style>
:root{--bg:#0a0e1a;--bg2:#111726;--card:#161d30;--line:#24304a;--ink:#e8edf7;
--mut:#8a97b5;--teal:#1fc8a9;--violet:#8b7bf0;--amber:#f5b53d;--green:#37d67a;
--rose:#ff6b8a;--ok:#37d67a;--warn:#f5b53d;--bad:#ff5470;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(1200px 600px at 70% -10%,#16203a 0%,var(--bg) 60%);
color:var(--ink);font:14px/1.5 'Segoe UI',system-ui,sans-serif;padding:28px;max-width:1180px;margin:auto}
h3{font-size:15px;letter-spacing:.3px;margin-bottom:12px;color:#cdd6ec}
h4{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--mut);margin:16px 0 8px}
.hero{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:18px;
padding:22px 26px;border-radius:18px;background:linear-gradient(135deg,#141d33,#0d1322);
border:1px solid var(--line);position:relative;overflow:hidden}
.hero:before{content:'';position:absolute;inset:0;opacity:.5;
background:linear-gradient(90deg,transparent,rgba(31,200,169,.08),transparent)}
.hero.ok{box-shadow:0 0 0 1px rgba(55,214,122,.25),0 18px 50px -20px rgba(55,214,122,.4)}
.hero.warn{box-shadow:0 0 0 1px rgba(245,181,61,.25),0 18px 50px -20px rgba(245,181,61,.4)}
.hero.bad{box-shadow:0 0 0 1px rgba(255,84,112,.3),0 18px 50px -20px rgba(255,84,112,.45)}
.brand{font-weight:800;font-size:20px;letter-spacing:2px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.logo{color:var(--teal);font-size:22px}
.tag{font-size:11px;font-weight:600;letter-spacing:1px;color:var(--mut);width:100%;margin-top:2px}
.hero-mid{text-align:center}
.verdict-badge{font-weight:800;font-size:22px;letter-spacing:1px;padding:10px 20px;border-radius:12px;
background:#0c1322;border:1px solid var(--line);display:inline-block}
.verdict-badge.ok{color:var(--ok);border-color:rgba(55,214,122,.5)}
.verdict-badge.warn{color:var(--warn);border-color:rgba(245,181,61,.5)}
.verdict-badge.bad{color:var(--bad);border-color:rgba(255,84,112,.5)}
.hero-verdict{font-size:11px;letter-spacing:2px;color:var(--mut);margin-top:8px;text-transform:uppercase}
.meta{text-align:right;color:var(--mut);font-size:12px;display:flex;flex-direction:column;gap:4px;align-items:flex-end}
.meta strong{color:var(--ink);font-size:14px}
.chip{display:inline-block;background:#0c1322;border:1px solid var(--line);border-radius:20px;
padding:2px 12px;font-weight:700;color:var(--teal);font-size:11px;letter-spacing:1px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 16px;
position:relative;overflow:hidden}
.kpi:before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px}
.kpi.teal:before{background:var(--teal)} .kpi.violet:before{background:var(--violet)}
.kpi.amber:before{background:var(--amber)} .kpi.green:before{background:var(--green)}
.kpi.rose:before{background:var(--rose)}
.kpi-val{font-size:30px;font-weight:800;letter-spacing:-.5px}
.kpi.teal .kpi-val{color:var(--teal)} .kpi.violet .kpi-val{color:var(--violet)}
.kpi.amber .kpi-val{color:var(--amber)} .kpi.green .kpi-val{color:var(--green)}
.kpi.rose .kpi-val{color:var(--rose)}
.kpi-label{font-size:12px;font-weight:700;margin-top:4px}
.kpi-sub{font-size:11px;color:var(--mut);margin-top:2px}
section{margin:22px 0}
.climb-wrap,.timeline-wrap,.tests-wrap{background:var(--card);border:1px solid var(--line);
border-radius:14px;padding:20px}
.climb-row{display:grid;grid-template-columns:140px 1fr;align-items:center;gap:14px;margin:10px 0}
.climb-row>span{color:var(--mut);font-size:12px}
.bar{position:relative;height:26px;background:#0c1322;border-radius:8px;overflow:hidden;
display:flex;align-items:center}
.bar.small{height:14px}
.fill{height:100%;width:0;border-radius:8px;animation:grow 1.4s cubic-bezier(.2,.8,.2,1) forwards}
.fill.base{background:linear-gradient(90deg,#566,#7a89a8)}
.fill.after{background:linear-gradient(90deg,var(--teal),#37d67a)}
.fill.mfill{background:linear-gradient(90deg,var(--violet),var(--teal))}
.bar b{position:absolute;right:10px;font-size:12px;font-weight:800;color:#fff;
text-shadow:0 1px 3px rgba(0,0,0,.6)}
@keyframes grow{to{width:var(--w)}}
.climb-note{margin-top:10px;font-size:12px;color:var(--mut)}
.climb-note strong{color:var(--teal)}
.cols{display:grid;grid-template-columns:1.25fr 1fr;gap:16px;align-items:start}
.col.side{display:flex;flex-direction:column;gap:16px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}
.asil-head{display:flex;gap:18px;align-items:center;margin-bottom:12px}
.asil-climb{display:flex;align-items:center;gap:10px}
.asil-to{font-size:22px;color:var(--teal);font-weight:800}
.asil-dial{width:84px;height:84px;border-radius:50%;display:grid;place-items:center;
background:conic-gradient(var(--line) 0,var(--line) 360deg);border:3px solid var(--line);position:relative}
.asil-dial.small{width:64px;height:64px}
.asil-dial.small .asil-grade{font-size:22px}
.asil-dial.ok{border-color:var(--ok);box-shadow:0 0 24px -6px var(--ok)}
.asil-dial.warn{border-color:var(--warn);box-shadow:0 0 24px -6px var(--warn)}
.asil-dial.bad{border-color:var(--bad);box-shadow:0 0 24px -6px var(--bad)}
.asil-grade{font-size:30px;font-weight:800;line-height:1}
.asil-dial.ok .asil-grade{color:var(--ok)} .asil-dial.warn .asil-grade{color:var(--warn)}
.asil-dial.bad .asil-grade{color:var(--bad)}
.asil-cap{font-size:9px;letter-spacing:1px;color:var(--mut);text-transform:uppercase}
.asil-meta div{font-size:13px;margin:2px 0}
.asil-clause{font-size:10px;color:var(--mut);margin-top:6px}
.verdict{padding:12px 14px;border-radius:10px;font-size:13px;font-weight:600;line-height:1.45;
background:#0c1322;border-left:4px solid var(--line)}
.verdict.ok{border-color:var(--ok);color:#bff0d2} .verdict.warn{border-color:var(--warn);color:#f6e0b0}
.verdict.bad{border-color:var(--bad);color:#ffc6d2}
.mrow{display:grid;grid-template-columns:120px 1fr 44px;align-items:center;gap:10px;margin:6px 0}
.mname{font-size:12px;color:#cdd6ec;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mpct{font-size:12px;font-weight:700;text-align:right;color:var(--teal)}
.spots{list-style:none;display:flex;flex-direction:column;gap:6px}
.spots li{display:grid;grid-template-columns:78px 110px 130px 1fr;gap:8px;align-items:center;
background:#0c1322;border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:11.5px}
.sev{font-weight:800;font-size:10px;letter-spacing:.5px;text-transform:uppercase;text-align:center;
padding:3px 6px;border-radius:6px}
.sev-crit .sev{background:rgba(255,84,112,.18);color:var(--bad)}
.sev-high .sev{background:rgba(245,181,61,.18);color:var(--amber)}
.sev-med .sev{background:rgba(139,123,240,.18);color:var(--violet)}
.sev-low .sev{background:rgba(55,214,122,.15);color:var(--green)}
.spot-method{font-weight:700;color:#dbe3f5} .spot-rc{color:var(--mut)} .spot-fix{color:#aeb8d4}
.radar{width:100%;max-width:360px;display:block;margin:0 auto}
.radar .grid{fill:none;stroke:var(--line);stroke-width:1}
.radar .spoke{stroke:var(--line);stroke-width:1}
.radar .genome{fill:rgba(31,200,169,.22);stroke:var(--teal);stroke-width:2;
animation:radarin 1.2s ease forwards;transform-origin:175px 165px;transform:scale(.2);opacity:0}
@keyframes radarin{to{transform:scale(1);opacity:1}}
.radar .dot{fill:var(--teal)} .radar .axislbl{fill:var(--mut);font-size:11px;font-weight:600}
.genome-meta{text-align:center;font-size:12px;color:var(--mut);margin-top:6px}
.genome-meta code{background:#0c1322;padding:2px 8px;border-radius:6px;color:var(--teal);font-weight:700}
.roi-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.roi-cell{background:#0c1322;border:1px solid var(--line);border-radius:10px;padding:12px;text-align:center}
.roi-cell .num{font-size:20px;font-weight:800;color:var(--rose)}
.roi-cell.big{grid-column:span 3}.roi-cell.big .num{font-size:34px;color:var(--green)}
.roi-cell span{display:block;font-size:10.5px;color:var(--mut);margin-top:3px}
.assump{font-size:10.5px;color:var(--mut);margin-top:12px;line-height:1.5}
.timeline{display:flex;align-items:stretch;gap:8px;flex-wrap:wrap}
.stage{flex:1;min-width:150px;background:#0c1322;border:1px solid var(--line);border-radius:12px;
padding:14px;opacity:0;transform:translateY(10px);animation:rise .5s ease forwards;animation-delay:var(--d)}
@keyframes rise{to{opacity:1;transform:none}}
.stage-no{width:26px;height:26px;border-radius:50%;background:var(--teal);color:#06281f;
font-weight:800;display:grid;place-items:center;margin-bottom:8px}
.stage-name{font-weight:700;font-size:13px} .stage-sub{font-size:11px;color:var(--mut);margin-top:3px}
.stage-arrow{display:flex;align-items:center;color:var(--line);font-size:20px}
.tests{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.test-card{background:#0c1322;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tc-head{display:flex;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line)}
.tc-method{font-weight:800;color:var(--teal)} .tc-rc{font-size:11px;color:var(--amber)}
.tc-conf{margin-left:auto;font-size:11px;color:var(--mut)}
.tc-code{padding:12px;font:12px/1.5 'Cascadia Code',Consolas,monospace;color:#c8d3ef;
white-space:pre-wrap;overflow-x:auto}
footer{text-align:center;color:var(--mut);font-size:11px;margin-top:26px;padding-top:16px;
border-top:1px solid var(--line)}
@media(max-width:880px){.kpis{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}
.tests{grid-template-columns:1fr}.hero{grid-template-columns:1fr}}
</style>"""

_SCRIPT = """<script>
(function(){
  function animate(el){
    var target=parseFloat(el.dataset.target||'0'),dec=parseInt(el.dataset.dec||'0'),
        pre=el.dataset.prefix||'',suf=el.dataset.suffix||'',t0=null,dur=1400;
    function fmt(v){var s=dec>0?v.toFixed(dec):Math.round(v).toLocaleString('en-US');
      if(dec>0&&Math.abs(target)>=1000)s=Number(v.toFixed(dec)).toLocaleString('en-US',{minimumFractionDigits:dec});
      return pre+s+suf;}
    function step(ts){if(!t0)t0=ts;var p=Math.min((ts-t0)/dur,1),
      e=1-Math.pow(1-p,3);el.textContent=fmt(target*e);if(p<1)requestAnimationFrame(step);}
    requestAnimationFrame(step);
  }
  var io=new IntersectionObserver(function(ents){ents.forEach(function(en){
    if(en.isIntersecting){animate(en.target);io.unobserve(en.target);}});},{threshold:.4});
  document.querySelectorAll('.num').forEach(function(n){io.observe(n);});
})();
</script>"""
