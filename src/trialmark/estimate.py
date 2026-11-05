"""What a run will cost, before it runs.

Each runner and scorer may offer `estimate_cost`: a runner's takes (model, case),
a scorer's takes (case), and both return US dollars or None when the cost is
unknown, as it is for your own function in the python runner. The core adds them
up across models, cases and repeats.

A plugin may also set `costs_money`. `trialmark run` asks for --yes before any
run where a runner or scorer costs money; runners are assumed to unless they say
otherwise, scorers are assumed not to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .run import Config


@dataclass
class Estimate:
    # Per model: the estimated cost of every answer, or None when unknown.
    answers: dict[str, float | None] = field(default_factory=dict)
    # Per scorer that charges: the estimated cost of grading every answer.
    scoring: dict[str, float | None] = field(default_factory=dict)

    @property
    def known_total(self) -> float:
        return sum(v for v in [*self.answers.values(), *self.scoring.values()] if v is not None)

    @property
    def unknown(self) -> list[str]:
        return [k for k, v in [*self.answers.items(), *self.scoring.items()] if v is None]


def estimate_run(config: Config) -> Estimate:
    est = Estimate()
    cases = config.test_set.cases
    for m in config.models:
        runner = config.runners[m.runner]
        fn = getattr(runner, "estimate_cost", None)
        if fn is None:
            est.answers[m.id] = None
            continue
        per = [fn(m, c) for c in cases]
        est.answers[m.id] = None if any(p is None for p in per) else sum(per) * config.repeats  # type: ignore[arg-type]
    for s in config.scorers:
        fn = getattr(s, "estimate_cost", None)
        if fn is None:
            continue
        name = getattr(s, "judge", {}).get("model") if isinstance(getattr(s, "judge", None), dict) else None
        label = f"judge {name}" if name else type(s).__name__
        per = [fn(c) for c in cases]
        est.scoring[label] = (
            None if any(p is None for p in per) else sum(per) * config.repeats * len(config.models)  # type: ignore[arg-type]
        )
    return est


def needs_confirmation(config: Config) -> bool:
    """Whether the run can spend money, so `trialmark run` should ask for --yes."""
    return any(getattr(r, "costs_money", True) for r in config.runners.values()) or any(
        getattr(s, "costs_money", False) for s in config.scorers
    )
