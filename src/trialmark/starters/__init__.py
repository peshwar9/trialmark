"""Ready-to-run starters, one for each kind of task, for Anthropic or OpenAI models.

`trialmark init <task> --provider <provider>` writes one. The same starters are in
the repository's examples/starters/, built from this module by
examples/make_starters.py, and a test keeps the two identical.

A starter is the task's content files (files/<task>/), a configuration built
from the task and the provider below, and a README.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from string import Template
from typing import Any, Callable


@dataclass(frozen=True)
class Provider:
    name: str
    extra: str
    key: str
    runner: str
    model_a: tuple[str, dict[str, float]]  # the cheaper model
    model_b: tuple[str, dict[str, float]]
    judge: tuple[str, dict[str, float]]  # a stronger model that is not under test
    prices_as_of: str


PROVIDERS: dict[str, Provider] = {
    "anthropic": Provider(
        name="anthropic",
        extra="anthropic",
        key="ANTHROPIC_API_KEY",
        runner="anthropic",
        model_a=("claude-haiku-5-5", {"input": 0.1, "output": 0.5}),
        model_b=("claude-sonnet-5-5", {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5}),
        judge=("claude-opus-5-5", {"input": 4.0, "output": 20.0, "cache_read": 0.2, "cache_write": 5.0}),
        prices_as_of="5 November 2026, Anthropic list prices in USD per million tokens; check current prices",
    ),
    "openai": Provider(
        name="openai",
        extra="openai",
        key="OPENAI_API_KEY",
        runner="openai",
        model_a=("gpt-4o-mini", {"input": 0.15, "output": 0.6, "cache_read": 0.075}),
        model_b=("gpt-5.6-sol", {"input": 4.0, "output": 20.0, "cache_read": 0.4}),
        judge=("gpt-6-astra", {"input": 10.0, "output": 50.0, "cache_read": 1.0}),
        prices_as_of=(
            "9 September 2026, OpenAI list prices in USD per million tokens, gpt-5.6-sol at promotional "
            "pricing until 21 November 2026; check current prices"
        ),
    ),
}


@dataclass(frozen=True)
class Task:
    name: str
    title: str
    files: tuple[str, ...]  # content files, copied as they are
    test_set: str
    system: str
    documents: tuple[str, ...]
    pass_mark: dict[str, Any]
    scorers: Callable[[Provider], list[Any]]
    extras: tuple[str, ...] = ()  # pip extras beyond the provider's
    gate_model: str = "a"  # which model the README's gate example names
    readme: str = ""
    report_flags: str = "--by-tag"
    after: str = ""  # an extra command after the run, if any
    options: dict[str, Any] = field(default_factory=dict)


def _judge(p: Provider, kind: str = "judge", **extra: Any) -> dict[str, Any]:
    opts: dict[str, Any] = {"model": p.judge[0], "pricing": p.judge[1], **extra}
    if p.name != "anthropic":
        opts["provider"] = p.name
    return {"name": kind, "options": opts}


TASKS: dict[str, Task] = {
    "qa": Task(
        name="qa",
        title="Answering questions from a document",
        files=("contract.md", "questions.csv"),
        test_set="questions.csv",
        system="Answer from the document only. If it does not contain the answer, say so.",
        documents=("contract.md",),
        pass_mark={"metric": "correct", "tolerance_points": 5, "floors": {"grounded": 0.9}, "choose": "cheapest"},
        scorers=lambda p: [_judge(p, documents=["contract.md"])],
        readme="""Two models answer ten questions about a short fictional consulting agreement
(`contract.md`). A third model, the judge, grades every answer against the reference answers in
`questions.csv`: correct, partly correct or incorrect, whether it stuck to the document
(grounded), and whether it declined when it should. The pass mark chooses the cheapest model
within 5 points of the best on correct answers, with at least 90% of its answers grounded.

