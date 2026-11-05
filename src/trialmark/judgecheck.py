"""Checking the judge against a person's grades.

A judge model is only worth trusting once you know how often it agrees with a
person. The check has two steps:

1. `trialmark judge-check sample` picks answers from a run and writes them to a
   CSV file with the question, the reference and the answer, and an empty
   `your_verdict` column. The judge's verdict is left out, so it cannot sway you.
2. You fill in `your_verdict` with correct, partial or incorrect, then
   `trialmark judge-check score` compares your grades with the judge's and
   lists every disagreement.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .record import Result, RunRecord
from .testset import TestSet

VERDICTS = ("correct", "partial", "incorrect")
COLUMNS = ["case_id", "model", "repeat", "question", "reference", "answer", "your_verdict"]


def verdict_of(result: Result) -> str:
    """The grade a run gave an answer: correct, partial or incorrect."""
    if result.metrics.get("correct", 0) >= 1:
        return "correct"
    if result.metrics.get("partial", 0) >= 1:
        return "partial"
    return "incorrect"


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ("" if value is None else str(value))


def write_sample(record: RunRecord, test_set: TestSet, path: str | Path, size: int = 20, seed: int = 1) -> int:
    """Write a blind sample of graded answers for a person to grade. Returns how many."""
    if not test_set.matches(record.test_set["hash"]):
        # A subset run has its own hash; accept it when every case is in the set.
        ids = {c.id for c in test_set.cases}
        if any(r.case_id not in ids for r in record.results):
            raise ValueError("The run's cases are not in this test set.")
    cases = {c.id: c for c in test_set.cases}
    pool = [r for r in record.results if r.error is None and r.output not in (None, "")]
    if not pool:
        raise ValueError("The run has no answers to sample.")
    chosen = random.Random(seed).sample(pool, min(size, len(pool)))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in chosen:
            c = cases[r.case_id]
            w.writerow({
                "case_id": r.case_id, "model": r.model, "repeat": r.repeat,
                "question": _text(c.input), "reference": _text(c.reference),
                "answer": _text(r.output), "your_verdict": "",
            })
    return len(chosen)


@dataclass
class Agreement:
    graded: int
    agreed: int
    # (case_id, model, repeat, your verdict, the run's verdict)
    disagreements: list[tuple[str, str, int, str, str]]
    # counts[(yours, the run's)]
    counts: dict[tuple[str, str], int]

    @property
    def rate(self) -> float:
        return self.agreed / self.graded if self.graded else 0.0


def score_grades(record: RunRecord, path: str | Path) -> Agreement:
    """Compare a person's grades with the run's, for every row with a verdict."""
    by_key = {(r.case_id, r.model, r.repeat): r for r in record.results}
    graded = agreed = 0
    disagreements = []
    counts: dict[tuple[str, str], int] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            yours = (row.get("your_verdict") or "").strip().lower()
            if not yours:
                continue
            if yours not in VERDICTS:
                raise ValueError(f"'{row.get('your_verdict')}' is not one of correct, partial or incorrect.")
            key = (row["case_id"], row["model"], int(row["repeat"]))
            if key not in by_key:
                raise ValueError(f"The run has no answer for case {key[0]}, model {key[1]}, repeat {key[2]}.")
            theirs = verdict_of(by_key[key])
            graded += 1
            counts[(yours, theirs)] = counts.get((yours, theirs), 0) + 1
            if yours == theirs:
                agreed += 1
            else:
                disagreements.append((*key, yours, theirs))
    if graded == 0:
        raise ValueError("No row has a verdict in your_verdict yet.")
    return Agreement(graded, agreed, disagreements, counts)


def agreement_report(a: Agreement, judge: str) -> str:
    lines = [
        f"You graded {a.graded} answers. The judge ({judge}) agreed with you on {a.agreed}: {a.rate:.0%}.",
        f"With {a.graded} graded, one answer moves that by {100 / a.graded:.0f} points.",
        "",
        "                    the judge said",
        "you said       " + "".join(f"{v:>11}" for v in VERDICTS),
    ]
    for y in VERDICTS:
        lines.append(f"{y:<15}" + "".join(f"{a.counts.get((y, t), 0):>11}" for t in VERDICTS))
    if a.disagreements:
        lines += ["", "Where you disagree:"]
        for case_id, model, repeat, yours, theirs in a.disagreements:
            lines.append(f"  {case_id} ({model}, repeat {repeat}): you said {yours}, the judge said {theirs}")
    return "\n".join(lines)
