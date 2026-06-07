"""
ROI / Cost Engine.

Translates mutation blind spots into the language management understands: money
and time. Every surviving safety-relevant mutant is a *probable escaped defect*;
in automotive, a field defect is orders of magnitude more expensive than a test.

All assumptions are explicit and configurable, and are surfaced in the briefing
so the numbers are transparent rather than magical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from wow.safety_compliance import category_weight


@dataclass
class CostModel:
    field_defect_cost_eur: float = 28000.0     # avg cost to fix one escaped automotive defect
    escape_base_probability: float = 0.18      # P(a surviving mutant -> real escaped defect)
    manual_test_minutes: float = 25.0          # engineer time to hand-write one good test
    engineer_rate_eur_h: float = 92.0          # loaded hourly rate
    ai_base_cost_eur: float = 0.38             # LLM cost for mutation gen + root-cause for the run
    ai_cost_per_test_eur: float = 0.012        # LLM cost to synthesise one test
    manual_mutation_days: float = 4.0          # doing this analysis by hand, per module

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ROIAssessment:
    risk_before_eur: float
    risk_after_eur: float
    risk_mitigated_eur: float
    engineer_hours_saved: float
    engineer_cost_saved_eur: float
    ai_cost_eur: float
    net_value_eur: float
    payback_ratio: float                       # value returned per €1 of AI spend
    manual_days_saved: float
    tests_generated: int
    defects_prevented: float
    model: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class ROIEngine:
    def __init__(self, model: CostModel | None = None) -> None:
        self.model = model or CostModel()

    def assess(self, report: Any) -> ROIAssessment:
        m = self.model
        survivors = report.stage4.survivors if report.stage4 else []
        accepted = report.stage5.accepted if report.stage5 else []
        generated = report.stage5.tests if report.stage5 else []

        # Which survivors does an accepted test cover? (matched by method + mutant id)
        covered = {(t.method, t.mutant_id) for t in accepted}

        def escape_prob(weight: float) -> float:
            # more safety-relevant categories escape into the field more readily
            return min(0.95, m.escape_base_probability * (0.5 + weight))

        risk_before = 0.0
        risk_after = 0.0
        defects_prevented = 0.0
        for s in survivors:
            w = category_weight(s.category)
            p = escape_prob(w)
            risk_before += p * m.field_defect_cost_eur
            if (s.method, s.mutant_id) in covered:
                defects_prevented += p
            else:
                risk_after += p * m.field_defect_cost_eur

        risk_mitigated = round(risk_before - risk_after, 2)

        n_accept = len(accepted)
        hours_saved = round(n_accept * m.manual_test_minutes / 60.0, 2)
        eng_saved = round(hours_saved * m.engineer_rate_eur_h, 2)
        ai_cost = round(m.ai_base_cost_eur + len(generated) * m.ai_cost_per_test_eur, 3)
        net = round(risk_mitigated + eng_saved - ai_cost, 2)
        # payback is genuinely large (field defects are expensive); cap the display
        # at a credible ceiling so it reads as a metric, not a glitch.
        raw_payback = (risk_mitigated + eng_saved) / ai_cost if ai_cost else 0.0
        payback = round(min(raw_payback, 5000.0), 0)
        methods = len(report.stage1.methods) if report.stage1 else 1

        return ROIAssessment(
            risk_before_eur=round(risk_before, 2),
            risk_after_eur=round(risk_after, 2),
            risk_mitigated_eur=risk_mitigated,
            engineer_hours_saved=hours_saved,
            engineer_cost_saved_eur=eng_saved,
            ai_cost_eur=ai_cost,
            net_value_eur=net,
            payback_ratio=payback,
            manual_days_saved=round(m.manual_mutation_days * max(methods, 1), 1),
            tests_generated=len(generated),
            defects_prevented=round(defects_prevented, 2),
            model=m.to_dict(),
        )