The questions are tagged by kind (`factual`, `multi-part`, `calculation`, `not-in-documents`),
so `--by-tag` shows where a cheaper model keeps up and where it falls behind.""",
    ),
    "extraction": Task(
        name="extraction",
        title="Extracting fields from documents",
        files=("invoices.json", "schema.json"),
        test_set="invoices.json",
        system=(
            "Read the invoice and reply with JSON only, with exactly these keys: invoice_number, "
            "invoice_date (YYYY-MM-DD), supplier (the company that issued the invoice), currency "
            "(the three-letter ISO code), and total (the amount due, including tax, as a plain number)."
        ),
        documents=(),
        pass_mark={"metric": "fields_correct", "tolerance_points": 2, "floors": {"matches_schema": 1.0}, "choose": "cheapest"},
        scorers=lambda p: [
            {"name": "fields", "options": {"tolerance": 0.005}},
            {"name": "json-schema", "options": {"schema_file": "schema.json"}},
        ],
        extras=("jsonschema",),
        readme="""Two models read six fictional invoices (`invoices.json`), some tidy and some messy,
and return five fields as JSON. No judge is needed: the `fields` scorer compares each field with
the value a person read from the invoice (numbers within 0.5%), and the `json-schema` scorer
checks the reply is valid JSON of the right shape (`schema.json`). The pass mark chooses the
cheapest model within 2 points of the best on fields correct, with every reply matching the
schema.

The invoices are tagged `tidy` or `messy`, so `--by-tag` shows whether a cheaper model copes
with the messy ones.""",
    ),
    "classification": Task(
        name="classification",
        title="Classifying messages into categories",
        files=("tickets.csv",),
        test_set="tickets.csv",
        system=(
            "Classify the customer message into exactly one of these categories: billing, technical, "
            "account, feedback. Reply with the category only."
        ),
        documents=(),
        pass_mark={"metric": "correct", "tolerance_points": 5, "choose": "cheapest"},
        scorers=lambda p: [{"name": "label", "options": {"labels": ["billing", "technical", "account", "feedback"]}}],
        readme="""Two models sort twelve fictional customer messages (`tickets.csv`) into four
categories: billing, technical, account and feedback. No judge is needed: the `label` scorer
reads the category from each answer, even one like "Category: Billing.", and compares it with
the right one. The pass mark chooses the cheapest model within 5 points of the best.

The messages are tagged `clear` or `mixed` (a mixed one touches two categories), so `--by-tag`
shows where models disagree. `trialmark confusion` then shows, for each category, how often the
model was right when it chose it (precision), how many of its cases it found (recall), and which
categories it mistook for which.""",
        after="trialmark confusion record.json --test-set tickets.csv",
    ),
    "summarisation": Task(
        name="summarisation",
        title="Summarising and other writing",
        files=("notes.json",),
        test_set="notes.json",
        system="You write short, accurate summaries for a busy chief executive.",
        documents=(),
        pass_mark={"metric": "checklist_met", "tolerance_points": 5, "choose": "cheapest"},
        scorers=lambda p: [
            _judge(
                p,
                kind="checklist",
                checklist=[
                    "Is under 120 words",
                    "States nothing that is not in the notes or email",
                    "Is written in plain English",
                ],
            )
        ],
        readme="""Two models summarise four fictional sets of meeting notes and emails
(`notes.json`). Writing has no single right answer, so each case carries a checklist of what a
good summary must contain, such as "Mentions the review on 8 December", and three items in
`config.json` apply to every case: under 120 words, nothing that is not in the source, and plain
English. A third
model, the judge, marks each item met or not met. The score is the share of items met; the pass
mark chooses the cheapest model within 5 points of the best.

The same approach suits any writing or analysis: emails, reports, explanations, reviews. Write
down what a good answer must do, item by item.""",
    ),
    "calculation": Task(
        name="calculation",
        title="Calculating figures from a document",
        files=("pricelist.md", "questions.csv"),
        test_set="questions.csv",
        system=(
            "Answer from the price list. Show your working if you need to, then end with a final line "
            "of the form 'Answer: <number>', in pounds, with no currency sign."
        ),
        documents=("pricelist.md",),
        pass_mark={"metric": "correct", "tolerance_points": 0, "choose": "cheapest"},
        scorers=lambda p: [{"name": "number", "options": {"tolerance": 0.005, "marker": "Answer:"}}],
        readme="""Two models answer six pricing questions about a fictional price list
(`pricelist.md`), some needing one step and some several (a discount, delivery, VAT). No judge
is needed: each model may show its working but must end with a line "Answer: <number>", and the
`number` scorer reads the number after "Answer:" and accepts it within 0.5% of the right one. The pass mark chooses the cheapest model that is as accurate as the best.

