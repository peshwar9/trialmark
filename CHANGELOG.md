# Changelog

## 0.4.0, 5 November 2026

- **Nothing is spent without `--yes`.** `trialmark run` prints the plan and a cost estimate for
  each model and for the judge, and calls no paid model until `--yes` is given. Runs with only
  the `echo` stand-in need no `--yes`. This changes how `trialmark run` behaves: scripts that
  ran it without `--yes` must add it.
- `--limit N` and `--only id,id` run part of the test set. The record holds the hash of the
  cases actually run.
- `trialmark init anthropic` and `trialmark init openai` write a ready-to-run starter: a
  fictional contract, ten tagged questions and a configuration with current models and prices.
  The same starters are in `examples/quickstart-anthropic` and `examples/quickstart-openai`.
- The judge takes `pricing`, and the record and the report show what it spent.
- `trialmark judge-check sample` and `score` measure how often the judge agrees with a person.
- Runners and the judge make their client when the run starts, so an estimate works before an
  SDK or key is set up, and a missing one stops the run once with a clear message.
- Plugins may offer `estimate_cost`, `costs_money` and `prepare` (see ARCHITECTURE.md).

## 0.3.1, 5 November 2026

- The README, the package description and the command's help describe Trialmark as a framework
  for evaluating language models and acceptance-testing them for your task. No change to
  behaviour or formats.

## 0.3.0, 5 November 2026

- Runners that call Anthropic and OpenAI models directly, installed as extras:
  `pip install "trialmark[anthropic]"` or `"trialmark[openai]"`. Prices are given per model.
- A reference-answer judge scorer, which grades free-text answers as correct, partly correct or
  incorrect, and whether they are grounded in the source documents and whether they declined.
  The record stores the judge's model, documents and a hash of its rules.
- Hashes now use canonical JSON under RFC 8785 and start with `jcs-sha256:`, so other languages
  can compute the same hash. Hashes from earlier versions (`sha256:`) are still checked.
- JSON Schema files for the test set, the pass mark and the run record, printed by
  `trialmark schema`.
- Scorers and runners can attach a note to each result.
- Relative paths in plugin options and model settings are resolved against the configuration
  file's folder.
- The README no longer says a pass mark cannot be changed after a run. A hash catches an
  accidental change; signed records, planned, will catch a deliberate one.

## 0.2.0, 5 November 2026

- Plugins for four customisation points: runners, scorers, loaders and report writers, found
  through Python entry points. See ARCHITECTURE.md.
- `trialmark run` runs a trial from a configuration file, with repeats and concurrency.
- Built-in runners: `echo`, a stand-in model, and `python`, which calls a function you name.
- Built-in scorers: `exact-match`, and `fields` for extraction.
- A CSV loader, and Markdown and JSON reports.
- The run record names each model's runner and the version of every plugin used.
- A model with any failed call no longer passes the pass mark.
- `trialmark plugins` lists what Trialmark can find.
- Records written by 0.1 still load.

## 0.1.0, 5 November 2026

- Test sets with hashing and tags, the pass mark stored with its hash before the run, run
  records, reports with ranges and a breakdown by tag, and `trialmark gate`.
