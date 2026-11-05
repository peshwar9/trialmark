# Trialmark starter: Summarising and other writing (OpenAI)

Two models summarise four fictional sets of meeting notes and emails
(`notes.json`). Writing has no single right answer, so each case carries a checklist of what a
good summary must contain, such as "Mentions the review on 8 December", and three items in
`config.json` apply to every case: under 120 words, nothing that is not in the source, and plain
English. A third
model, the judge, marks each item met or not met. The score is the share of items met; the pass
mark chooses the cheapest model within 5 points of the best.

The same approach suits any writing or analysis: emails, reports, explanations, reviews. Write
down what a good answer must do, item by item.

Models under test: `gpt-4o-mini` and `gpt-5.6-sol`. Judge: `gpt-6-astra`.

## Run it

```bash
pip install "trialmark[openai]"
export OPENAI_API_KEY=...

trialmark run config.json                        # the plan and a cost estimate; spends nothing
trialmark run config.json --limit 3 --yes        # three cases first, to see it working
trialmark run config.json --by-tag --yes         # the full test
trialmark gate record.json --model gpt-4o-mini
```

## Make it yours

- **Your cases:** replace `notes.json` with your own, in the same format. Tags give the report its
  breakdown by kind of case.
- **Your models:** change the model ids in `config.json`, and their prices under `pricing`, in US
  dollars per million tokens. The prices here were current when the starter was written; check
  yours.
- **Your instructions:** the `system` setting is what each model is told. Keep it the same for
  every model, so only the model changes.
- **Your pass mark:** set it before you look at the results. That is the point of an acceptance
  test.
- **Check the judge:** `trialmark judge-check sample record.json --test-set notes.json` writes a sample for you to grade; `trialmark judge-check score record.json grades.csv` says how often the judge agreed with you.

See [docs/tasks.md](https://github.com/peshwar9/trialmark/blob/main/docs/tasks.md) for every kind
of task Trialmark can test, and how.
