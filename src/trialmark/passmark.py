"""Pass marks: the decision rule, written down before the run.

A pass mark says which model to choose once the results are in, so the choice
is not made after seeing them:

    {
      "metric": "correct",
      "tolerance_points": 3,
      "floors": {"grounded": 0.95},
      "choose": "cheapest"
    }

Read as: among the models whose mean "grounded" is at least 0.95, every model
within 3 points of the best mean "correct" passes, and the cheapest of those is
chosen. Points are percentage points of a score between 0 and 1.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .testset import canonical_json

CHOOSE_RULES = ("cheapest", "fastest", "best")


@dataclass(frozen=True)
class PassMark:
    metric: str
    tolerance_points: float = 0.0
    floors: dict[str, float] = field(default_factory=dict)
    choose: str = "cheapest"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            # Floats throughout, so 3 and 3.0 hash the same after a round trip.
            "tolerance_points": float(self.tolerance_points),
            "floors": {k: float(v) for k, v in self.floors.items()},
            "choose": self.choose,
        }

    @property
    def hash(self) -> str:
        return "sha256:" + hashlib.sha256(canonical_json(self.to_dict()).encode("utf-8")).hexdigest()


def parse_pass_mark(data: dict[str, Any]) -> PassMark:
    if "metric" not in data:
        raise ValueError("Pass mark is missing 'metric'.")
    choose = data.get("choose", "cheapest")
    if choose not in CHOOSE_RULES:
        raise ValueError(f"Pass mark 'choose' must be one of {', '.join(CHOOSE_RULES)}.")
    tolerance = float(data.get("tolerance_points", 0))
    if tolerance < 0:
        raise ValueError("Pass mark 'tolerance_points' cannot be negative.")
    floors = {str(k): float(v) for k, v in dict(data.get("floors", {})).items()}
    return PassMark(metric=str(data["metric"]), tolerance_points=tolerance, floors=floors, choose=choose)


@dataclass(frozen=True)
class ModelVerdict:
    model: str
    passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    chosen: str | None
    best_score: float | None
    verdicts: tuple[ModelVerdict, ...]

    def verdict_for(self, model: str) -> ModelVerdict | None:
        return next((v for v in self.verdicts if v.model == model), None)


def decide(pass_mark: PassMark, summaries: list[Any]) -> Decision:
    """Apply a pass mark to model summaries (see report.summarise)."""
    scored = [s for s in summaries if pass_mark.metric in s.metrics]
    if not scored:
        return Decision(chosen=None, best_score=None, verdicts=tuple(
            ModelVerdict(s.model, False, (f"no '{pass_mark.metric}' results",)) for s in summaries
        ))
    best = max(s.metrics[pass_mark.metric].mean for s in scored)
    threshold = best - pass_mark.tolerance_points / 100
    verdicts: list[ModelVerdict] = []
    passing = []
    for s in summaries:
        reasons: list[str] = []
        m = s.metrics.get(pass_mark.metric)
        if m is None:
            reasons.append(f"no '{pass_mark.metric}' results")
        elif m.mean < threshold - 1e-9:
            reasons.append(
                f"{pass_mark.metric} {m.mean:.1%} is more than {pass_mark.tolerance_points:g} points below the best {best:.1%}"
            )
        # Failed calls leave the scores incomplete, so the model cannot pass.
        if getattr(s, "errors", 0):
            reasons.append(f"{s.errors} calls failed")
        for name, floor in pass_mark.floors.items():
            fm = s.metrics.get(name)
            if fm is None:
                reasons.append(f"no '{name}' results")
            elif fm.mean < floor - 1e-9:
                reasons.append(f"{name} {fm.mean:.1%} is below the floor of {floor:.1%}")
        verdicts.append(ModelVerdict(s.model, not reasons, tuple(reasons)))
        if not reasons:
            passing.append(s)
    chosen = None
    if passing:
        if pass_mark.choose == "cheapest":
            chosen = min(passing, key=lambda s: (s.cost_per_100_usd, s.model)).model
        elif pass_mark.choose == "fastest":
            chosen = min(passing, key=lambda s: (s.latency_p50_ms, s.model)).model
        else:
            chosen = max(passing, key=lambda s: (s.metrics[pass_mark.metric].mean, -s.cost_per_100_usd)).model
    return Decision(chosen=chosen, best_score=best, verdicts=tuple(verdicts))
