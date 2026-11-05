# Trialmark

**Trialmark is an open-source framework for evaluating language models and acceptance-testing
them for your task.** Test models on your own cases, fix the pass mark before you see the
results, and get a reproducible record of accuracy, cost and speed, with a gate your pipeline can
enforce.

Evaluation measures how models perform. Acceptance testing decides whether a model is good
enough for the task, against a rule written down before the results are seen, and records that
decision so anyone can check it. Trialmark does both.

## What you can do with Trialmark

You are building something with an AI model and have to choose one. A bigger model is usually
more accurate but costs more and is slower; a smaller one is cheaper, but is it good enough for
your task? Trialmark answers that with evidence from your own questions, not a leaderboard.

**1. Try it in two minutes with a ready-made example.** `trialmark init qa` gives you a small
working project: a short made-up contract, ten questions about it with the right answers, and a
settings file. Add your API key and run it. Two models answer the questions and a third model
grades their answers. There are starters for four other kinds of task too: extracting fields,
classifying, summarising and calculating.

**2. Test models on your own questions.** Put your questions and their right answers in a
spreadsheet saved as CSV, label each question with its kind if you like ("simple fact", "needs
several parts"), and name the models you want to compare. Trialmark asks every model every
question, several times over, because models do not answer the same way every time.

**3. Decide what "good enough" means before you see the results.** You write the rule down
first, for example "pick the cheapest model that scores within 3 points of the best one".
Trialmark saves it before any model runs, so nobody can quietly move the goalposts after seeing
the numbers. Then it applies your rule and names the winner.

**4. See accuracy, cost and speed side by side.** For each model: how often it was right, partly
right or wrong; whether its answers stuck to your documents or added things that are not there;
whether it correctly said "I don't know" when the answer was not available; what it cost; and how
long it took. The results are also broken down by kind of question. That is often the most
useful part: a cheap model may be perfect on simple facts and slip on harder, multi-part
questions.

**5. Know the cost before you spend anything.** A run first shows the plan and an estimated bill,
and spends nothing. Models are called only when you add `--yes`, and `--limit 3` tries the first
three questions before the full run.

**6. Let a model grade the answers, then check the grader.** Free-text answers cannot be marked
by matching text exactly, so Trialmark uses an AI model as the judge, comparing each answer with
your right answer. To know whether to trust it, `trialmark judge-check` gives you a sample of
answers to mark yourself, without showing the judge's marks, and tells you how often you agreed.

**7. Keep a record anyone can check, and use it to block bad changes.** Every run saves one file
holding exactly what was tested: the questions, with a fingerprint that proves they did not
change, the models, your rule, every answer and every cost. `trialmark gate` turns that into a
pass or a fail, so your build pipeline can refuse a model switch that does not meet your rule.

**8. Test your own system, not just a bare model.** If your app does more than call a model, for
example searching your own documents first, write a small Python function that calls your app,
and Trialmark tests the whole thing. You can also add your own pieces, such as a new model
provider, a new way of grading or a new file format, without forking Trialmark.

**What it does not do yet.** There is no web dashboard or HTML report; reports are text,
Markdown or JSON. And it cannot yet prove who ran a test: the fingerprints catch accidental
changes, not deliberate tampering. Signed records are planned.

Trialmark runs on your own machines. Your test sets, reference answers and records stay with you.

## Documentation

| Guide | What it covers |
|---|---|
| [What makes Trialmark different](docs/design.md) | The design decisions: the decision registered before the results, one method for every task with plugins for the marking, practice from experimental work, and a record others can check |
| [What you can test](docs/tasks.md) | Each kind of task (questions over documents, extraction, classification, writing, calculation, structured output, your own system): how it is marked, what your test cases look like, and its starter |
| [Which models](docs/models.md) | The models Trialmark can call today, what a new kind of model would need, and how to add one with plugins, with a worked example for speech to text |
| [Deployment](docs/deployment.md) | Where Trialmark runs (a laptop, a build pipeline, a schedule, your own servers), what it reads and writes, and when testing a model needs servers or storage |
| [Starters](examples/starters) | Ten ready-to-run examples, one per kind of task, for Anthropic or OpenAI models |
| [Architecture](ARCHITECTURE.md) | How a run works, what is fixed in the core, and how to write a plugin |
| [Launch post](docs/blog/2026-11-05-trialmark-0-5.md) | Why Trialmark exists and how it differs from other evaluation tools |
| [Changelog](CHANGELOG.md) and [Releasing](RELEASING.md) | What changed in each version, and how a release is published |

## Where it comes from

Trialmark was spun out of the model benchmark in [Forge](https://www.forgeprivate.com), a
governed layer through which organisations delegate work to AI. That benchmark compares models
on a fixed set of business-document questions, through Forge's own answer path, with three
repeats and accuracy, cost and speed side by side. Trialmark makes the same kind of test
available to any developer or team, with or without Forge.

## Status

Trialmark is at an early stage.

| Built | Planned |
|---|---|
| The test set format, with hashing and tags, read from JSON or CSV | Signed run records |
| The pass mark and the decision rule | An HTML report with a chart of correctness against cost |
| The run record, with the pass mark's hash, the judge and the plugins used | Logging runs to MLflow |
| `trialmark run`, which estimates the cost, then runs every model on every case for every repeat once you add `--yes` | |
| Runners that call Anthropic and OpenAI models directly, and a runner for a function of your own | |
| A reference-answer judge, which grades an answer as correct, partly correct or incorrect, and whether it is grounded and whether it declined | |
| Scorers for each kind of task: exact match, fields, labels, numbers, JSON Schema, and a checklist judge for writing | |
| `trialmark confusion`: per-category precision and recall for classification | |
| Plugins for runners, scorers, loaders and reports (see [ARCHITECTURE.md](ARCHITECTURE.md)) | |
| Reports as text, Markdown or JSON, with ranges and the breakdown by tag | |
| `trialmark gate` for pipelines, and JSON Schema files for every format | |
| `trialmark init`, with ready-to-run starters for five kinds of task, for Anthropic or OpenAI models | |
| `trialmark judge-check`, which measures how often the judge agrees with your own grades | |

## Install

```bash
pip install trialmark
```

Python 3.10 or later. The core has no dependencies. To call models directly, add the provider's
SDK as an extra:

```bash
pip install "trialmark[anthropic]"
pip install "trialmark[openai]"
```

## Quick start with your own key

Each starter tests two models on a small fictional task and runs as it is. Bring an Anthropic
or OpenAI key:

```bash
pip install "trialmark[anthropic]"
export ANTHROPIC_API_KEY=...

trialmark init qa                             # writes trialmark-qa-anthropic/
cd trialmark-qa-anthropic
trialmark run config.json                     # the plan and a cost estimate; spends nothing
trialmark run config.json --limit 3 --yes     # three questions first
trialmark run config.json --by-tag --yes      # the full test, about $1
trialmark gate record.json --model claude-haiku-5-5
```

For OpenAI, use `"trialmark[openai]"`, `OPENAI_API_KEY` and `trialmark init qa --provider openai`.
Every starter is also in [`examples/starters/`](examples/starters), each with a README on making
it yours: your cases, your models, your instructions and your pass mark.

## Kinds of task

Trialmark tests any task where you can give a model an input and say what a good output is.
[docs/tasks.md](docs/tasks.md) explains each kind: how it is marked, what your test cases look
like, and how to set it up.

| Kind of task | Marked by | Starter |
|---|---|---|
| Answering questions from documents (RAG) | a judge model, against your right answers | `trialmark init qa` |
| Extracting fields from documents and forms | field by field, and the JSON's shape | `trialmark init extraction` |
| Classifying into categories | the label, then per-category precision and recall | `trialmark init classification` |
| Writing, summarising and analysis | a judge model, against your checklist | `trialmark init summarisation` |
| Calculating figures | the number, within a tolerance | `trialmark init calculation` |
| Structured output (JSON of a given shape) | a JSON Schema | part of `extraction` |
| Your own system, such as your own retrieval pipeline | any of the above | see [docs/tasks.md](docs/tasks.md) |

Conversations and agents (several turns, tool calls) are not supported yet.

## Which models

Any model you can call from Python. Claude and OpenAI models have built-in runners; every other
model, such as Gemini, Mistral, open-weight models run locally with Ollama or vLLM, your
fine-tuned models, classic text classifiers, or your own system built on models, takes a short
Python function. What matters is not how a model is built but what it returns: today Trialmark
marks text, JSON, labels and numbers. Other outputs need their own scorers first: boxes and masks
from detection models, transcripts from speech-to-text, rankings from embedding models, and
generated images.
[docs/models.md](docs/models.md) says what is supported and what each new kind of model would
need.

**Nothing is spent without `--yes`.** `trialmark run` first prints the plan and an estimate
for each model and for the judge. The estimate errs on the high side; the record holds what
was actually spent, the judge's share included. `--limit N` runs the first N questions and
`--only q3,q7` runs the ones named, so you can try a few before the full run.

## Try it without a key

The `examples` folder also holds a five-question test set and a configuration that compares
stand-in models, so a run needs no API key. Run it from the repository's root folder:

```bash
trialmark validate examples/testset.json
trialmark run examples/config.json --by-tag --yes
trialmark report examples/config-run-record.json --format markdown
trialmark gate examples/config-run-record.json --model perfect-model
trialmark plugins
```

One of its models is a function of your own (`examples/my_model.py`), whose cost Trialmark
cannot know, which is why that run also asks for `--yes`. `examples/run-record.json` is an
illustrative record of three made-up models whose scores are invented to show the format.
They are not measurements of any real model.

## Compare models on your own questions

This configuration compares two Claude models, gives each the whole source document, and has a
third model grade every answer against your reference answers:

```json
{
  "test_set": "my-questions.csv",
  "pass_mark": {
    "metric": "correct", "tolerance_points": 3, "floors": { "grounded": 0.95 }, "choose": "cheapest"
  },
  "repeats": 3,
  "concurrency": 4,
  "models": [
    { "id": "claude-sonnet-5-5", "runner": "anthropic",
      "settings": { "documents": ["contract.md"], "pricing": { "input": 2.0, "output": 10.0, "cache_read": 0.2 } } },
    { "id": "claude-haiku-5-5", "runner": "anthropic",
      "settings": { "documents": ["contract.md"], "pricing": { "input": 0.1, "output": 0.5 } } }
  ],
  "scorers": [
    { "name": "judge", "options": { "model": "claude-opus-5-5", "documents": ["contract.md"] } }
  ],
  "output": "run-record.json"
}
```

```bash
export ANTHROPIC_API_KEY=...
trialmark run config.json                 # the estimate
trialmark run config.json --by-tag --yes  # the run
```

Every run calls the models for real and costs money: here, two models, three repeats and every
question, plus one judge call per answer.

A few things to know:

- **Prices** are yours to give, in US dollars per million tokens, because they change. Check
  your provider's current prices. A model without prices reports a cost of zero, with a note on
  each result.
- **The judge** works best when it is not one of the models under test. Give it `pricing` too,
  so its spend is estimated and recorded. Its model, the documents it read, a hash of its rules
  and what it spent are kept in the record. `rules_file` replaces the built-in rules with your
  own.
- **Check the judge against your own grades** before relying on it:
  `trialmark judge-check sample record.json --test-set questions.csv` writes 20 answers to
  `grades.csv` without the judge's verdicts; fill in `your_verdict` with correct, partial or
  incorrect, then `trialmark judge-check score record.json grades.csv` shows how often the judge
  agreed with you and lists each disagreement.
- **OpenAI models** use `"runner": "openai"`, and the judge takes `"provider": "openai"`.
- **Your own system**, such as your own retrieval pipeline, plugs in through the `python` runner:
  write a function that takes the model's name, the question and the settings, and returns the
  answer, or a `trialmark.RunOutput` with its cost and tokens. Name it in the model's settings as
  `"callable": "my_system.py:answer"`.
- **Exact match** (`"scorers": ["exact-match"]`) is enough for short answers such as a number or a
  date, and costs nothing.

## Use it from Python

```python
from trialmark import ModelEntry, PassMark, load_with, make_scorer, render, run_trial

record = run_trial(
    load_with("my-testset.csv"),
    PassMark(metric="correct", tolerance_points=3, floors={"grounded": 0.95}, choose="cheapest"),
    [ModelEntry(id="model-a", runner="mine"), ModelEntry(id="model-b", runner="mine")],
    runners={"mine": MyRunner()},          # any object with run(model, case) -> RunOutput
    scorers=[make_scorer("exact-match"), MyGroundednessScorer()],
    repeats=3,
    concurrency=4,
)
record.save("run-record.json")
print(render(record, "text", by_tag=True))
```

## Customising Trialmark

There are four customisation points: **runners** (call a model), **scorers** (turn an answer into
metrics), **loaders** (read a test set from a file format) and **report writers**.
[ARCHITECTURE.md](ARCHITECTURE.md) gives each interface and explains what stays fixed in the
core and why.

You do not need to fork Trialmark to customise it. Install it from PyPI and add plugins:

- For a one-off model call, use the `python` runner, as above.
- From Python, pass your own runner and scorer objects to `run_trial`.
- To share a plugin, publish it as its own package.

### Writing a plugin

A plugin package declares an entry point in one of the groups `trialmark.runners`,
`trialmark.scorers`, `trialmark.loaders` or `trialmark.reports`:

```python
# trialmark_acme/__init__.py
from trialmark import RunOutput

class AcmeRunner:
    def __init__(self, endpoint="https://api.acme.example"):
        self.endpoint = endpoint

    def run(self, model, case):
        reply = call_acme(self.endpoint, model.id, case.input, **model.settings)
        return RunOutput(output=reply.text, cost_usd=reply.cost)
```

```toml
# pyproject.toml of the plugin package
[project.entry-points."trialmark.runners"]
acme = "trialmark_acme:AcmeRunner"
```

Once it is installed, `trialmark plugins` lists it, and a configuration uses it with
`"runner": "acme"`, with options under `"runners": {"acme": {"endpoint": "..."}}`. A plugin cannot
take the name of a built-in plugin.

## Formats

**Test set**

```json
{
  "name": "contract-questions",
  "version": "2026-11-05",
  "cases": [
    { "id": "q1", "input": "What is the notice period?", "reference": "Sixty days' written notice.", "tags": ["factual"] }
  ]
}
```

The hash covers the cases (their ids, inputs, references and tags), not the name or version. It
is the SHA-256 of canonical JSON under RFC 8785, so other languages can compute the same hash.
Hashes written before 0.3 start with `sha256:` and are still checked. `trialmark schema testset`,
`passmark` and `run-record` print the JSON Schema of each format.

**Pass mark**

| Field | Meaning |
|---|---|
| `metric` | The score the decision rests on, such as `correct` |
| `tolerance_points` | How many percentage points below the best model still passes |
| `floors` | Minimum mean scores on other metrics, such as `{"grounded": 0.95}` |
| `choose` | Which passing model to choose: `cheapest`, `fastest` or `best` |

**Metrics** are whatever your scorer produces, each between 0 and 1. A model's score on a
metric is the mean within each repeat; the report shows the mean of those and their range.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
