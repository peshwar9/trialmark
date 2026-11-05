# Changelog

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
