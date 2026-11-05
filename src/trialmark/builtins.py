"""The built-in plugins: two runners, two scorers, two loaders and three reports.

They are small on purpose. Each shows one customisation point working, and the
first two runners let a run be tried without any model or API key.
"""

from __future__ import annotations

import csv
import importlib
import importlib.util
import json
import re
import string
from pathlib import Path
from typing import Any

from .plugins import RunOutput, builtin
from .record import ModelEntry, RunRecord
from .report import summarise, text_report
from .testset import Case, TestSet, load_test_set, parse_test_set

# --- Runners --------------------------------------------------------------------


@builtin("runner", "echo")
class EchoRunner:
    """A stand-in model for trying Trialmark and for tests.

    Model settings:
      answer: "reference" (the default) returns the reference, a perfect model;
              "input" returns the input, a model that is always wrong.
      wrong_tags: cases with any of these tags get an empty answer.
      cost_usd: the cost reported for each case (default 0).
    """

    # A stand-in: it calls nothing, so a run of it needs no --yes.
    costs_money = False

    def estimate_cost(self, model: ModelEntry, case: Case) -> float | None:
        return float(model.settings.get("cost_usd", 0))

    def run(self, model: ModelEntry, case: Case) -> RunOutput:
        s = model.settings
        if set(s.get("wrong_tags", [])) & set(case.tags):
            out: Any = ""
        else:
            out = case.input if s.get("answer", "reference") == "input" else case.reference
        return RunOutput(output=out, cost_usd=float(s.get("cost_usd", 0)))


