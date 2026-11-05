# Trialmark

**Model acceptance tests for language models.** Test models on your own work, decide in advance
what result is good enough, and keep a record that anyone can rerun and check.

Choosing a language model is a trade between accuracy, cost and speed. Trialmark makes that
choice systematic:

1. **Your own test set.** Cases from your own work, each with a reference answer written by a
   person and tagged by kind, such as "factual" or "multi-part". The set is hashed, so a later
   run can prove it used exactly the same cases.
2. **A pass mark set before the run.** For example: "choose the cheapest model within 3 points
   of the best on correctness, as long as at least 95% of its answers are grounded". The rule
   is stored with its hash and the time it was set, so it cannot be quietly changed after the
   results are in.
3. **Repeats, with the range shown.** Models do not give the same answer every time. Each model
   runs several times, and the report shows the lowest and highest result so that a difference
   inside the range is read as no difference.
4. **A report by kind of case.** A small model may be as good as a large one on single facts
   and worse on multi-part questions. The breakdown by tag shows where.
5. **A run record and a release gate.** Every run writes one JSON file with the test set's hash,
   the models and their settings, the judge, the pass mark and every result. `trialmark gate`
   exits with 0 or 1, so a pipeline can refuse a model change that fails the pass mark.

Trialmark runs on your own machines. Your test sets, reference answers and records stay with you.

## Where it comes from

Trialmark was spun out of the model benchmark in [Forge](https://www.forgeprivate.com), a
governed layer through which organisations delegate work to AI. That benchmark compares models
on a fixed set of business-document questions, through Forge's own answer path, with three
repeats and accuracy, cost and speed side by side. Trialmark makes the same kind of test
available to any developer or team, with or without Forge.

## Status

Trialmark is at an early stage. Version 0.1 provides the formats and the decision:

| Built in 0.1 | Planned |
|---|---|
| The test set format, with hashing and tags | Runners that call models directly (Anthropic, OpenAI and others) |
| The pass mark and the decision rule | A reference-answer judge, which grades an answer as correct, partly correct or incorrect and checks that it is grounded |
| The run record, with the pass mark's hash | A field-by-field scorer for extraction and classification |
| The report, with ranges and the breakdown by tag | A runner that tests a model inside Forge, with Forge's retrieval and rules applied |
| `trialmark gate` for pipelines | Logging runs to MLflow |

In 0.1 you produce the results yourself, with your own code, and Trialmark records, reports and
decides on them.

## Install

```bash
pip install trialmark
```

Python 3.10 or later. The core has no dependencies.

## Try it

The `examples` folder holds a five-question test set and an illustrative run of three made-up
models. The scores in it are invented to show the format; they are not measurements of any real
model.

```bash
trialmark validate examples/testset.json
trialmark report examples/run-record.json --by-tag
trialmark gate examples/run-record.json --model medium-model --test-set examples/testset.json
```

## Use it from Python

```python
from trialmark import ModelEntry, PassMark, Result, RunRecord, load_test_set, text_report

test_set = load_test_set("my-testset.json")

# Fix the decision before any model runs.
pass_mark = PassMark(metric="correct", tolerance_points=3, floors={"grounded": 0.95}, choose="cheapest")
record = RunRecord.start(
    test_set,
    pass_mark,
    [ModelEntry(id="model-a", provider="provider-x"), ModelEntry(id="model-b", provider="provider-y")],
    repeats=3,
    judge={"model": "judge-model", "prompt_version": "1"},
)

for repeat in range(3):
    for model in ("model-a", "model-b"):
        for case in test_set.cases:
            answer, cost, ms = call_your_model(model, case.input)   # your code
            score = grade(answer, case.reference)                     # your code: 0, 0.5 or 1
            record.add(Result(
                model=model, repeat=repeat, case_id=case.id, tags=list(case.tags),
                metrics={"correct": score, "grounded": 1.0},
                output=answer, cost_usd=cost, latency_ms=ms,
            ))

record.save("run-record.json")
print(text_report(record, by_tag=True))
```

## Formats

**Test set**

```json
{
  "name": "contract-questions",
  "version": "2026-11-05",
  "cases": [
    { "id": "q1", "input": "What is the notice period?", "reference": "Sixty days' written notice.", "tags": ["factual"] }
  ]
}
```

The hash covers the cases (their ids, inputs, references and tags), not the name or version.

**Pass mark**

| Field | Meaning |
|---|---|
| `metric` | The score the decision rests on, such as `correct` |
| `tolerance_points` | How many percentage points below the best model still passes |
| `floors` | Minimum mean scores on other metrics, such as `{"grounded": 0.95}` |
| `choose` | Which passing model to choose: `cheapest`, `fastest` or `best` |

**Metrics** are whatever your scorer produces, each between 0 and 1. A model's score on a
metric is the mean within each repeat; the report shows the mean of those and their range.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
