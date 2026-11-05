"""Test sets: the cases a model is tested on, each with a reference output and tags.

A test set is a JSON file:

    {
      "name": "contracts",
      "version": "2026-11-05",
      "cases": [
        {"id": "q1", "input": "What is the notice period?",
         "reference": "Sixty days' written notice.", "tags": ["factual"]}
      ]
    }

The hash covers the cases only, so a rerun can prove it used exactly the same
cases even if the set was renamed. It uses canonical JSON (RFC 8785), so other
languages can compute the same hash (see canonical.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .canonical import digest, matches


@dataclass(frozen=True)
class Case:
    id: str
    input: Any
    reference: Any
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class TestSet:
    name: str
    version: str
    cases: tuple[Case, ...]
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def hash(self) -> str:
        return hash_cases(self.cases)

    def matches(self, stored_hash: str) -> bool:
        """Whether a hash recorded earlier, by any Trialmark version, is this set's hash."""
        return matches(stored_hash, _case_rows(self.cases))

    def tags(self) -> list[str]:
        return sorted({t for c in self.cases for t in c.tags})


def _case_rows(cases: tuple[Case, ...] | list[Case]) -> list[dict[str, Any]]:
    return sorted(
        ({"id": c.id, "input": c.input, "reference": c.reference, "tags": sorted(c.tags)} for c in cases),
        key=lambda r: r["id"],
    )


def hash_cases(cases: tuple[Case, ...] | list[Case]) -> str:
    return digest(_case_rows(cases))


def parse_test_set(data: dict[str, Any]) -> TestSet:
    for key in ("name", "version", "cases"):
        if key not in data:
            raise ValueError(f"Test set is missing '{key}'.")
    if not isinstance(data["cases"], list) or not data["cases"]:
        raise ValueError("Test set 'cases' must be a non-empty list.")
    cases: list[Case] = []
    seen: set[str] = set()
    for i, raw in enumerate(data["cases"]):
        if not isinstance(raw, dict):
            raise ValueError(f"Case {i} must be an object.")
        for key in ("id", "input", "reference"):
            if key not in raw:
                raise ValueError(f"Case {i} is missing '{key}'.")
        cid = str(raw["id"])
        if cid in seen:
            raise ValueError(f"Case id '{cid}' appears more than once.")
        seen.add(cid)
        tags = raw.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError(f"Case '{cid}' tags must be a list of strings.")
        cases.append(Case(id=cid, input=raw["input"], reference=raw["reference"], tags=tuple(tags)))
    extra = {k: v for k, v in data.items() if k not in ("name", "version", "cases", "description")}
    return TestSet(
        name=str(data["name"]),
        version=str(data["version"]),
        cases=tuple(cases),
        description=str(data.get("description", "")),
        extra=extra,
    )


def load_test_set(path: str | Path) -> TestSet:
    with open(path, encoding="utf-8") as f:
        return parse_test_set(json.load(f))
