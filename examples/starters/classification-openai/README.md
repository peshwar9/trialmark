# Trialmark starter: Classifying messages into categories (OpenAI)

Two models sort twelve fictional customer messages (`tickets.csv`) into four
categories: billing, technical, account and feedback. No judge is needed: the `label` scorer
reads the category from each answer, even one like "Category: Billing.", and compares it with
the right one. The pass mark chooses the cheapest model within 5 points of the best.

The messages are tagged `clear` or `mixed` (a mixed one touches two categories), so `--by-tag`
shows where models disagree. `trialmark confusion` then shows, for each category, how often the
model was right when it chose it (precision), how many of its cases it found (recall), and which
categories it mistook for which.

Models under test: `gpt-4o-mini` and `gpt-5.6-sol`.

## Run it

```bash
pip install "trialmark[openai]"
export OPENAI_API_KEY=...

trialmark run config.json                        # the plan and a cost estimate; spends nothing
trialmark run config.json --limit 3 --yes        # three cases first, to see it working
trialmark run config.json --by-tag --yes         # the full test
trialmark gate record.json --model gpt-4o-mini
trialmark confusion record.json --test-set tickets.csv
```

## Make it yours

- **Your cases:** replace `tickets.csv` with your own, in the same format. Tags give the report its
  breakdown by kind of case.
- **Your models:** change the model ids in `config.json`, and their prices under `pricing`, in US
  dollars per million tokens. The prices here were current when the starter was written; check
  yours.
- **Your instructions:** the `system` setting is what each model is told. Keep it the same for
  every model, so only the model changes.
- **Your pass mark:** set it before you look at the results. That is the point of an acceptance
  test.

See [docs/tasks.md](https://github.com/peshwar9/trialmark/blob/main/docs/tasks.md) for every kind
of task Trialmark can test, and how.
