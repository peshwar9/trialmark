# What you can test with Trialmark

Trialmark tests any task where you can give a model an input and say what a good output is.
What changes from one kind of task to the next is how an output is marked. This guide takes each
kind in turn: what it is, how Trialmark marks it, what your test cases look like, and the
starter that shows it working.

Every starter runs as it is, once you add an Anthropic or OpenAI key:

```bash
trialmark init <task> --provider anthropic     # or --provider openai
cd trialmark-<task>-anthropic
trialmark run config.json                      # the plan and a cost estimate; spends nothing
trialmark run config.json --limit 3 --yes      # a few cases first
trialmark run config.json --by-tag --yes       # the full test
```

The same starters are in [`examples/starters/`](../examples/starters) to read or copy.

| Kind of task | Examples | Marked by | Needs a judge model | Starter |
|---|---|---|---|---|
| [Answering questions from documents](#answering-questions-from-documents) | A help desk over your manuals, questions about a contract, RAG | `judge` | Yes | `qa` |
| [Extracting fields](#extracting-fields-from-documents-and-forms) | Invoices, forms, CVs, contracts into a table | `fields` and `json-schema` | No | `extraction` |
| [Classifying](#classifying-into-categories) | Routing tickets, tagging documents, spotting intent | `label`, then `trialmark confusion` | No | `classification` |
| [Writing and analysis](#writing-summarising-and-analysis) | Summaries, emails, reports, reviews, explanations | `checklist` | Yes | `summarisation` |
| [Calculating](#calculating-figures) | Prices, totals, dates, figures from a document | `number` | No | `calculation` |
| [Structured output](#structured-output) | Any task whose answer must be JSON of a given shape | `json-schema` | No | part of `extraction` |
| [Your own system](#testing-your-own-system-rather-than-a-bare-model) | Your retrieval pipeline, your agent, your app | any of the above | Depends | none: see below |

Scorers can be combined: list several under `scorers` and each adds its own metrics.

---

## Answering questions from documents

**What it is.** A model answers questions about your documents: a contract, a manual, a policy.
This is the usual retrieval-augmented generation (RAG) case.

**How it is marked.** The `judge` scorer asks a model to compare each answer with the right
answer you wrote, and returns:

| Metric | Meaning |
|---|---|
| `correct` | The answer has every essential fact and nothing that contradicts the documents |
| `partial` | Right as far as it goes, but missing an essential part |
| `grounded` | Every claim is supported by the documents (only when the judge is given them) |
| `declined` | The answer said it could not answer, though it was not correct to |

**Your test cases.** A CSV file with `id`, `input` (the question), `reference` (the right
answer, written by a person) and optional `tags`. For a question the documents cannot answer,
write a reference such as "The documents do not say": then declining is correct and inventing
an answer is not.

```csv
id,input,reference,tags
q1,What is the notice period?,Sixty days' written notice.,factual
q9,Who is the project manager?,The documents do not say.,not-in-documents
```

**Configuration.**

```json
"models": [{ "id": "claude-sonnet-5-5", "runner": "anthropic",
             "settings": { "documents": ["contract.md"], "pricing": { "input": 2, "output": 10 } } }],
"scorers": [{ "name": "judge", "options": { "model": "claude-opus-5-5", "documents": ["contract.md"],
                                            "pricing": { "input": 4, "output": 20 } } }]
```

`documents` puts the whole files in front of the model. If your system retrieves passages
instead, test your system, not the bare model: see [your own system](#testing-your-own-system-rather-than-a-bare-model).

**Starter:** `trialmark init qa`.

---

## Extracting fields from documents and forms

**What it is.** A model reads a document and fills in named fields: an invoice's number, date
and total; a form's applicant and address; a contract's parties and term.

**How it is marked.** No judge is needed.

- The `fields` scorer compares each field with the value a person read. Text is compared
  ignoring case and punctuation, and numbers as numbers, so `"1,250.00"` matches `1250`. Its
  `tolerance` option allows a small difference in numeric fields.
- The `json-schema` scorer checks the answer is valid JSON of the right shape.

| Metric | Meaning |
|---|---|
| `fields_correct` | The share of fields the model got right |
| `all_fields_correct` | 1 only if every field is right |
| `valid_json`, `matches_schema` | From `json-schema`: the answer parses, and matches the schema |

The note on each result names the fields that were wrong.

**Your test cases.** A JSON test set, because each reference is an object:

```json
{ "name": "invoices", "version": "1", "cases": [
  { "id": "inv1", "input": "INVOICE ... Total due GBP 3,888.00",
    "reference": { "invoice_number": "NB-2026-0142", "invoice_date": "2026-03-14", "total": 3888.00 },
    "tags": ["tidy"] }
] }
```

Tell every model the exact keys and formats to use (for example, dates as YYYY-MM-DD) in its
`system` setting, so a model is not marked down for a format you never asked for.

**Configuration.**

```json
"scorers": [
  { "name": "fields", "options": { "tolerance": 0.005 } },
  { "name": "json-schema", "options": { "schema_file": "schema.json" } }
]
```

`json-schema` needs `pip install "trialmark[jsonschema]"`.

**Starter:** `trialmark init extraction`.

---

## Classifying into categories

**What it is.** A model puts each input into one of a fixed set of categories: routing support
tickets, tagging documents by type, detecting intent or sentiment.

**How it is marked.** No judge is needed. The `label` scorer reads the category from the answer
(an answer such as "Category: Billing." counts as `billing` when you list the allowed labels)
and compares it with the right one. Its metric is `correct`.

Accuracy alone hides which categories a model gets wrong, so after a run:

```bash
trialmark confusion record.json --test-set tickets.csv
```

gives each category's **precision** (of the answers given that category, the share that were
right), **recall** (of the cases in that category, the share the model found) and a table of
which categories it mistook for which.

**Your test cases.** A CSV file whose `reference` is the right category:

```csv
id,input,reference,tags
t1,"I was charged twice this month, please refund one.",billing,clear
t9,"I upgraded but the app still shows monthly, and I was charged.",billing,mixed
```

Include cases that sit between two categories and tag them, so `--by-tag` shows how models
handle them.

**Configuration.**

```json
"scorers": [{ "name": "label", "options": { "labels": ["billing", "technical", "account", "feedback"] } }]
```

**Starter:** `trialmark init classification`.

---

## Writing, summarising and analysis

**What it is.** Any task with no single right answer: summaries, emails, reports, explanations,
reviews, analyses.

**How it is marked.** Write down what a good answer must do, as a checklist. The `checklist`
scorer asks a judge model to mark each item met or not met.

| Metric | Meaning |
|---|---|
| `checklist_met` | The share of checklist items met |
| `all_met` | 1 only if every item is met |

The note on each result lists the items missed. Items in the scorer's `checklist` option apply
to every case, such as "Is under 120 words" or "States nothing that is not in the source";
each case adds its own, such as "Mentions the review on 8 December".

**Your test cases.** A JSON test set whose reference is the case's checklist:

```json
{ "id": "s1", "input": "Summarise these notes for the chief executive in under 120 words. ...",
  "reference": { "checklist": ["Says the pick rate fell after the new scanners",
                               "Gives the decision to hire two temporary pickers for four weeks"] } }
```

A reference may also be a plain list of items, or `{"checklist": [...], "reference": "an
example of a good answer"}`.

**Writing good items.** Make each item one thing a reader could check: "Mentions the 90-day
termination right", not "Is accurate and complete". Avoid items that depend on taste, such as
"Is well written"; the judge will apply them inconsistently. Run `trialmark judge-check` (see
below) before relying on the results.

**Configuration.**

```json
"scorers": [{ "name": "checklist", "options": {
  "model": "claude-opus-5-5", "pricing": { "input": 4, "output": 20 },
  "checklist": ["Is under 120 words", "States nothing that is not in the notes", "Is written in plain English"] } }]
```

**Starter:** `trialmark init summarisation`.

---

## Calculating figures

**What it is.** A model works out a number: a price, a total, a date difference, a figure from
a document.

**How it is marked.** No judge is needed. The `number` scorer reads the number from the answer
and compares it with the right one. Its metric is `correct`.

- **Let the model show its working,** and ask it to end with a fixed final line such as
  `Answer: 96.50`. With the option `"marker": "Answer:"`, the scorer reads the number after the
  last "Answer:". Asking for "the number only" is fragile: some models show their working
  anyway, and the first number in the working is not the answer.
- `tolerance` allows a relative difference (`0.005` is 0.5%), and `absolute` an absolute one.

**Your test cases.** A CSV file whose reference is the number:

```csv
id,input,reference,tags
c3,What do 12 chairs cost before VAT after the volume discount?,3422.40,two-step
```

**Configuration.**

```json
"scorers": [{ "name": "number", "options": { "tolerance": 0.005, "marker": "Answer:" } }]
```

**Starter:** `trialmark init calculation`.

---

## Structured output

**What it is.** Any task whose answer must be JSON of a given shape, so other software can use
it.

**How it is marked.** The `json-schema` scorer checks the answer parses as JSON (a ```json
fence around it is allowed) and matches your JSON Schema. Its metrics are `valid_json` and
`matches_schema`. Pair it with `fields` to check the values as well as the shape. A pass mark
floor such as `"floors": {"matches_schema": 1.0}` rejects any model that ever returns the wrong
shape.

**Starter:** the `extraction` starter uses it.

---

## Testing your own system rather than a bare model

If your app does more than call a model, for example retrieving passages from your own search
index first, or calling tools, test the app itself. Write a Python function that takes the
model's name, the input and the model's settings, calls your app, and returns the answer:

```python
# my_system.py
from trialmark import RunOutput

def answer(model_id, case_input, settings):
    reply = my_app.ask(case_input, model=model_id)        # your code
    return RunOutput(output=reply.text, cost_usd=reply.cost)
```

```json
"models": [{ "id": "claude-sonnet-5-5", "runner": "python", "settings": { "callable": "my_system.py:answer" } }]
```

Any scorer above then marks your system's answers. Trialmark cannot know what your function
costs, so a run asks for `--yes`.

---

## Checking the judge

The `judge` and `checklist` scorers use a model to mark answers, and a judge can be wrong.
Before relying on one, check it against your own marks:

```bash
trialmark judge-check sample record.json --test-set questions.csv   # writes grades.csv
# fill in your_verdict (correct, partial or incorrect) without looking at the judge's marks
trialmark judge-check score record.json grades.csv
```

It reports how often the judge agreed with you and lists each disagreement. Choose a judge that
is not one of the models under test, since a judge can favour its own answers.

---

## Not yet supported

- **Conversations and agents.** Each case today is one input and one output. Multi-turn
  conversations, and checking which tools an agent called and in what order, need changes to
  the test set format and are not built.
- **Images and audio.** Inputs are text, or anything your own function in the `python` runner
  can turn into a model call.

If you need one of these, [open an issue](https://github.com/peshwar9/trialmark/issues).
