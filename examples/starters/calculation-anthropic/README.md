# Trialmark starter: Calculating figures from a document (Anthropic)

Two models answer six pricing questions about a fictional price list
(`pricelist.md`), some needing one step and some several (a discount, delivery, VAT). No judge
is needed: each model may show its working but must end with a line "Answer: <number>", and the
`number` scorer reads the number after "Answer:" and accepts it within 0.5% of the right one. The pass mark chooses the cheapest model that is as accurate as the best.

The questions are tagged `one-step` or `two-step`, so `--by-tag` shows whether a cheaper model
slips when a sum has several steps.

Models under test: `claude-haiku-5-5` and `claude-sonnet-5-5`.

## Run it

```bash
pip install "trialmark[anthropic]"
export ANTHROPIC_API_KEY=...

trialmark run config.json                        # the plan and a cost estimate; spends nothing
trialmark run config.json --limit 3 --yes        # three cases first, to see it working
trialmark run config.json --by-tag --yes         # the full test
trialmark gate record.json --model claude-haiku-5-5
```

## Make it yours

- **Your cases:** replace `questions.csv` with your own, in the same format. Tags give the report its
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