@builtin("runner", "python")
class PythonRunner:
    """Calls a function of your own, so a model can be tested without writing a plugin package.

    Model settings:
      callable: "module:function", for a module Python can import, or
                "path/to/file.py:function", for a file. A relative file path is
                looked up beside the configuration file, then in the folder
                Trialmark is run from.

    The function is called as function(model_id, case_input, settings) and returns
    either the output or a trialmark.RunOutput.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._cache: dict[str, Any] = {}
        self.base_dir = base_dir

    def _function(self, spec: str):
        if spec not in self._cache:
            module, _, name = spec.partition(":")
            if not module or not name:
                raise ValueError(f"callable must look like 'module:function', not '{spec}'.")
            if module.endswith(".py"):
                path = Path(module)
                if not path.is_absolute() and self.base_dir is not None and (self.base_dir / path).exists():
                    path = self.base_dir / path
                loaded = importlib.util.spec_from_file_location(path.stem, path)
                if loaded is None or loaded.loader is None:
                    raise ValueError(f"Cannot load '{module}'.")
                mod = importlib.util.module_from_spec(loaded)
                loaded.loader.exec_module(mod)
            else:
                mod = importlib.import_module(module)
            self._cache[spec] = getattr(mod, name)
        return self._cache[spec]

    def run(self, model: ModelEntry, case: Case) -> RunOutput:
        spec = model.settings.get("callable")
        if not spec:
            raise ValueError(f"Model '{model.id}' uses the python runner but has no 'callable' setting.")
        result = self._function(spec)(model.id, case.input, model.settings)
        return result if isinstance(result, RunOutput) else RunOutput(output=result)


# --- Scorers --------------------------------------------------------------------

_SPACE = re.compile(r"\s+")
_PUNCT = str.maketrans("", "", string.punctuation)


def _normalise(value: Any, normalise: bool) -> str:
    text = "" if value is None else str(value)
    if not normalise:
        return text
    return _SPACE.sub(" ", text.lower().translate(_PUNCT)).strip()


@builtin("scorer", "exact-match")
class ExactMatch:
    """correct = 1 if the output equals the reference, else 0.

    Options:
      normalise: ignore case, punctuation and extra spaces (default true).
      metric: the metric's name (default "correct").
    """

    def __init__(self, normalise: bool = True, metric: str = "correct") -> None:
        self.normalise = normalise
        self.metrics = (metric,)

    def score(self, case: Case, output: Any) -> dict[str, float]:
        same = _normalise(output, self.normalise) == _normalise(case.reference, self.normalise)
        return {self.metrics[0]: 1.0 if same else 0.0}


@builtin("scorer", "fields")
class FieldMatch:
    """For extraction: the reference and the output are objects with named fields.

    fields_correct = the share of the reference's fields the output got right.
    all_fields_correct = 1 only if every field is right.
    An output that is a JSON string is parsed first. Field values are compared
    after the same normalisation as exact-match.

    Options:
      normalise: as for exact-match (default true).
    """

    metrics = ("fields_correct", "all_fields_correct")

    def __init__(self, normalise: bool = True) -> None:
        self.normalise = normalise

    def score(self, case: Case, output: Any) -> dict[str, float]:
        ref = case.reference
        if not isinstance(ref, dict) or not ref:
            raise ValueError(f"Case '{case.id}': the fields scorer needs a reference object with fields.")
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                output = {}
        if not isinstance(output, dict):
            output = {}
        right = sum(
            1 for k, v in ref.items() if _normalise(output.get(k), self.normalise) == _normalise(v, self.normalise)
        )
        return {"fields_correct": right / len(ref), "all_fields_correct": 1.0 if right == len(ref) else 0.0}


# --- Loaders --------------------------------------------------------------------


@builtin("loader", "json")
def load_json(path, **_options) -> TestSet:
    return load_test_set(path)


@builtin("loader", "csv")
def load_csv(path, name: str | None = None, version: str = "1", tag_separator: str = ";", **_options) -> TestSet:
    """A CSV file with the columns id, input and reference, and optionally tags.

    Tags are separated by semicolons. The set's name defaults to the file name.
    """
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for col in ("id", "input", "reference"):
        if rows and col not in rows[0]:
            raise ValueError(f"The CSV file needs a '{col}' column.")
    cases = [
        {
            "id": r["id"],
            "input": r["input"],
            "reference": r["reference"],
            "tags": [t.strip() for t in (r.get("tags") or "").split(tag_separator) if t.strip()],
        }
        for r in rows
    ]
    return parse_test_set({"name": name or Path(path).stem, "version": version, "cases": cases})


# --- Reports --------------------------------------------------------------------


@builtin("report", "text")
def report_text(record: RunRecord, by_tag: bool = False) -> str:
    return text_report(record, by_tag=by_tag)


def _summary_dict(record: RunRecord, tag: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "model": s.model,
            "cases": s.cases,
            "repeats": s.repeats,
            "errors": s.errors,
            "metrics": {k: {"mean": v.mean, "low": v.low, "high": v.high} for k, v in s.metrics.items()},
            "cost_per_100_usd": s.cost_per_100_usd,
            "latency_p50_ms": s.latency_p50_ms,
        }
        for s in summarise(record, tag=tag)
    ]


@builtin("report", "json")
def report_json(record: RunRecord, by_tag: bool = False) -> str:
    from .report import decision

    d = decision(record)
    out: dict[str, Any] = {
        "run_id": record.run_id,
        "test_set": record.test_set,
        "pass_mark": record.pass_mark,
        "models": _summary_dict(record),
        "chosen": d.chosen,
        "verdicts": [{"model": v.model, "passed": v.passed, "reasons": list(v.reasons)} for v in d.verdicts],
    }
    if by_tag:
        tags = sorted({t for r in record.results for t in r.tags})
        out["by_tag"] = {t: _summary_dict(record, tag=t) for t in tags}
    return json.dumps(out, indent=2)


def _md_table(record: RunRecord, tag: str | None, metrics: list[str]) -> list[str]:
    lines = ["| Model | " + " | ".join(metrics) + " | Cost per 100 | Median time |",
             "|---|" + "---|" * len(metrics) + "---|---|"]
    for s in summarise(record, tag=tag):
        cells = []
        for n in metrics:
            m = s.metrics.get(n)
            if m is None:
                cells.append("-")
            elif abs(m.high - m.low) < 1e-9:
                cells.append(f"{m.mean:.0%}")
            else:
                cells.append(f"{m.mean:.0%} ({m.low:.0%} to {m.high:.0%})")
        lines.append(f"| {s.model} | " + " | ".join(cells) + f" | ${s.cost_per_100_usd:.2f} | {s.latency_p50_ms / 1000:.1f}s |")
    return lines


@builtin("report", "markdown")
def report_markdown(record: RunRecord, by_tag: bool = False) -> str:
    from .report import decision

    d = decision(record)
    metrics = sorted({n for s in summarise(record) for n in s.metrics})
    ts = record.test_set
    lines = [
        f"# Trialmark run {record.run_id}",
        "",
        f"Test set **{ts['name']}** version {ts['version']} (`{ts['hash']}`), {record.repeats} repeats.",
        "",
        *_md_table(record, None, metrics),
        "",
        "Ranges are the lowest and highest repeat. Treat differences inside them as no difference.",
        "",
        "## Pass mark",
        "",
        f"Set at {record.pass_mark_set_at} (`{record.pass_mark_hash}`): `{json.dumps(record.pass_mark)}`",
        "",
    ]
    for v in d.verdicts:
        lines.append(f"- **{'Pass' if v.passed else 'Fail'}**: {v.model}" + (f". {'; '.join(v.reasons)}." if v.reasons else ""))
    lines += ["", f"**Chosen:** {d.chosen or 'no model met the pass mark'}"]
    if by_tag:
        for t in sorted({t for r in record.results for t in r.tags}):
            lines += ["", f"## Tag: {t}", "", *_md_table(record, t, metrics)]
    return "\n".join(lines) + "\n"
