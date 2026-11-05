# Trialmark architecture

For why it is built this way, see [What makes Trialmark different](docs/design.md).

Trialmark has a small fixed core and four customisation points. The core is what makes two runs
comparable, so it does not change from one team to the next. Everything that touches a model,
a file format or a way of scoring is a plugin.

## How a run flows

```
 test set ──┐                       ┌── runner (one per model) ──┐
 (loader)   │                       │                            │
            ▼                       │                            ▼
 pass mark ──► run record started ──► each repeat × model × case ──► scorers ──► result
 (fixed)       (hashes fixed)                                                     │
                                                                                  ▼
                                    report (writer) ◄── summary and decision ◄── run record
                                    gate (exit 0 or 1)
```

1. A **loader** reads the test set. The core hashes its cases.
2. The **pass mark** is parsed and hashed, and the **run record** is started with both hashes and
   the time. From this point the decision rule cannot change without the record showing it.
3. For each repeat, each model and each case, the model's **runner** produces an output, with
   its cost, tokens and time taken. A call that raises an error is recorded with the error,
   scored zero, and does not stop the run.
4. Each **scorer** turns the output and the case's reference into metrics between 0 and 1.
5. The core summarises each model: the mean of each metric within each repeat, then the mean
   and range across repeats, the cost per 100 cases and the median time. It does the same for
   each tag.
6. The core applies the pass mark and decides which model, if any, passes and which is chosen.
   A model with any failed call cannot pass, because its scores are incomplete.
7. A **report writer** renders the record and the decision. `trialmark gate` turns the decision
   for one model into an exit code.

## What is fixed in the core

| Part | Module | Why it is fixed |
|---|---|---|
| Canonical JSON and hashes | `canonical.py` | Every hash is SHA-256 over canonical JSON (RFC 8785), so a program in any language computes the same hash. Hashes from before 0.3 (`sha256:`) are still checked with the older method. |
| Test set and its hash | `testset.py` | A rerun must be able to prove it used the same cases |
| Pass mark and its hash | `passmark.py` | The rule is set before the results, and an accidental later change is caught. A hash does not stop someone changing the rule and recomputing it; signed records, planned, will. |
| The decision | `passmark.py` | The same results and rule must always give the same choice |
| Run record | `record.py` | One format that any tool can read |
| Summaries | `report.py` | Means, ranges across repeats and breakdowns by tag are computed one way |
| The run loop | `run.py` | Every model sees every case, repeats are counted the same way, and failures are recorded |

## The four customisation points

All interfaces are in `src/trialmark/plugins.py`.

### Runner

Calls one model on one case. Constructed once per run with options from the configuration's
`runners` section; may be called from several threads.

```python
class Runner(Protocol):
    def run(self, model: ModelEntry, case: Case) -> RunOutput: ...
```

`model.settings` holds that model's settings from the configuration, such as a temperature or
an endpoint. `RunOutput` carries the output, cost, input and output tokens, an optional time
taken (Trialmark times the call when it is left empty), an optional error and an optional note.

Built in:
- `anthropic` and `openai` call a model directly through the provider's SDK, installed as an
  extra. Their settings take instructions, whole documents to put in front of the model, an
  output limit, and prices per million tokens (Trialmark ships no price list, because prices
  change). Credentials come from the environment, as the SDK reads them.
- `python` calls a function you name (`"path/to/file.py:function"` or `"module:function"`), so
  any model or system can be tested without writing a plugin package.
- `echo` is a stand-in model for trying Trialmark and for tests.

Optional on any runner:
- `estimate_cost(model, case)` returns the rough cost of one call in US dollars, or None when it
  cannot be known. `trialmark run` adds these up before anything runs.
- `costs_money`: `trialmark run` asks for `--yes` before any run with a runner that costs money.
  Runners are assumed to unless they set it to False, as `echo` does.
- `prepare()` makes any client the runner needs. It is called once before the first call, so a
  missing SDK or key stops the run with one message instead of failing every case, and a cost
  estimate works before either is set up.

### Scorer

Turns an output into metrics. Constructed once per run with its options.

```python
class Scorer(Protocol):
    metrics: tuple[str, ...]      # every metric score() can return
    def score(self, case: Case, output: Any) -> dict[str, float]: ...   # each between 0 and 1
```

Scorers may offer `estimate_cost(case)`, `costs_money` and `prepare()` as runners do; scorers
are assumed not to cost money unless they say so, as the `judge` does.

