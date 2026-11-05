"""Running a trial: every model on every case, for every repeat, scored and recorded.

The record is started, with the pass mark fixed, before any model is called.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .passmark import PassMark, parse_pass_mark
from .plugins import RunOutput, Runner, Scorer, load_with, make_runner, make_scorer, version_of
from .record import ModelEntry, Result, RunRecord
from .testset import Case, TestSet


def _one(
    runner: Runner, scorers: list[Scorer], model: ModelEntry, case: Case, repeat: int
) -> Result:
    t0 = time.perf_counter()
    try:
        out = runner.run(model, case)
        if not isinstance(out, RunOutput):
            out = RunOutput(output=out)
    except Exception as e:  # a failed call is recorded, not fatal
        out = RunOutput(output=None, error=f"{type(e).__name__}: {e}"[:500])
    latency = out.latency_ms if out.latency_ms is not None else int((time.perf_counter() - t0) * 1000)

    metrics: dict[str, float] = {}
    note = ""
    for scorer in scorers:
        if out.error is not None:
            metrics.update({m: 0.0 for m in scorer.metrics})
            continue
        try:
            got = scorer.score(case, out.output)
        except Exception as e:
            metrics.update({m: 0.0 for m in scorer.metrics})
            note = f"scorer {type(scorer).__name__} failed: {e}"[:500]
            continue
        for k, v in got.items():
            v = float(v)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"Scorer {type(scorer).__name__} returned {k}={v}; metrics must be between 0 and 1.")
            metrics[k] = v
    return Result(
        model=model.id,
        repeat=repeat,
        case_id=case.id,
        tags=list(case.tags),
        metrics=metrics,
        output=out.output,
        cost_usd=out.cost_usd,
        latency_ms=latency,
        input_tokens=out.input_tokens,
        output_tokens=out.output_tokens,
        error=out.error,
        note=note,
    )


def run_trial(
    test_set: TestSet,
    pass_mark: PassMark,
    models: list[ModelEntry],
    runners: dict[str, Runner],
    scorers: list[Scorer],
    repeats: int = 3,
    concurrency: int = 1,
    judge: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
    plugin_versions: dict[str, dict[str, str]] | None = None,
    progress: Callable[[Result], None] | None = None,
) -> RunRecord:
    """Run every model on every case for every repeat and return the record.

    `runners` maps each runner name used in `models` to a runner object, so
    plugin objects can be passed directly from Python.
    """
    if not scorers:
        raise ValueError("A run needs at least one scorer.")
    for m in models:
        if m.runner not in runners:
            raise ValueError(f"Model '{m.id}' names runner '{m.runner}', which was not provided.")
    record = RunRecord.start(test_set, pass_mark, models, repeats=repeats, judge=judge, environment=environment)
    record.plugins = plugin_versions or {
        "runners": {name: type(r).__name__ for name, r in runners.items()},
        "scorers": {type(s).__name__: "" for s in scorers},
    }
    jobs = [(m, c, r) for r in range(repeats) for m in models for c in test_set.cases]

    def work(job):
        m, c, r = job
        return _one(runners[m.runner], scorers, m, c, r)

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        for result in pool.map(work, jobs):
            record.add(result)
            if progress:
                progress(result)
    return record


# --- Running from a configuration file -------------------------------------------


@dataclass
class Config:
    test_set: TestSet
    pass_mark: PassMark
    models: list[ModelEntry]
    runners: dict[str, Runner]
    scorers: list[Scorer]
    repeats: int = 3
    concurrency: int = 1
    judge: dict[str, Any] | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    output: Path | None = None
    plugin_versions: dict[str, dict[str, str]] = field(default_factory=dict)


def load_config(path: str | Path) -> Config:
    """Read a run configuration. Relative paths in it are relative to the file."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    base = path.parent
    for key in ("test_set", "pass_mark", "models", "scorers"):
        if key not in data:
            raise ValueError(f"The configuration is missing '{key}'.")

    ts_spec = data["test_set"]
    if isinstance(ts_spec, str):
        ts_spec = {"path": ts_spec}
    test_set = load_with(base / ts_spec["path"], ts_spec.get("loader"), ts_spec.get("options"))

    models = []
    for m in data["models"]:
        if "id" not in m or "runner" not in m:
            raise ValueError("Each model needs an 'id' and a 'runner'.")
        models.append(ModelEntry(id=m["id"], provider=m.get("provider", ""), settings=m.get("settings", {}), runner=m["runner"]))

    runner_options = data.get("runners", {})
    runners = {name: make_runner(name, runner_options.get(name)) for name in sorted({m.runner for m in models})}

    scorers = []
    scorer_versions = {}
    for s in data["scorers"]:
        s = {"name": s} if isinstance(s, str) else s
        scorers.append(make_scorer(s["name"], s.get("options")))
        scorer_versions[s["name"]] = version_of("scorer", s["name"])

    return Config(
        test_set=test_set,
        pass_mark=parse_pass_mark(data["pass_mark"]),
        models=models,
        runners=runners,
        scorers=scorers,
        repeats=int(data.get("repeats", 3)),
        concurrency=int(data.get("concurrency", 1)),
        judge=data.get("judge"),
        environment=dict(data.get("environment", {})),
        output=base / data["output"] if data.get("output") else None,
        plugin_versions={"runners": {n: version_of("runner", n) for n in runners}, "scorers": scorer_versions},
    )


def run_config(config: Config, progress: Callable[[Result], None] | None = None) -> RunRecord:
    return run_trial(
        config.test_set,
        config.pass_mark,
        config.models,
        config.runners,
        config.scorers,
        repeats=config.repeats,
        concurrency=config.concurrency,
        judge=config.judge,
        environment=config.environment,
        plugin_versions=config.plugin_versions,
        progress=progress,
    )
