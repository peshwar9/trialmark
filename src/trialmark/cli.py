"""The trialmark command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .plugins import available, load_with, render
from .record import load_record
from .report import decision
from .run import load_config, run_config, select_cases

STARTERS = ("anthropic", "openai")


def _hash(args: argparse.Namespace) -> int:
    print(load_with(args.test_set, args.loader).hash)
    return 0


def _validate(args: argparse.Namespace) -> int:
    ts = load_with(args.test_set, args.loader)
    tags = ts.tags()
    print(f"{ts.name} v{ts.version}: {len(ts.cases)} cases, tags: {', '.join(tags) if tags else 'none'}")
    print(ts.hash)
    return 0


def _money(v: float | None) -> str:
    if v is None:
        return "unknown"
    return f"${v:.2f}" if v >= 0.01 or v == 0 else "under $0.01"


def _run(args: argparse.Namespace) -> int:
    from .estimate import estimate_run, needs_confirmation

    config = load_config(args.config)
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    config = select_cases(config, only, args.limit)
    out = args.output or config.output
    if out is None:
        print("trialmark: give an output path with --output or 'output' in the configuration.", file=sys.stderr)
        return 2
    total = len(config.models) * len(config.test_set.cases) * config.repeats
    print(
        f"Plan: {len(config.models)} models on {len(config.test_set.cases)} cases, {config.repeats} repeats: "
        f"{total} answers"
        + (f", each graded by {', '.join(config.judge_names)}." if getattr(config, "judge_names", None) else ".")
    )
    est = estimate_run(config)
    print("Estimated cost (rough; the record holds what is actually spent):")
    for model, cost in est.answers.items():
        reason = "" if cost is not None else "  (no pricing in its settings, or your own function)"
        print(f"  {model:<28} {_money(cost)}{reason}")
    for label, cost in est.scoring.items():
        reason = "" if cost is not None else "  (no pricing in its options)"
        print(f"  {label:<28} {_money(cost)}{reason}")
    print(f"  {'total':<28} {_money(est.known_total)}" + (" plus the unknown items" if est.unknown else ""))
    if needs_confirmation(config) and not args.yes:
        print("\nNothing run. Add --yes to call the models and spend this. Try --limit 3 first.")
        return 0
    print("The pass mark is fixed now.")
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


def _init(args: argparse.Namespace) -> int:
    from .starters import PROVIDERS, resolve, write

    task, provider = args.task, args.provider
    if task in PROVIDERS:  # "trialmark init anthropic", as in 0.4: the question-answering starter
        task, provider = "qa", task
    t = resolve(task)
    target = Path(args.dir or f"trialmark-{t.name}-{provider}")
    if target.exists() and any(target.iterdir()):
        print(f"trialmark: {target} already exists and is not empty; choose another --dir.", file=sys.stderr)
        return 2
    names = write(t.name, provider, target)
    p = PROVIDERS[provider]
    print(f"Wrote the {t.title.lower()} starter for {provider} in {target}/: {', '.join(names)}.")
    print("Next:")
    print(f'  pip install "trialmark[{",".join([p.extra, *t.extras])}]"')
    print(f"  export {p.key}=...")
    print(f"  cd {target}")
    print("  trialmark run config.json                  # the plan and a cost estimate; spends nothing")
    print("  trialmark run config.json --limit 3 --yes  # three cases first")
    return 0


def _judge_sample(args: argparse.Namespace) -> int:
    from .judgecheck import write_sample

    n = write_sample(load_record(args.record), load_with(args.test_set), args.out, size=args.size, seed=args.seed)
    print(f"Wrote {n} answers to {args.out}. Fill in your_verdict with correct, partial or incorrect,")
    print("without looking at the judge's grades, then run:")
    print(f"  trialmark judge-check score {args.record} {args.out}")
    return 0


def _judge_score(args: argparse.Namespace) -> int:
    from .judgecheck import agreement_report, score_grades

    record = load_record(args.record)
    judge = (record.judge or {}).get("model", "the scorer")
    print(agreement_report(score_grades(record, args.grades), judge))
    return 0


def _confusion(args: argparse.Namespace) -> int:
    from .confusion import confusion, confusion_report

    labels = [x.strip() for x in args.labels.split(",")] if args.labels else None
    print(confusion_report(confusion(load_record(args.record), load_with(args.test_set), labels)))
    return 0


def _plugins(args: argparse.Namespace) -> int:
    for kind, rows in available().items():
        print(f"{kind}s:")
        for name, source in rows:
            print(f"  {name:<16} {source}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="trialmark", description="Evaluate language models and acceptance-test them for your task, with a pass mark fixed before the results.")
    p.add_argument("--version", action="version", version=f"trialmark {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("run", help="estimate, then run a trial from a configuration file and save its record")
    s.add_argument("config")
    s.add_argument("--yes", action="store_true", help="call the models and spend the estimated cost")
    s.add_argument("--limit", type=int, help="run only the first N cases")
    s.add_argument("--only", help="run only these case ids, separated by commas")
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

    s = sub.add_parser("init", help="write a ready-to-run starter for one kind of task")
    s.add_argument("task", help="qa, extraction, classification, summarisation or calculation")
    s.add_argument("--provider", default="anthropic", choices=STARTERS)
    s.add_argument("--dir", help="where to write it (default: trialmark-<task>-<provider>)")
    s.set_defaults(fn=_init)

    s = sub.add_parser("confusion", help="per-label precision and recall for a classification run")
    s.add_argument("record")
    s.add_argument("--test-set", required=True, help="the test set the run used")
    s.add_argument("--labels", help="the allowed labels, separated by commas (default: the labels in the test set)")
    s.set_defaults(fn=_confusion)

    jc = sub.add_parser("judge-check", help="check the judge against your own grades")
    jsub = jc.add_subparsers(dest="step", required=True)
    s = jsub.add_parser("sample", help="write a blind sample of answers for you to grade")
    s.add_argument("record")
    s.add_argument("--test-set", required=True, help="the test set the run used")
    s.add_argument("--out", default="grades.csv")
    s.add_argument("--size", type=int, default=20)
    s.add_argument("--seed", type=int, default=1)
    s.set_defaults(fn=_judge_sample)
    s = jsub.add_parser("score", help="compare your grades with the judge's")
    s.add_argument("record")
    s.add_argument("grades")
    s.set_defaults(fn=_judge_score)

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
