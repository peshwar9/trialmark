# Trialmark

**Model acceptance tests for language models.** Test models on your own work, decide in advance
what result is good enough, and keep a record that anyone can rerun and check.

Choosing a language model is a trade between accuracy, cost and speed. Trialmark makes that
choice systematic:

1. **Your own test set.** Cases from your own work, each with a reference answer written by a
   person and tagged by kind, such as "factual" or "multi-part". The set is hashed, so a later
   run can prove it used exactly the same cases.
2. **A pass mark set before the run.** For example: "choose the cheapest model within 3 points
   of the best on correctness, as long as at least 95% of its answers are grounded". The rule
   is stored with its hash and the time it was set, so an accidental change after the results
   are in is caught. Signed records, planned, will also make a deliberate change detectable.
3. **Repeats, with the range shown.** Models do not give the same answer every time. Each model
   runs several times, and the report shows the lowest and highest result so that a difference
   inside the range is read as no difference.
4. **A report by kind of case.** A small model may be as good as a large one on single facts
   and worse on multi-part questions. The breakdown by tag shows where.
5. **A run record and a release gate.** Every run writes one JSON file with the test set's hash,
   the models and their settings, the judge, the pass mark and every result. `trialmark gate`
   exits with 0 or 1, so a pipeline can refuse a model change that fails the pass mark.

Trialmark runs on your own machines. Your test sets, reference answers and records stay with you.

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
| The test set format, with hashing and tags, read from JSON or CSV | A runner that tests a model inside Forge, with Forge's retrieval and rules applied |
| The pass mark and the decision rule | Signed run records |
| The run record, with the pass mark's hash, the judge and the plugins used | An HTML report with a chart of correctness against cost |
| `trialmark run`, which runs every model on every case for every repeat | Logging runs to MLflow |
| Runners that call Anthropic and OpenAI models directly, and a runner for a function of your own | |
| A reference-answer judge, which grades an answer as correct, partly correct or incorrect, and whether it is grounded and whether it declined | |
| An exact-match scorer and a field-by-field scorer for extraction | |
| Plugins for runners, scorers, loaders and reports (see [ARCHITECTURE.md](ARCHITECTURE.md)) | |
| Reports as text, Markdown or JSON, with ranges and the breakdown by tag | |
| `trialmark gate` for pipelines, and JSON Schema files for every format | |

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

## Try it

The `examples` folder holds a five-question test set and a configuration that compares three
stand-in models, so a run needs no API key. Run it from the repository's root folder:

```bash
trialmark validate examples/testset.json
trialmark run examples/config.json --by-tag
trialmark report examples/config-run-record.json --format markdown
trialmark gate examples/config-run-record.json --model perfect-model
trialmark plugins
```

`examples/run-record.json` is an illustrative record of three made-up models whose scores are
invented to show the format. They are not measurements of any real model.

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
trialmark run config.json --by-tag
```

Every run calls the models for real and costs money: here, two models, three repeats and every
question, plus one judge call per answer.

A few things to know:

- **Prices** are yours to give, in US dollars per million tokens, because they change. Check
  your provider's current prices. A model without prices reports a cost of zero, with a note on
  each result.
- **The judge** works best when it is not one of the models under test. Check it against a
  person's grades on part of the set before relying on it. Its model, the documents it read and
  a hash of its rules are kept in the record. `rules_file` replaces the built-in rules with your
  own.
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
