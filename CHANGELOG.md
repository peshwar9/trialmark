# Changelog

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
