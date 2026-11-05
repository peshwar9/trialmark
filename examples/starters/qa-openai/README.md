# Trialmark starter: Answering questions from a document (OpenAI)

Two models answer ten questions about a short fictional consulting agreement
(`contract.md`). A third model, the judge, grades every answer against the reference answers in
`questions.csv`: correct, partly correct or incorrect, whether it stuck to the document
(grounded), and whether it declined when it should. The pass mark chooses the cheapest model
within 5 points of the best on correct answers, with at least 90% of its answers grounded.

The questions are tagged by kind (`factual`, `multi-part`, `calculation`, `not-in-documents`),
so `--by-tag` shows where a cheaper model keeps up and where it falls behind.

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

- **Your cases:** replace `questions.csv` with your own, in the same format. Tags give the report its
  breakdown by kind of case.
- **Your models:** change the model ids in `config.json`, and their prices under `pricing`, in US
  dollars per million tokens. The prices here were current when the starter was written; check
  yours.
- **Your instructions:** the `system` setting is what each model is told. Keep it the same for
  every model, so only the model changes.
- **Your pass mark:** set it before you look at the results. That is the point of an acceptance
  test.
- **Check the judge:** `trialmark judge-check sample record.json --test-set questions.csv` writes a sample for you to grade; `trialmark judge-check score record.json grades.csv` says how often the judge agreed with you.

See [docs/tasks.md](https://github.com/peshwar9/trialmark/blob/main/docs/tasks.md) for every kind
of task Trialmark can test, and how.
