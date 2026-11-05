"""An example of the python runner: any function can stand in for a model.

A real one would call a model's API here and return a trialmark.RunOutput with
the cost and token counts."""

from trialmark import RunOutput


def answer(model_id, case_input, settings):
    # A deliberately poor "model" that only knows one fact.
    if "confidentiality" in case_input:
        return RunOutput(output="Three years after termination.", cost_usd=0.001)
    return RunOutput(output="I don't know.", cost_usd=0.001)