`metrics` lets the core score a failed call zero on every metric. A scorer that raises an
error scores the case zero and leaves a note on the result. `score` may also return a short
explanation under the key `note`, which is kept on the result. A scorer that grades with a model
sets an attribute `judge`, a dict describing the judge, which the run record stores.

Built in:
- `judge` grades a free-text answer against the reference with a language model, through the
  Anthropic or OpenAI SDK, with structured output. Metrics: `correct`, `partial`, `declined`,
  and `grounded` when source documents are given. `rules_file` replaces the built-in grading
  rules; the record keeps a hash of the rules in use.
- `checklist` (in `providers.py`), for writing and analysis: a judge model marks each item of a
  checklist met or not met. Metrics: `checklist_met`, `all_met`.
- `exact-match` (metric `correct`, ignoring case, punctuation and spacing by default).
- `fields` (for extraction: `fields_correct` and `all_fields_correct`, comparing a reference
  object field by field, and numbers as numbers).
- In `scorers.py`: `label` for classification, `number` for figures within a tolerance, and
  `json-schema` for structured output.

[docs/tasks.md](docs/tasks.md) says which scorer suits which kind of task.

### Loader

Reads a test set from a file: `(path, **options) -> TestSet`. Chosen by the file extension unless
named. Built in: `json` and `csv` (columns `id`, `input`, `reference` and an optional `tags`,
separated by semicolons).

### Report writer

Renders a record: `(record, by_tag) -> str`. Built in: `text`, `markdown` and `json`.

## How plugins are found

1. Built-in plugins, registered in `builtins.py` and `providers.py`.
2. Installed packages that declare an entry point in `trialmark.runners`, `trialmark.scorers`,
   `trialmark.loaders` or `trialmark.reports`.

A plugin cannot take a built-in plugin's name; Trialmark stops with an error naming the package.
`trialmark plugins` lists everything it can find and where each plugin comes from. The run
record stores the name and version of every runner and scorer used.

From Python, plugin objects can also be passed straight to `run_trial`, with no registration.

## Customising without forking

Teams extend Trialmark by installing it from PyPI and adding plugins, not by forking it:

- **A one-off model call:** write a function and use the `python` runner.
- **A reusable runner, scorer, loader or report:** publish a package, for example
  `trialmark-acme`, that declares an entry point (see "Writing a plugin" in the README).
- **A change to the core:** open an issue or a pull request. A fork cannot publish under the name
  `trialmark` on PyPI, and its users stop receiving updates, so forking is the last resort.

## Before and after a run

`trialmark run` narrows the cases (`--limit`, `--only`), prints the plan and the estimate
(`estimate.py`), and stops unless `--yes` is given when anything costs money. The record of a
narrowed run holds the hash of the cases actually run. After the run, a scorer with a `spent`
attribute, such as the judge, has its spend written into the record's `judge` entry.

`trialmark init <task> --provider <provider>` writes a starter built by `src/trialmark/starters/`:
each task's content files (`starters/files/<task>/`), a configuration combining the task with
the provider's models and prices, and a README. `examples/starters/` holds every starter,
written by `examples/make_starters.py`, and a test keeps them identical to what `init` writes.
`trialmark confusion` (`confusion.py`) computes per-label precision and recall for a
classification run. `trialmark judge-check` (`judgecheck.py`)
writes a blind sample of answers for a person to grade and compares their grades with the run's.

## Configuration file

`trialmark run config.json` reads:

| Key | Meaning |
|---|---|
| `test_set` | A path, or `{"path", "loader", "options"}` |
| `pass_mark` | The rule (see the README) |
| `models` | A list of `{"id", "runner", "provider", "settings"}` |
| `runners` | Optional options for each runner, by name |
| `scorers` | A list of names, or `{"name", "options"}` |
| `repeats` | How many times each model runs the whole set (default 3) |
| `concurrency` | How many calls run at once (default 1) |
| `judge` | Optional: a description of the judge, recorded for readers. Filled in by the `judge` scorer when left out. |
| `environment` | Optional: anything else to record, such as a code version |
| `output` | Where to save the run record |

Paths in the file are relative to the file, including the paths in plugin options and model
settings: a plugin class whose constructor accepts `base_dir` receives the configuration's
folder. The `python` runner also looks for a relative file in the folder Trialmark is run from.

## File formats

`src/trialmark/schemas/` holds a JSON Schema for the test set, the pass mark and the run record.
`trialmark schema <name>` prints one. Code in another language can write Trialmark files against
them, and compute the same hashes by following RFC 8785.
