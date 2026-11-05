# Trialmark starter: anthropic

A ready-to-run acceptance test. Two models, claude-haiku-5-5 and claude-sonnet-5-5, answer ten questions about a short
fictional consulting agreement (`contract.md`), three times each. A third model, claude-opus-5-5, grades
every answer against the reference answers in `questions.csv`. The pass mark in `config.json`
chooses the cheapest model within 5 points of the best, with at least 90% of its answers
grounded in the document.

## Run it

```bash
pip install "trialmark[anthropic]"
export ANTHROPIC_API_KEY=...

trialmark run config.json                        # prints the plan and a cost estimate, spends nothing
trialmark run config.json --limit 3 --yes        # three questions first, to see it working
trialmark run config.json --by-tag --yes         # the full test
trialmark gate record.json --model claude-haiku-5-5     # exit 0 if it meets the pass mark
```

## Make it yours

- **Your questions:** replace `questions.csv`. Keep the columns `id`, `input`, `reference` and
  `tags`; tags give the report its breakdown by kind of question.
- **Your documents:** replace `contract.md`, and list your files under `documents` for each
  model and for the judge. Whole documents are put in front of the model, up to its context
  limit. If your real system retrieves passages instead, test that system through the
  `python` runner rather than the bare model.
- **Your models:** change the model ids, and their prices under `pricing`, in US dollars per
  million tokens. The prices here were current when the starter was written; check yours.
- **Your pass mark:** set it before you look at the results. That is the point of an
  acceptance test.
- **Check the judge:** `trialmark judge-check sample record.json --test-set questions.csv` writes
  a sample for you to grade; `trialmark judge-check score record.json grades.csv` says how
  often the judge agreed with you.
