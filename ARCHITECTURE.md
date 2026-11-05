# Trialmark architecture

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
| Test set and its hash | `testset.py` | A rerun must be able to prove it used the same cases |
| Pass mark and its hash | `passmark.py` | The rule is set before the results, and the record shows any later change |
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
taken (Trialmark times the call when it is left empty) and an optional error.

Built in: `echo`, a stand-in model for trying Trialmark and for tests, and `python`, which calls
a function you name (`"path/to/file.py:function"` or `"module:function"`), so a model can be
tested without writing a plugin package.

### Scorer

Turns an output into metrics. Constructed once per run with its options.

```python
class Scorer(Protocol):
    metrics: tuple[str, ...]      # every metric score() can return
    def score(self, case: Case, output: Any) -> dict[str, float]: ...   # each between 0 and 1
```

`metrics` lets the core score a failed call zero on every metric. A scorer that raises an
error scores the case zero and leaves a note on the result.

Built in: `exact-match` (metric `correct`, ignoring case, punctuation and spacing by default)
and `fields` (for extraction: `fields_correct` and `all_fields_correct`, comparing a reference
object field by field).

### Loader

Reads a test set from a file: `(path, **options) -> TestSet`. Chosen by the file extension unless
named. Built in: `json` and `csv` (columns `id`, `input`, `reference` and an optional `tags`,
separated by semicolons).

### Report writer

Renders a record: `(record, by_tag) -> str`. Built in: `text`, `markdown` and `json`.

## How plugins are found

1. Built-in plugins, registered in `builtins.py`.
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
| `judge` | Optional: the judge model and prompt version, recorded for readers |
| `environment` | Optional: anything else to record, such as a code version |
| `output` | Where to save the run record |

Paths in the file are relative to the file. The `python` runner's file paths are relative to the
folder Trialmark is run from.
