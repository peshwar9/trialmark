"""Scorers for kinds of task beyond question answering: labels (classification),
numbers (calculations and figures) and JSON that must match a schema (structured
output). The checklist scorer, which needs a model, is in providers.py.

See docs/tasks.md for which scorer suits which task.
"""

from __future__ import annotations

import json
import re
import string
from pathlib import Path
from typing import Any

from .plugins import builtin
from .testset import Case

_SPACE = re.compile(r"\s+")
_PUNCT = str.maketrans("", "", string.punctuation)
_FENCE = re.compile(r"^\s*```[a-zA-Z0-9]*\s*\n(.*?)\n\s*```\s*$", re.DOTALL)
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?%?|-?\.\d+%?")


def normalise_text(value: Any) -> str:
    """Lower case, no punctuation, single spaces."""
    text = "" if value is None else str(value)
    return _SPACE.sub(" ", text.lower().translate(_PUNCT)).strip()


def parse_json_output(output: Any) -> tuple[Any, bool]:
    """Read a model's output as JSON, allowing a ```json fence around it.

    Returns the value and whether it parsed.
    """
    if not isinstance(output, str):
        return output, output is not None
    text = output.strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        return json.loads(text), True
    except json.JSONDecodeError:
        # A model sometimes writes a sentence before the object; take the outermost braces.
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1]), True
            except json.JSONDecodeError:
                pass
        return None, False


def numbers_in(text: Any) -> list[float]:
    """Every number written in a text: "1,250.50" gives 1250.5 and "12%" gives 12."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return [float(text)]
    out = []
    for m in _NUMBER.findall("" if text is None else str(text)):
        try:
            out.append(float(m.rstrip("%").replace(",", "")))
        except ValueError:
            continue
    return out


def close_enough(a: float, b: float, tolerance: float = 0.0, absolute: float = 0.0) -> bool:
    return abs(a - b) <= max(absolute, tolerance * max(abs(a), abs(b)), 1e-9)


# --- Classification ---------------------------------------------------------------


def predicted_label(output: Any, labels: list[str] | None) -> str:
    """The label a model chose, normalised.

    With no label list, the whole output is the label. With one, the output is
    matched to the list: an output that is exactly a label wins; otherwise the
    label written first in the output; otherwise no label ("").
    """
    text = normalise_text(output)
    if not labels:
        return text
    choices = [normalise_text(label) for label in labels]
    if text in choices:
        return text
    found = []
    for c in choices:
        m = re.search(rf"(?<![a-z0-9]){re.escape(c)}(?![a-z0-9])", text)
        if m:
            found.append((m.start(), -len(c), c))
    return min(found)[2] if found else ""


@builtin("scorer", "label")
class LabelMatch:
    """For classification: did the model choose the right label?

    Metrics:
      correct: 1 if the label matches the reference label, else 0.

    Options:
      labels: the allowed labels. With them, an answer such as "Category:
              Billing." is read as the label "billing". Without them, the whole
              answer must be the label.

    `trialmark confusion` adds precision and recall for each label, and a table of
    which labels are mistaken for which.
    """

    metrics = ("correct",)

    def __init__(self, labels: list[str] | None = None) -> None:
        self.labels = list(labels) if labels else None

    def score(self, case: Case, output: Any) -> dict[str, Any]:
        got = predicted_label(output, self.labels)
        want = normalise_text(case.reference)
        return {"correct": 1.0 if got == want else 0.0, "note": f"label: {got or '(none)'}"}


# --- Numbers ------------------------------------------------------------------------


@builtin("scorer", "number")
class NumberMatch:
    """For calculations and figures: is the number in the answer close enough?

    Metrics:
      correct: 1 if the number read from the answer is within the tolerance of
               the reference number, else 0.

    Options:
      tolerance: the allowed relative difference, as a fraction (default 0,
                 exact; 0.01 allows 1%).
      absolute: the allowed absolute difference (default 0).
      marker: text that comes just before the answer, such as "Answer:". The
              number after its last occurrence counts, so a model may show its
              working first. Ask the models to end with that line.
      pick: without a marker, or when it is missing, which number counts:
            "first" (default) or "last".
    """

    metrics = ("correct",)

    def __init__(self, tolerance: float = 0.0, absolute: float = 0.0, pick: str = "first",
                 marker: str | None = None) -> None:
        if pick not in ("first", "last"):
            raise ValueError("The number scorer's pick must be 'first' or 'last'.")
        self.tolerance, self.absolute, self.pick = float(tolerance), float(absolute), pick
        self.marker = marker

    def score(self, case: Case, output: Any) -> dict[str, Any]:
        want = numbers_in(case.reference)
        if not want:
            raise ValueError(f"Case '{case.id}': the number scorer needs a number as the reference.")
        text = "" if output is None else str(output)
        if self.marker:
            at = text.lower().rfind(self.marker.lower())
            if at >= 0:
                text = text[at + len(self.marker):]
        got = numbers_in(text)
        if not got:
            return {"correct": 0.0, "note": "no number in the answer"}
        n = got[0] if self.pick == "first" else got[-1]
        ok = close_enough(n, want[0], self.tolerance, self.absolute)
        return {"correct": 1.0 if ok else 0.0, "note": f"read {n:g}, expected {want[0]:g}"}


# --- Structured output ---------------------------------------------------------------


@builtin("scorer", "json-schema")
class JsonSchemaCheck:
    """For structured output: is the answer valid JSON of the right shape?

    Metrics:
      valid_json: 1 if the answer parses as JSON (a ```json fence is allowed).
      matches_schema: 1 if it also matches the JSON Schema.

    Options:
      schema: the JSON Schema, inline.
      schema_file: or a file holding it, relative to the configuration.

    Needs the jsonschema package: pip install "trialmark[jsonschema]".
    Pair it with the fields scorer to check the values as well as the shape.
    """

    metrics = ("valid_json", "matches_schema")

    def __init__(self, schema: dict[str, Any] | None = None, schema_file: str | None = None,
                 base_dir: Path | None = None) -> None:
        if schema_file:
            path = Path(schema_file)
            if not path.is_absolute() and base_dir is not None:
                path = base_dir / path
            schema = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(schema, dict):
            raise ValueError("The json-schema scorer needs a 'schema' or a 'schema_file'.")
        self.schema = schema
        # Made when the run starts (prepare), so a cost estimate works before
        # jsonschema is installed.
        self.validator: Any = None

    def prepare(self) -> None:
        if self.validator is not None:
            return
        try:
            import jsonschema
        except ImportError:
            raise ValueError('The json-schema scorer needs jsonschema: pip install "trialmark[jsonschema]"') from None
        jsonschema.Draft202012Validator.check_schema(self.schema)
        self.validator = jsonschema.Draft202012Validator(self.schema)

    def score(self, case: Case, output: Any) -> dict[str, Any]:
        self.prepare()
        value, parsed = parse_json_output(output)
        if not parsed:
            return {"valid_json": 0.0, "matches_schema": 0.0, "note": "the answer is not valid JSON"}
        errors = sorted(self.validator.iter_errors(value), key=lambda e: list(e.path))
        if errors:
            where = "/".join(str(p) for p in errors[0].path) or "the top level"
            return {"valid_json": 1.0, "matches_schema": 0.0, "note": f"at {where}: {errors[0].message}"[:300]}
        return {"valid_json": 1.0, "matches_schema": 1.0}
