"""Trialmark: model acceptance tests with a pass mark set before the run."""

__version__ = "0.1.0"

from .passmark import Decision, PassMark, decide, parse_pass_mark  # noqa: E402
from .record import ModelEntry, Result, RunRecord, load_record, parse_record  # noqa: E402
from .report import decision, summarise, text_report  # noqa: E402
from .testset import Case, TestSet, hash_cases, load_test_set, parse_test_set  # noqa: E402

__all__ = [
    "Case",
    "Decision",
    "ModelEntry",
    "PassMark",
    "Result",
    "RunRecord",
    "TestSet",
    "decide",
    "decision",
    "hash_cases",
    "load_record",
    "load_test_set",
    "parse_pass_mark",
    "parse_record",
    "parse_test_set",
    "summarise",
    "text_report",
]
