# Which models Trialmark can test

Trialmark does not care how a model is built. "Transformer", "language model" and "vision
model" describe a model's design or what it is good at; what Trialmark needs to know is simpler:
**how to call the model, and how to mark what it returns.** Calling is the job of a *runner*,
marking is the job of a *scorer*, and both are plugins (see [ARCHITECTURE.md](../ARCHITECTURE.md)).

So the practical question is what goes in and what comes out.

## Supported today

| What the model takes and returns | Examples | How Trialmark calls it | How it is marked |
|---|---|---|---|
| **Text in, text out, through Anthropic's API** | Any Claude model the API serves | The built-in `anthropic` runner | Any scorer for the task: judge, checklist, fields, label, number, JSON Schema |
| **Text in, text out, through OpenAI's API** | Any model OpenAI's Responses API serves | The built-in `openai` runner | As above |
| **Text in, text out, anywhere else** | Google Gemini, Mistral, Cohere, models on Amazon Bedrock or Azure, open-weight models such as Llama or Qwen run locally with Ollama, vLLM or Hugging Face Transformers, your fine-tuned models | The `python` runner: a short function that calls the model with its own SDK and returns the answer | As above |
| **Your own system built on models** | A retrieval pipeline, an app that calls several models, a single-turn agent | The `python` runner, calling your system | As above |
| **Classic machine-learning models with a text or number output** | A scikit-learn or fine-tuned text classifier, a model that predicts a number | The `python` runner | `label` (with `trialmark confusion`) for classes, `number` for predictions within a tolerance |

The `python` runner's function receives the model's name, the case's input and the model's
settings, and returns the output, or a `trialmark.RunOutput` with its cost and tokens:

```python
# my_model.py
from trialmark import RunOutput

def answer(model_id, case_input, settings):
    reply = my_client.generate(model=model_id, prompt=case_input)   # any SDK or local model
    return RunOutput(output=reply.text, cost_usd=reply.cost)
```

```json
"models": [{ "id": "llama-3.3-70b", "runner": "python", "settings": { "callable": "my_model.py:answer" } }]
```

A case's input can be any JSON value, not only text, so a function can take, for example, a
file path or a set of parameters and do whatever the model needs.

Whether testing a model needs servers or storage depends on where the model runs, not on its
type: see [Deployment](deployment.md).

## Not supported yet, and what each would need

The core (test sets, the pass mark, repeats, the record, the gate) stays the same for every kind
of model. A new kind needs a runner to call it, a scorer to mark its output, and sometimes a
loader to read its test cases.

| Kind of model | What works today | What is missing |
|---|---|---|
| **Speech to text** | A `python` runner returns the transcript; `exact-match` marks it, which is too strict for transcripts | A word error rate scorer |
| **Embedding and retrieval models** | A `python` runner can return the retrieved documents | Retrieval scorers such as recall at k and mean reciprocal rank |
| **Image, audio and video generation** | Nothing useful yet | A judge that can look at the output, and a record that can hold or point to it |
| **Conversations and agents that call tools** | Single-turn calls only | Test cases with several turns, and scorers for which tools were called and in what order |
| **Models that read images, audio or video and answer in text** (vision-language models, document readers) | A `python` runner can load the file named in a case's input, send it to the model and return its text answer; the text scorers then mark it | A built-in runner that sends files to Anthropic and OpenAI models, so no code is needed |
| **Detection, segmentation and tracking vision models** (they return boxes, masks or tracks) | A `python` runner can return the predictions as JSON | Scorers for precision, recall and mAP, and for tracking; a loader for labelled images; a compact store for large numbers of predictions; and speed and hardware measurements, which matter more for these models. Runners for code under copyleft licences would ship as separate packages, so the core stays Apache-2.0 |

## Adding a new kind of model

Supporting a new kind of model means writing plugins, not changing Trialmark. The core (test
sets, the pass mark, repeats, the record and the gate) works the same for every model. A new kind
of model needs up to three plugins:

| Plugin | Its job | For an image, audio or video model |
|---|---|---|
| **Loader** | Read your test cases from wherever they are kept | Turn a folder of files and their labels into cases. A case's input can be any JSON value, so it can hold a file path, or several, rather than the file itself |
| **Runner** | Call the model with one case's input and return its output | Open the file the case names, send it to the model, and return the output as JSON: a transcript, a list of boxes, a label |
| **Scorer** | Mark one output against the case's reference | Compute the measure that suits the output, such as word error rate for a transcript or precision and recall for boxes, as numbers between 0 and 1 |

Each is a small Python class or function with one method, and each can ship as its own package
that Trialmark finds once it is installed. [ARCHITECTURE.md](../ARCHITECTURE.md) gives the
interfaces, and the README's "Writing a plugin" section shows how a package declares them.

### A worked example: speech to text

A team testing transcription models keeps audio files and the correct transcripts in a folder.

**The cases.** A JSON test set whose inputs are file paths and whose references are the right
transcripts, so no loader is needed:

```json
{ "name": "calls", "version": "1", "cases": [
  { "id": "c1", "input": "audio/call-001.wav", "reference": "I'd like to change my delivery address.", "tags": ["clear"] },
  { "id": "c2", "input": "audio/call-002.wav", "reference": "My order number is four seven two nine.", "tags": ["noisy"] }
] }
```

**The runner.** A function for the `python` runner that sends the file to a speech model:

```python
# transcribe.py
from openai import OpenAI
from trialmark import RunOutput

client = OpenAI()

def transcribe(model_id, case_input, settings):
    with open(case_input, "rb") as f:
        result = client.audio.transcriptions.create(model=model_id, file=f)
    return RunOutput(output=result.text)
```

**The scorer.** Word error rate, wrapped so that 1 is a perfect transcript:

```python
# trialmark_wer/__init__.py
import jiwer

class WordAccuracy:
    metrics = ("word_accuracy",)

    def score(self, case, output):
        error = jiwer.wer(case.reference, output or "")
        return {"word_accuracy": max(0.0, 1.0 - error)}
```

Registered in its package's `pyproject.toml` under `[project.entry-points."trialmark.scorers"]`
as `word-accuracy = "trialmark_wer:WordAccuracy"`, it is used like any other scorer:
`"scorers": ["word-accuracy"]`, with a pass mark such as "the cheapest model within 2 points of
the best on word accuracy". Everything else, the repeats, the breakdown by tag (`clear` against
`noisy`), the cost and the gate, comes from Trialmark.

### Things to plan for

- **Large outputs.** The record keeps every output. For a model that returns thousands of boxes
  per image, have the runner write its predictions to a file and return the file's path, so the
  record stays small.
- **Large inputs.** Keep media files in shared storage and put their paths in the test set; see
  [Deployment](deployment.md).
- **Speed.** For a model you run yourself, have the runner report the time taken on the hardware
  you will deploy on, since that is often part of the decision.
- **Licences.** A runner that wraps code under a copyleft licence, such as GPL or AGPL, should
  ship as its own package, so Trialmark's core stays Apache-2.0 and its users do not inherit those
  terms.

If you need one of these, [open an issue](https://github.com/peshwar9/trialmark/issues), or write
the runner and scorer as plugins: [ARCHITECTURE.md](../ARCHITECTURE.md) and the README's
"Writing a plugin" section show how, and Trialmark finds an installed plugin without any change
to the core.

**See also:** [What you can test](tasks.md) for each kind of task and its scorer,
[Deployment](deployment.md) for what you need to set up, and the
[starters](../examples/starters) for ready-to-run examples.
