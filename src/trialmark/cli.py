"""The trialmark command."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .record import load_record
from .report import decision, text_report
from .testset import load_test_set


def _hash(args: argparse.Namespace) -> int:
    ts = load_test_set(args.test_set)
    print(ts.hash)
    return 0


def _validate(args: argparse.Namespace) -> int:
    ts = load_test_set(args.test_set)
    tags = ts.tags()
    print(f"{ts.name} v{ts.version}: {len(ts.cases)} cases, tags: {', '.join(tags) if tags else 'none'}")
    print(ts.hash)
    return 0


def _report(args: argparse.Namespace) -> int:
    print(text_report(load_record(args.record), by_tag=args.by_tag))
    return 0


def _gate(args: argparse.Namespace) -> int:
    record = load_record(args.record)
    if args.test_set:
        expected = load_test_set(args.test_set).hash
        if expected != record.test_set["hash"]:
            print(f"FAIL: the run used test set {record.test_set['hash']}, not {expected}.")
            return 1
    d = decision(record)
    v = d.verdict_for(args.model)
    if v is None:
        print(f"FAIL: {args.model} has no results in this run.")
        return 1
    if v.passed:
        print(f"PASS: {args.model} meets the pass mark.")
        return 0
    print(f"FAIL: {args.model}: {'; '.join(v.reasons)}")
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="trialmark", description="Model acceptance tests with a pass mark set before the run.")
    p.add_argument("--version", action="version", version=f"trialmark {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("hash", help="print a test set's hash")
    s.add_argument("test_set")
    s.set_defaults(fn=_hash)

    s = sub.add_parser("validate", help="check a test set and list its tags")
    s.add_argument("test_set")
    s.set_defaults(fn=_validate)

    s = sub.add_parser("report", help="summarise a run record against its pass mark")
    s.add_argument("record")
    s.add_argument("--by-tag", action="store_true", help="also break results down by tag")
    s.set_defaults(fn=_report)

    s = sub.add_parser("gate", help="exit 0 if a model meets the run's pass mark, 1 if not")
    s.add_argument("record")
    s.add_argument("--model", required=True)
    s.add_argument("--test-set", help="also check that the run used this exact test set")
    s.set_defaults(fn=_gate)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except (OSError, ValueError) as e:
        print(f"trialmark: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
