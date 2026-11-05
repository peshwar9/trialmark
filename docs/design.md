# What makes Trialmark different

Trialmark is built on a few deliberate decisions. Most of them borrow established practice from
experimental science and software testing; what is distinctive is applying them together to one
question: *which model should we ship for this task, and can we show how we decided?* This page
sets out each decision, why it was made, and what is not new about it.

## 1. The decision is registered before the results exist

Clinical trials register how they will judge their results before the trial starts, so nobody can
move the goalposts once the data is in. Trialmark does the same for choosing a model.

- **The pass mark is written in the configuration** and stored in the run record, with its
  fingerprint and the time it was set, before any model is called.
- **The rule chooses between models,** rather than passing or failing each test on its own. For
  example: "choose the cheapest model within 3 points of the best on correct answers, with at least
  95% of its answers grounded in the documents". The rule has four parts: the metric that decides,
  how many points below the best still pass, floors on other metrics, and whether to choose the
  cheapest, the fastest or the best of the models that pass.
- **The decision is computed, not read off a chart.** `trialmark report` names the model chosen,
  and `trialmark gate` turns it into a pass or a fail that a build pipeline can enforce.

Most evaluation tools produce scores and leave the choice to whoever reads them, after they have
seen them. Some let you set a threshold per test. Few treat "which model do we ship?" as the thing
to encode in advance.

## 2. One decision method for every task; only the marking changes

Trialmark has two layers, and the line between them is the main architectural decision.

| Layer | What it holds | Who changes it |
|---|---|---|
| **The fixed core** | The test-set format and its fingerprint, the pass mark and the decision rule, repeats and ranges, the run record, the cost estimate and the gate | Nobody, per task or per model. This is what makes any two runs comparable. |
| **Plugins** | **Runners** (how to call a model), **scorers** (how to mark an output), **loaders** (how to read test cases) and **report writers** | Anyone, by installing a package, without forking Trialmark |

**Why it works.** Every scorer reduces its judgement to numbers between 0 and 1, whatever the task:
a judge grades an answer correct or not, the fields scorer gives the share of fields right, a word
error rate scorer gives word accuracy. Because every result lands on the same scale, the same
decision rule, the same repeats, the same gate and the same record serve every kind of task and
every kind of model.

**What that gives you:**

1. **One method for every task.** Extraction, classification, summarising, calculating and
   answering questions are all decided the same way, so a team learns one tool, not one per task.
2. **A new task or model is a plugin, not a new framework.** Supporting speech to text takes a
   runner and a scorer, about thirty lines between them ([models.md](models.md) has the example);
   the pass mark, repeats, cost tracking and gate come with it.
3. **No lock-in to a model provider.** Each provider is a runner. Claude, GPT and an open-weight
   model you run yourself can be compared in one run, under one rule.
4. **The trust does not depend on the plugin.** Fingerprinting, the pass mark and the record live in
   the core, so a scorer someone else wrote cannot weaken them. The record names every plugin and
   its version, and an installed plugin cannot take the name of a built-in one.

Plugin architectures are common; pytest has plugins, and promptfoo has providers and assertions.
What is distinctive is which part is held fixed: the decision layer is the same for every task.

## 3. Practice from experimental work, built in

| What Trialmark does | The practice behind it |
|---|---|
| Every model answers every case several times, and the report shows the lowest and highest repeat. A difference inside the range is treated as no difference. | Repeated measurement, and reporting the spread rather than one number |
| Results are broken down by the tags on each case, such as "simple fact" or "needs several parts" | Stratified analysis: the reason trials report results by subgroup. A cheap model is often as good as an expensive one on easy cases and worse on hard ones |
| A model with any failed call cannot pass | Incomplete results count as a failure, not as an average of what came back |
| `judge-check` has a person mark a sample of answers without seeing the AI judge's grades, then reports how often they agreed | Blind marking, and measuring agreement between two graders before trusting one |
| A run on part of a test set records the fingerprint of the part actually run | A partial run can never be mistaken for the full test |
| `trialmark run` prints the plan and an estimated cost, and calls no paid model until `--yes` | A dry run before committing resources |
| The judge's own spend is recorded beside the answers' cost | The full cost of a measurement, not only the part being measured |

## 4. A record built to be checked by someone else

A result is only as convincing as its record. Trialmark's is designed to be checked by a colleague,
an auditor or a customer, not only by the person who ran it.

| What | Standard or technique |
|---|---|
| **Fingerprints that any program reproduces** | SHA-256 over canonical JSON as defined by RFC 8785, so a program in any language that hashes the same test set or pass mark gets the same fingerprint. Checked against an independent TypeScript implementation on a 42-question test set. Fingerprints from versions before 0.3 are still checked. |
| **Formats any tool can validate** | JSON Schema (draft 2020-12) for the test set, the pass mark and the run record; `trialmark schema` prints each |
| **Everything needed to rerun** | The record holds the test set's fingerprint, each model's identifier and settings, the judge, its rules' fingerprint and the documents it read, the pass mark, the plugins and their versions, and every result with its cost, tokens and time |
| **A gate that checks the test set too** | `trialmark gate --test-set` fails if the run used a different test set from the one named |

**What a fingerprint does not do.** It catches any change to a test set or pass mark. It does not
stop someone changing both a pass mark and its fingerprint together, and it does not prove who ran
a test. Signed records, which would, are planned.

## 5. Engineering choices

| What | How |
|---|---|
| **Light to install** | The core has no dependencies. Each model provider's library, and `jsonschema`, is an optional extra, loaded only when used. |
| **Plugins without forking** | Python's standard entry points, the mechanism pytest uses |
| **Judge verdicts that always parse** | The providers' structured outputs, constrained to a schema |
| **A cheaper judge** | Prompt caching of the source documents across every grading call |
| **Estimates before keys** | Model clients are created when a run starts, so a cost estimate works before an SDK or a key is set up, and a missing one stops the run once with a clear message |
| **Runs on your own machines** | No service, no account and no hosted storage: a test reads files, calls the models you name and writes files. See [Deployment](deployment.md). |
| **A licence that suits companies** | Apache-2.0. Runners that wrap code under copyleft licences are meant to ship as separate packages, so users of the core never inherit those terms |

## What is not new

None of the parts is an invention on its own. Pre-registration comes from clinical trials,
repeated measurement and stratified analysis from experimental science, blind marking from
assessment, acceptance tests and pass-or-fail gates from software engineering, and canonical JSON,
SHA-256 and JSON Schema are published standards. Trialmark's contribution is putting them together,
in one tool with one decision method, for the everyday question of which AI model to ship.

**See also:** [ARCHITECTURE.md](../ARCHITECTURE.md) for how a run works and the plugin interfaces,
[What you can test](tasks.md) and [Which models](models.md).
