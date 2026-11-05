"""Run records: everything needed to repeat a run and check its result.

A record is started before any model runs, with the test set and the pass mark
fixed, and results are added as they arrive. The pass mark's hash and the time
it was set are kept, so a reader can see it was not changed after the results.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .passmark import PassMark, parse_pass_mark
from .testset import TestSet


@dataclass
class ModelEntry:
    id: str
    provider: str = ""
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class Result:
    model: str
    repeat: int
    case_id: str
    metrics: dict[str, float]
    tags: list[str] = field(default_factory=list)
    output: Any = None
    cost_usd: float = 0.0
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    note: str = ""


@dataclass
class RunRecord:
    test_set: dict[str, str]
    pass_mark: dict[str, Any]
    pass_mark_hash: str
    pass_mark_set_at: str
    models: list[ModelEntry]
    repeats: int
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trialmark_version: str = __version__
    judge: dict[str, Any] | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    results: list[Result] = field(default_factory=list)

    @classmethod
    def start(
        cls,
        test_set: TestSet,
        pass_mark: PassMark,
        models: list[ModelEntry],
        repeats: int = 3,
        judge: dict[str, Any] | None = None,
        environment: dict[str, Any] | None = None,
    ) -> "RunRecord":
        if repeats < 1:
            raise ValueError("A run needs at least one repeat.")
        if not models:
            raise ValueError("A run needs at least one model.")
        return cls(
            test_set={"name": test_set.name, "version": test_set.version, "hash": test_set.hash},
            pass_mark=pass_mark.to_dict(),
            pass_mark_hash=pass_mark.hash,
            pass_mark_set_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            models=models,
            repeats=repeats,
            judge=judge,
            environment=environment or {},
        )

    def add(self, result: Result) -> None:
        if result.model not in {m.id for m in self.models}:
            raise ValueError(f"Model '{result.model}' is not in this run.")
        if not 0 <= result.repeat < self.repeats:
            raise ValueError(f"Repeat {result.repeat} is outside 0..{self.repeats - 1}.")
        self.results.append(result)

    def parsed_pass_mark(self) -> PassMark:
        pm = parse_pass_mark(self.pass_mark)
        if pm.hash != self.pass_mark_hash:
            raise ValueError("The pass mark does not match the hash recorded when it was set.")
        return pm

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            f.write("\n")


def parse_record(data: dict[str, Any]) -> RunRecord:
    try:
        models = [ModelEntry(**m) for m in data["models"]]
        results = [Result(**r) for r in data.get("results", [])]
        return RunRecord(
            test_set=dict(data["test_set"]),
            pass_mark=dict(data["pass_mark"]),
            pass_mark_hash=str(data["pass_mark_hash"]),
            pass_mark_set_at=str(data["pass_mark_set_at"]),
            models=models,
            repeats=int(data["repeats"]),
            run_id=str(data.get("run_id", "")),
            trialmark_version=str(data.get("trialmark_version", "")),
            judge=data.get("judge"),
            environment=dict(data.get("environment", {})),
            results=results,
        )
    except KeyError as e:
        raise ValueError(f"Run record is missing {e}.") from None
    except TypeError as e:
        raise ValueError(f"Run record has an unexpected field: {e}.") from None


def load_record(path: str | Path) -> RunRecord:
    with open(path, encoding="utf-8") as f:
        return parse_record(json.load(f))
