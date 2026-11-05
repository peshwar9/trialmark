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

## Do you need servers to run a test?

Usually not. Trialmark itself is a Python package: a test starts, calls the models, writes its
record and finishes, with no server of its own. Whether you need any other infrastructure
depends on two things, not on the type of model:

1. **Where the model runs.** A model a provider hosts behind an API needs nothing from you. A
   model you run yourself needs machines that can run it, and if speed matters, the same
   hardware you will deploy on, because the same model runs at very different speeds on
   different hardware.
2. **How big the test data is.** A few thousand cases of text fit in a file. Hours of audio or
   video, or large image sets, need shared storage, and a run that makes millions of
   predictions needs somewhere compact to keep them.

This applies to language models as much as any other: a model called through an API needs
nothing, while an open-weight model on your own servers needs a GPU machine.

| Kind of model | Through a provider's API: no infrastructure | Run yourself: needs infrastructure | Test data |
|---|---|---|---|
| **Language models** | Claude, GPT, Gemini, Mistral | Llama, Qwen and others on your own GPU servers, with vLLM or Ollama | Text: small |
| **Classic machine-learning models** (scikit-learn classifiers, forecasting) | Rarely offered | Usually an ordinary laptop or server; small models need no GPU | Tables: small |
| **Embedding and reranking models** | Voyage, OpenAI, Cohere | Open models such as BGE on your own machines, often without a GPU | Text: small, plus a collection of documents to search |
| **Speech to text** | Whisper through Groq or OpenAI, and other speech APIs | Whisper or similar on your own GPUs | Audio: large |
| **Image, audio and video generation** | Generation APIs from several providers | Open models on large GPUs | The outputs are large |
| **Models that read images and answer in text** | Claude, GPT and Gemini read images through their APIs | Open-weight models such as Qwen-VL on GPUs | Images: medium |
| **Detection, segmentation and tracking models** | Rarely: a few cloud vision APIs | Almost always: GPUs or edge devices, tested on the hardware they will run on | Images and video: large |

So a team whose models are all reached through APIs needs only Trialmark, on a laptop or in its
build pipeline. A team that runs its own models needs compute to run them, and a team with large
media test sets needs storage. None of it runs all the time: these are what a test reads from and
writes to while it runs.

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

If you need one of these, [open an issue](https://github.com/peshwar9/trialmark/issues), or write
the runner and scorer as plugins: [ARCHITECTURE.md](../ARCHITECTURE.md) and the README's
"Writing a plugin" section show how, and Trialmark finds an installed plugin without any change
to the core.

**See also:** [What you can test](tasks.md) for each kind of task and its scorer, and the
[starters](../examples/starters) for ready-to-run examples.
