# Deployment: where Trialmark runs and what it needs

Trialmark is a Python package with a command-line tool. It is not a service: there is no server
to keep running, no database and no account. A test starts, calls the models, writes its record
and finishes. Everything it produces is files.

So for most teams, deploying Trialmark means installing it where tests should run. What else you
need depends on the models you test, not on Trialmark.

## Where Trialmark runs

| Where | Use it for | What it takes |
|---|---|---|
| **A laptop** | Trying models, writing and refining test sets, one-off decisions | `pip install trialmark` and an API key |
| **A build pipeline** (GitHub Actions, GitLab CI and others) | Refusing a model or prompt change that fails the pass mark | The key as a pipeline secret, and `trialmark gate` as a step |
| **A scheduled job** (a scheduled workflow, cron) | Rerunning the same test when a provider releases a model, or monthly, to catch a model getting worse | The same as a pipeline, on a timer, keeping each run's record |
| **Your own servers** | Testing models you run yourself, or keeping every case and answer inside your network | Python 3.10 or later; the machines your models run on |

## What a test reads and writes

| | Where it lives | Notes |
|---|---|---|
| **Reads:** the configuration, test set and any documents | Files beside the configuration | Keep them in version control, so every run can be traced to the cases it used |
| **Reads:** API keys | Environment variables such as `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`, read by each provider's SDK | Trialmark never writes a key to a record or a report |
| **Calls:** the models | The provider's API, or your own model through the `python` runner | Every case's input is sent to the model, so the provider's terms for your data apply |
| **Writes:** the run record | One JSON file, named in the configuration | Holds every answer; store it where the test set is allowed to be stored |
| **Writes:** reports | The terminal, or files you redirect it to | Text, Markdown or JSON |

## Do you need servers or storage?

Usually not. Whether you need any infrastructure depends on two things, not on the type of
model:

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
writes to while it runs. [Which models](models.md) says which of these Trialmark can mark today.

## In a build pipeline

A GitHub Actions job that fails when a model change does not meet the pass mark:

```yaml
name: model-acceptance
on:
  pull_request:
    paths: ["prompts/**", "trialmark/**"]
jobs:
  acceptance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "trialmark[anthropic]"
      - run: trialmark run trialmark/config.json --yes --output record.json
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - run: trialmark gate record.json --model claude-haiku-5-5 --test-set trialmark/questions.csv
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: trialmark-record
          path: record.json
```

- **Run it only when something relevant changes,** as the `paths` filter does here: every run
  calls the models and costs money. `trialmark run config.json` without `--yes` shows the cost
  of a run.
- **Keep the record.** Uploading it, as the last step does, means every decision can be checked
  later.
- **Gate on the model you intend to ship,** and pass `--test-set` so the gate also fails if the
  test set was changed.

For a scheduled rerun, replace the trigger with a schedule, for example
`on: { schedule: [{ cron: "0 6 1 * *" }] }` for the first of each month.

## Keeping everything inside your network

Trialmark sends nothing anywhere except to the models you configure. To keep every case and
answer inside your network, run Trialmark on your own servers and test models that also run
there, through the `python` runner. Use a judge model you also host, or the scorers that need no
judge (`fields`, `label`, `number`, `json-schema`, `exact-match`).
