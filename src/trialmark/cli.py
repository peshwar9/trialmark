"""The trialmark command."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .plugins import available, load_with, render
from .record import load_record
from .report import decision
from .run import load_config, run_config


def _hash(args: argparse.Namespace) -> int:
    print(load_with(args.test_set, args.loader).hash)
    return 0


def _validate(args: argparse.Namespace) -> int:
    ts = load_with(args.test_set, args.loader)
    tags = ts.tags()
    print(f"{ts.name} v{ts.version}: {len(ts.cases)} cases, tags: {', '.join(tags) if tags else 'none'}")
    print(ts.hash)
    return 0


def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    out = args.output or config.output
    if out is None:
        print("trialmark: give an output path with --output or 'output' in the configuration.", file=sys.stderr)
        return 2
    total = len(config.models) * len(config.test_set.cases) * config.repeats
    print(
        f"Running {len(config.models)} models on {len(config.test_set.cases)} cases, "
        f"{config.repeats} repeats: {total} calls. The pass mark is fixed now."
    )
    done = 0

    def progress(result) -> None:
        nonlocal done
        done += 1
        if result.error:
            print(f"  ! {result.model} {result.case_id}: {result.error}")
        if done % 50 == 0 or done == total:
            print(f"  {done}/{total}")

    record = run_config(config, progress=progress)
    record.save(out)
    print(f"Saved {out}\n")
    print(render(record, "text", by_tag=args.by_tag))
    return 0


def _report(args: argparse.Namespace) -> int:
    print(render(load_record(args.record), args.format, by_tag=args.by_tag))
    return 0


def _gate(args: argparse.Namespace) -> int:
    record = load_record(args.record)
    if args.test_set:
        expected = load_with(args.test_set)
        if not expected.matches(record.test_set["hash"]):
            print(f"FAIL: the run used test set {record.test_set['hash']}, not {expected.hash}.")
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


def _schema(args: argparse.Namespace) -> int:
    from importlib import resources

    print(resources.files("trialmark").joinpath(f"schemas/{args.name}.schema.json").read_text(encoding="utf-8"))
    return 0


def _plugins(args: argparse.Namespace) -> int:
    for kind, rows in available().items():
        print(f"{kind}s:")
        for name, source in rows:
            print(f"  {name:<16} {source}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="trialmark", description="Model acceptance tests with a pass mark set before the run.")
    p.add_argument("--version", action="version", version=f"trialmark {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("run", help="run a trial from a configuration file and save its record")
    s.add_argument("config")
    s.add_argument("--output", help="where to save the run record (overrides the configuration)")
    s.add_argument("--by-tag", action="store_true", help="also break results down by tag")
    s.set_defaults(fn=_run)

    s = sub.add_parser("hash", help="print a test set's hash")
    s.add_argument("test_set")
    s.add_argument("--loader", help="loader to use (default: from the file extension)")
    s.set_defaults(fn=_hash)

    s = sub.add_parser("validate", help="check a test set and list its tags")
    s.add_argument("test_set")
    s.add_argument("--loader", help="loader to use (default: from the file extension)")
    s.set_defaults(fn=_validate)

    s = sub.add_parser("report", help="summarise a run record against its pass mark")
    s.add_argument("record")
    s.add_argument("--by-tag", action="store_true", help="also break results down by tag")
    s.add_argument("--format", default="text", help="report writer: text, markdown, json or a plugin's name")
    s.set_defaults(fn=_report)

    s = sub.add_parser("gate", help="exit 0 if a model meets the run's pass mark, 1 if not")
    s.add_argument("record")
    s.add_argument("--model", required=True)
    s.add_argument("--test-set", help="also check that the run used this exact test set")
    s.set_defaults(fn=_gate)

    s = sub.add_parser("schema", help="print the JSON Schema of a Trialmark file format")
    s.add_argument("name", choices=["testset", "passmark", "run-record"])
    s.set_defaults(fn=_schema)

    s = sub.add_parser("plugins", help="list the runners, scorers, loaders and reports Trialmark can find")
    s.set_defaults(fn=_plugins)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except (OSError, ValueError) as e:
        print(f"trialmark: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
