"""Per-label results for classification runs: `trialmark confusion`.

Accuracy alone hides which labels a model gets wrong. For each model this gives,
for every label, its precision (of the answers given that label, the share that
were right), its recall (of the cases that had that label, the share found) and
F1 (their balance), and a table of which labels were mistaken for which.
"""

from __future__ import annotations

from dataclasses import dataclass

from .record import RunRecord
from .scorers import normalise_text, predicted_label
from .testset import TestSet

NONE = "(none)"


@dataclass
class LabelStats:
    label: str
    support: int  # how many answers should have had this label
    precision: float | None
    recall: float | None
    f1: float | None


@dataclass
class ModelConfusion:
    model: str
    answers: int
    accuracy: float
    labels: list[LabelStats]
    # matrix[(expected, predicted)] = count
    matrix: dict[tuple[str, str], int]
    order: list[str]


def confusion(record: RunRecord, test_set: TestSet, labels: list[str] | None = None) -> list[ModelConfusion]:
    refs = {c.id: normalise_text(c.reference) for c in test_set.cases}
    missing = {r.case_id for r in record.results} - set(refs)
    if missing:
        raise ValueError(f"The run has cases that are not in this test set: {', '.join(sorted(missing))}.")
    allowed = [normalise_text(x) for x in labels] if labels else sorted(set(refs.values()))
    out = []
    for m in record.models:
        rs = [r for r in record.results if r.model == m.id]
        if not rs:
            continue
        pairs = [(refs[r.case_id], (predicted_label(r.output, allowed) or NONE) if r.error is None else NONE) for r in rs]
        matrix: dict[tuple[str, str], int] = {}
        for p in pairs:
            matrix[p] = matrix.get(p, 0) + 1
        order = list(allowed) + ([NONE] if any(g == NONE for _, g in pairs) else [])
        stats = []
        for label in allowed:
            tp = matrix.get((label, label), 0)
            given = sum(v for (_, g), v in matrix.items() if g == label)
            support = sum(v for (e, _), v in matrix.items() if e == label)
            precision = tp / given if given else None
            recall = tp / support if support else None
            f1 = (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if given or support else None)
            stats.append(LabelStats(label, support, precision, recall, f1))
        accuracy = sum(1 for e, g in pairs if e == g) / len(pairs)
        out.append(ModelConfusion(m.id, len(pairs), accuracy, stats, matrix, order))
    return out


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v:.0%}"


def confusion_report(results: list[ModelConfusion]) -> str:
    lines: list[str] = []
    for mc in results:
        lines += [f"{mc.model}: {mc.accuracy:.0%} correct over {mc.answers} answers", ""]
        w = max(8, *(len(s.label) for s in mc.labels))
        lines.append(f"  {'label':<{w}}  {'precision':>9}  {'recall':>7}  {'F1':>5}  {'cases':>5}")
        for s in mc.labels:
            lines.append(f"  {s.label:<{w}}  {_pct(s.precision):>9}  {_pct(s.recall):>7}  {_pct(s.f1):>5}  {s.support:>5}")
        cw = max(7, *(len(x) for x in mc.order))
        lines += ["", "  expected (rows) against the model's answer (columns):", "  " + " " * cw + "".join(f"  {x:>{cw}}" for x in mc.order)]
        for e in mc.order:
            if e == NONE:
                continue
            lines.append(f"  {e:<{cw}}" + "".join(f"  {mc.matrix.get((e, g), 0):>{cw}}" for g in mc.order))
        lines.append("")
    lines.append("Precision: of the answers given a label, the share that were right. Recall: of the cases")
    lines.append(f"with a label, the share the model found. {NONE} means the answer matched no allowed label.")
    return "\n".join(lines)
