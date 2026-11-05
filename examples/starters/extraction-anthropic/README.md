# Trialmark starter: Extracting fields from documents (Anthropic)

Two models read six fictional invoices (`invoices.json`), some tidy and some messy,
and return five fields as JSON. No judge is needed: the `fields` scorer compares each field with
the value a person read from the invoice (numbers within 0.5%), and the `json-schema` scorer
checks the reply is valid JSON of the right shape (`schema.json`). The pass mark chooses the
cheapest model within 2 points of the best on fields correct, with every reply matching the
schema.

The invoices are tagged `tidy` or `messy`, so `--by-tag` shows whether a cheaper model copes
with the messy ones.

Models under test: `claude-haiku-5-5` and `claude-sonnet-5-5`.

## Run it

```bash
pip install "trialmark[anthropic,jsonschema]"
export ANTHROPIC_API_KEY=...

trialmark run config.json                        # the plan and a cost estimate; spends nothing
trialmark run config.json --limit 3 --yes        # three cases first, to see it working
trialmark run config.json --by-tag --yes         # the full test
trialmark gate record.json --model claude-haiku-5-5
```

## Make it yours

- **Your cases:** replace `invoices.json` with your own, in the same format. Tags give the report its
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