The questions are tagged `one-step` or `two-step`, so `--by-tag` shows whether a cheaper model
slips when a sum has several steps.""",
    ),
}

ALIASES = {"summarization": "summarisation", "rag": "qa", "questions": "qa", "extract": "extraction"}


def resolve(task: str) -> Task:
    t = TASKS.get(ALIASES.get(task, task))
    if t is None:
        raise ValueError(f"No starter for '{task}'. Available: {', '.join(TASKS)}.")
    return t


def config_for(task: Task, p: Provider) -> dict[str, Any]:
    def model(m: tuple[str, dict[str, float]]) -> dict[str, Any]:
        settings: dict[str, Any] = {}
        if task.documents:
            settings["documents"] = list(task.documents)
        settings["system"] = task.system
        settings["pricing"] = m[1]
        return {"id": m[0], "runner": p.runner, "settings": settings}

    return {
        "test_set": task.test_set,
        "pass_mark": task.pass_mark,
        "repeats": 3,
        "concurrency": 4,
        "models": [model(p.model_a), model(p.model_b)],
        "scorers": task.scorers(p),
        "environment": {"starter": f"{task.name}-{p.name}", "prices_as_of": p.prices_as_of},
        "output": "record.json",
    }


README = Template("""# Trialmark starter: $title ($provider)

$body

Models under test: `$model_a` and `$model_b`.$judge_line

## Run it

```bash
pip install "trialmark[$extras]"
export $key=...

trialmark run config.json                        # the plan and a cost estimate; spends nothing
trialmark run config.json --limit 3 --yes        # three cases first, to see it working
trialmark run config.json $flags --yes         # the full test
trialmark gate record.json --model $model_a$after
```

## Make it yours

- **Your cases:** replace `$test_set` with your own, in the same format. Tags give the report its
  breakdown by kind of case.
- **Your models:** change the model ids in `config.json`, and their prices under `pricing`, in US
  dollars per million tokens. The prices here were current when the starter was written; check
  yours.
- **Your instructions:** the `system` setting is what each model is told. Keep it the same for
  every model, so only the model changes.
- **Your pass mark:** set it before you look at the results. That is the point of an acceptance
  test.$judge_tip

See [docs/tasks.md](https://github.com/peshwar9/trialmark/blob/main/docs/tasks.md) for every kind
of task Trialmark can test, and how.
""")


def readme_for(task: Task, p: Provider) -> str:
    uses_judge = any(s["name"] in ("judge", "checklist") for s in task.scorers(p))
    return README.substitute(
        title=task.title,
        provider="Anthropic" if p.name == "anthropic" else "OpenAI",
        body=task.readme,
        model_a=p.model_a[0],
        model_b=p.model_b[0],
        judge_line=f" Judge: `{p.judge[0]}`." if uses_judge else "",
        extras=",".join([p.extra, *task.extras]),
        key=p.key,
        flags=task.report_flags,
        after=f"\n{task.after}" if task.after else "",
        test_set=task.test_set,
        judge_tip=(
            "\n- **Check the judge:** `trialmark judge-check sample record.json --test-set "
            f"{task.test_set}` writes a sample for you to grade; `trialmark judge-check score "
            "record.json grades.csv` says how often the judge agreed with you."
            if uses_judge
            else ""
        ),
    )


def build(task_name: str, provider: str) -> dict[str, str]:
    """Every file of a starter, by name."""
    task = resolve(task_name)
    if provider not in PROVIDERS:
        raise ValueError(f"No provider '{provider}'. Available: {', '.join(PROVIDERS)}.")
    p = PROVIDERS[provider]
    src = resources.files("trialmark").joinpath(f"starters/files/{task.name}")
    out = {name: src.joinpath(name).read_text(encoding="utf-8") for name in task.files}
    out["config.json"] = json.dumps(config_for(task, p), indent=2) + "\n"
    out["README.md"] = readme_for(task, p)
    return out


def write(task_name: str, provider: str, target: Path) -> list[str]:
    files = build(task_name, provider)
    target.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (target / name).write_text(text, encoding="utf-8")
    return sorted(files)
