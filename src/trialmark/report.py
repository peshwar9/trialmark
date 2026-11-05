"""Summaries and reports: each model's scores, cost and speed, with the range
across repeats, overall and for each tag."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from .passmark import Decision, decide
from .record import Result, RunRecord


@dataclass(frozen=True)
class MetricSummary:
    mean: float
    low: float
    high: float


@dataclass(frozen=True)
class ModelSummary:
    model: str
    cases: int
    repeats: int
    errors: int
    metrics: dict[str, MetricSummary]
    cost_per_100_usd: float
    latency_p50_ms: int


def _summarise(model: str, results: list[Result]) -> ModelSummary:
    by_repeat: dict[int, list[Result]] = {}
    for r in results:
        by_repeat.setdefault(r.repeat, []).append(r)
    names = sorted({k for r in results for k in r.metrics})
    metrics: dict[str, MetricSummary] = {}
    for name in names:
        # Mean within each repeat, then the mean and range across repeats.
        per_repeat = []
        for rs in by_repeat.values():
            vals = [r.metrics[name] for r in rs if name in r.metrics]
            if vals:
                per_repeat.append(sum(vals) / len(vals))
        if per_repeat:
            metrics[name] = MetricSummary(
                mean=sum(per_repeat) / len(per_repeat), low=min(per_repeat), high=max(per_repeat)
            )
    costs = [sum(r.cost_usd for r in rs) / len(rs) * 100 for rs in by_repeat.values() if rs]
    latencies = [r.latency_ms for r in results if r.latency_ms > 0 and r.error is None]
    return ModelSummary(
        model=model,
        cases=len({r.case_id for r in results}),
        repeats=len(by_repeat),
        errors=sum(1 for r in results if r.error),
        metrics=metrics,
        cost_per_100_usd=sum(costs) / len(costs) if costs else 0.0,
        latency_p50_ms=int(statistics.median(latencies)) if latencies else 0,
    )


def summarise(record: RunRecord, tag: str | None = None) -> list[ModelSummary]:
    out = []
    for m in record.models:
        rs = [r for r in record.results if r.model == m.id and (tag is None or tag in r.tags)]
        if rs:
            out.append(_summarise(m.id, rs))
    return out


def decision(record: RunRecord) -> Decision:
    return decide(record.parsed_pass_mark(), summarise(record))


def _pct(m: MetricSummary | None) -> str:
    if m is None:
        return "-"
    if abs(m.high - m.low) < 1e-9:
        return f"{m.mean:.0%}"
    return f"{m.mean:.0%} ({m.low:.0%}-{m.high:.0%})"


def _table(summaries: list[ModelSummary], metrics: list[str]) -> list[str]:
    head = ["Model", *metrics, "Cost/100", "Median time"]
    rows = [
        [
            s.model,
            *(_pct(s.metrics.get(n)) for n in metrics),
            f"${s.cost_per_100_usd:.2f}",
            f"{s.latency_p50_ms / 1000:.1f}s",
        ]
        for s in summaries
    ]
    widths = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
    fmt = lambda r: "  ".join(str(x).ljust(w) for x, w in zip(r, widths)).rstrip()  # noqa: E731
    return [fmt(head), fmt(["-" * w for w in widths]), *map(fmt, rows)]


def text_report(record: RunRecord, by_tag: bool = False) -> str:
    summaries = summarise(record)
    metrics = sorted({n for s in summaries for n in s.metrics})
    pm = record.parsed_pass_mark()
    d = decide(pm, summaries)
    lines = [
        f"Test set   {record.test_set['name']} v{record.test_set['version']} ({record.test_set['hash'][:19]}...)",
        f"Run        {record.run_id}, {record.repeats} repeats, Trialmark {record.trialmark_version}",
    ]
    if record.judge:
        lines.append(f"Judge      {record.judge.get('model', '?')}")
    lines += ["", *_table(summaries, metrics), ""]
    lines.append(
        "Ranges in brackets are the lowest and highest repeat. Treat differences inside them as no difference."
    )
    lines += ["", f"Pass mark  set {record.pass_mark_set_at}: {pm.metric} within {pm.tolerance_points:g} points of the best"
              + "".join(f", {k} at least {v:.0%}" for k, v in pm.floors.items())
              + f"; choose the {pm.choose}."]
    for v in d.verdicts:
        lines.append(f"  {'PASS' if v.passed else 'FAIL'}  {v.model}" + (f": {'; '.join(v.reasons)}" if v.reasons else ""))
    lines.append(f"Chosen     {d.chosen or 'no model met the pass mark'}")
    if by_tag:
        tags = sorted({t for r in record.results for t in r.tags})
        for t in tags:
            lines += ["", f"Tag: {t}", *_table(summarise(record, tag=t), metrics)]
    return "\n".join(lines)
