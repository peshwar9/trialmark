"""Trialmark: an open-source framework for evaluating language models and acceptance-testing them for your task."""

__version__ = "0.4.0"

from .passmark import Decision, PassMark, decide, parse_pass_mark  # noqa: E402
from .record import ModelEntry, Result, RunRecord, load_record, parse_record  # noqa: E402
from .report import decision, summarise, text_report  # noqa: E402
from .testset import Case, TestSet, hash_cases, load_test_set, parse_test_set  # noqa: E402
from .plugins import RunOutput, Runner, Scorer, available, load_with, make_runner, make_scorer, render  # noqa: E402
from .run import load_config, run_config, run_trial  # noqa: E402

__all__ = [
    "Case",
    "Decision",
    "ModelEntry",
    "PassMark",
    "Result",
    "RunOutput",
    "RunRecord",
    "Runner",
    "Scorer",
    "TestSet",
    "available",
    "decide",
    "decision",
    "hash_cases",
    "load_config",
    "load_record",
    "load_test_set",
    "load_with",
    "make_runner",
    "make_scorer",
    "parse_pass_mark",
    "parse_record",
    "parse_test_set",
    "render",
    "run_config",
    "run_trial",
    "summarise",
    "text_report",
]
