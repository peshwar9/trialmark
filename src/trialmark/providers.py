"""Runners that call models directly, and the reference-answer judge.

Each needs its provider's SDK, installed as an extra:

    pip install "trialmark[anthropic]"    pip install "trialmark[openai]"

The SDK is imported only when the plugin is constructed, so the core keeps no
dependencies. Credentials come from the environment, as each SDK reads them
(ANTHROPIC_API_KEY, OPENAI_API_KEY and so on). Trialmark never stores them.

Prices change, so Trialmark ships no price list. Give each model its prices, in
US dollars per million tokens, under the model's "pricing" setting:

    "pricing": {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5}

A model without prices reports a cost of zero, and each of its results carries
a note saying so. The judge takes the same "pricing" option, so its spend is
recorded too.

Before a run, `trialmark run` estimates the cost from the size of the documents,
instructions and questions, at about four characters a token, and an expected
answer length ("expected_output_tokens", 400 by default; the judge assumes 500,
since it thinks before it grades). It errs on the high side, by two to three times
on the starters; the record holds what was actually spent.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .plugins import RunOutput, builtin
from .record import ModelEntry
from .testset import Case

NO_PRICING = "No pricing in the model's settings, so the cost is reported as zero."


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _read(paths: list[str] | str | None, base_dir: Path | None) -> list[tuple[str, str]]:
    if not paths:
        return []
    if isinstance(paths, str):
        paths = [paths]
    out = []
    for p in paths:
        path = Path(p)
        if not path.is_absolute() and base_dir is not None:
            path = base_dir / path
        out.append((Path(p).name, path.read_text(encoding="utf-8")))
    return out


def _documents_block(docs: list[tuple[str, str]]) -> str:
    return "\n\n".join(f'<document name="{name}">\n{text}\n</document>' for name, text in docs)


def _cost(pricing: dict[str, float] | None, input_tokens: int, output_tokens: int,
          cache_read: int = 0, cache_write: int = 0) -> float:
    if not pricing:
        return 0.0
    p_in = float(pricing.get("input", 0))
    return (
        input_tokens * p_in
        + output_tokens * float(pricing.get("output", 0))
        + cache_read * float(pricing.get("cache_read", p_in))
        + cache_write * float(pricing.get("cache_write", p_in))
    ) / 1e6


def _tokens(text: str) -> float:
    return len(text) / 4


def _estimate(pricing: dict[str, float] | None, cached_tokens: float, fresh_tokens: float,
              output_tokens: float) -> float | None:
    """A rough cost for one call: cached text at the cache price, the rest at the input price."""
    if not pricing:
        return None
    p_in = float(pricing.get("input", 0))
    return (
        cached_tokens * float(pricing.get("cache_read", p_in))
        + fresh_tokens * p_in
        + output_tokens * float(pricing.get("output", 0))
    ) / 1e6


def _system_text(settings: dict[str, Any], base_dir: Path | None) -> str:
    parts = []
    if settings.get("system_file"):
        parts.append(_read(settings["system_file"], base_dir)[0][1])
    if settings.get("system"):
        parts.append(str(settings["system"]))
    return "\n\n".join(parts)


# --- Clients --------------------------------------------------------------------


def _anthropic_client(who: str) -> Any:
    try:
        import anthropic
    except ImportError:
        raise ValueError(f'The {who} needs the Anthropic SDK: pip install "trialmark[anthropic]"') from None
    try:
        return anthropic.Anthropic()
    except Exception as e:  # the SDK's error when no credentials are found
        raise ValueError(f"The {who} could not create an Anthropic client: {e} Set ANTHROPIC_API_KEY.") from None


def _openai_client(who: str) -> Any:
    try:
        import openai
    except ImportError:
        raise ValueError(f'The {who} needs the OpenAI SDK: pip install "trialmark[openai]"') from None
    try:
        return openai.OpenAI()
    except Exception as e:  # the SDK's error when no key is found
        raise ValueError(f"The {who} could not create an OpenAI client: {e} Set OPENAI_API_KEY.") from None


# --- Runners --------------------------------------------------------------------


@builtin("runner", "anthropic")
class AnthropicRunner:
    """Calls a Claude model through the Anthropic SDK.

    Model settings:
      max_tokens: the output limit (default 16000). Calls are streamed, so large
                  limits do not time out.
      system, system_file: instructions, as text or from a file.
      documents: files placed in the system prompt, and cached, for a test that
                 gives the model whole documents rather than retrieved passages.
      effort: low, medium, high, xhigh or max, for models that support it.
      pricing: see the module's description.
      extra: any other request fields, passed through unchanged.

    Runner options:
      client: an Anthropic client to use, instead of one built from the environment.
    """

    def __init__(self, client: Any = None, base_dir: Path | None = None) -> None:
        # The client is made when the run starts (prepare), so a cost estimate
        # works before the SDK or a key is set up.
        self.client = client
        self.base_dir = base_dir

    def prepare(self) -> None:
        if self.client is None:
            self.client = _anthropic_client("anthropic runner")

    def estimate_cost(self, model: ModelEntry, case: Case) -> float | None:
        s = model.settings
        docs = _documents_block(_read(s.get("documents"), self.base_dir))
        fresh = _tokens(_system_text(s, self.base_dir)) + _tokens(_text(case.input))
        return _estimate(s.get("pricing"), _tokens(docs), fresh, float(s.get("expected_output_tokens", 400)))

    def run(self, model: ModelEntry, case: Case) -> RunOutput:
        s = model.settings
        system = []
        docs = _read(s.get("documents"), self.base_dir)
        if docs:
            system.append({"type": "text", "text": _documents_block(docs), "cache_control": {"type": "ephemeral"}})
        instructions = _system_text(s, self.base_dir)
        if instructions:
            system.append({"type": "text", "text": instructions})
        params: dict[str, Any] = {
            "model": model.id,
            "max_tokens": int(s.get("max_tokens", 16000)),
            "messages": [{"role": "user", "content": _text(case.input)}],
        }
        if system:
            params["system"] = system
        if s.get("effort"):
            params["output_config"] = {"effort": s["effort"]}
        params.update(s.get("extra", {}))
        self.prepare()
        with self.client.messages.stream(**params) as stream:
            message = stream.get_final_message()
        u = message.usage
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
        text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
        error = None
        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            error = f"The model declined the request ({getattr(details, 'category', None) or 'no category'})."
        elif message.stop_reason == "max_tokens":
            error = "The answer was cut off at max_tokens."
        return RunOutput(
            output=text,
            cost_usd=_cost(s.get("pricing"), u.input_tokens, u.output_tokens, cache_read, cache_write),
            input_tokens=u.input_tokens + cache_read + cache_write,
            output_tokens=u.output_tokens,
            error=error,
            note="" if s.get("pricing") else NO_PRICING,
        )


@builtin("runner", "openai")
class OpenAIRunner:
    """Calls an OpenAI model through the OpenAI SDK's Responses API.

    Model settings:
      max_tokens: the output limit (default 16000).
      system, system_file: instructions, as text or from a file.
      documents: files placed in the instructions, for a whole-documents test.
      pricing: see the module's description ("cache_read" is the price of cached input).
      extra: any other request fields, passed through unchanged.

    Runner options:
      client: an OpenAI client to use, instead of one built from the environment.
    """

    def __init__(self, client: Any = None, base_dir: Path | None = None) -> None:
        # Made when the run starts (prepare), as for the anthropic runner.
        self.client = client
        self.base_dir = base_dir

    def prepare(self) -> None:
        if self.client is None:
            self.client = _openai_client("openai runner")

    def estimate_cost(self, model: ModelEntry, case: Case) -> float | None:
        s = model.settings
        docs = _documents_block(_read(s.get("documents"), self.base_dir))
        fresh = _tokens(_system_text(s, self.base_dir)) + _tokens(_text(case.input))
        return _estimate(s.get("pricing"), _tokens(docs), fresh, float(s.get("expected_output_tokens", 400)))

    def run(self, model: ModelEntry, case: Case) -> RunOutput:
        s = model.settings
        parts = []
        docs = _read(s.get("documents"), self.base_dir)
        if docs:
            parts.append(_documents_block(docs))
        instructions = _system_text(s, self.base_dir)
        if instructions:
            parts.append(instructions)
        params: dict[str, Any] = {
            "model": model.id,
            "input": _text(case.input),
            "max_output_tokens": int(s.get("max_tokens", 16000)),
        }
        if parts:
            params["instructions"] = "\n\n".join(parts)
        params.update(s.get("extra", {}))
        self.prepare()
        response = self.client.responses.create(**params)
        u = response.usage
        cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
        error = None
        if getattr(response, "status", "completed") == "incomplete":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
            error = f"The answer is incomplete ({reason or 'no reason given'})."
        return RunOutput(
            output=response.output_text,
            # OpenAI counts cached tokens inside input_tokens.
            cost_usd=_cost(s.get("pricing"), u.input_tokens - cached, u.output_tokens, cached, 0),
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            error=error,
            note="" if s.get("pricing") else NO_PRICING,
        )


# --- The reference-answer judge --------------------------------------------------

JUDGE_RULES = """You grade answers against reference answers written by a person.

For each item you receive a QUESTION, the REFERENCE answer and the ANSWER being graded.
{documents_line}

verdict:
- "correct": the answer contains every essential fact in the reference and nothing that
  contradicts it{or_documents}. Wording, order and extra correct detail do not matter.
- "partial": the answer is right as far as it goes but leaves out an essential part of the
  reference, such as one of two conditions or the exceptions to a rule.
- "incorrect": the answer is wrong, contradicts the reference{or_documents}, or declines a
  question the reference answers.
- When the reference says the answer is not available, "correct" means the answer says so
  (it may mention related facts); inventing an answer is "incorrect".
{grounded_rule}
declined: true if the answer says it does not have the information or cannot answer.

note: one short sentence explaining the verdict.

Masked placeholders such as [PERSON_1] or [EMAIL_2] in the answer are expected and are not
errors."""

GROUNDED_RULE = """
grounded: true if every factual claim in the answer is supported by the source documents. A
correct decline is grounded.
"""


def judge_rules(with_documents: bool) -> str:
    return JUDGE_RULES.format(
        documents_line="The source documents are given above." if with_documents else "",
        or_documents=" or the documents" if with_documents else "",
        grounded_rule=GROUNDED_RULE if with_documents else "",
    )


def _verdict_schema(with_documents: bool) -> dict[str, Any]:
    props: dict[str, Any] = {
        "verdict": {"type": "string", "enum": ["correct", "partial", "incorrect"]},
        "declined": {"type": "boolean"},
        "note": {"type": "string"},
    }
    if with_documents:
        props["grounded"] = {"type": "boolean"}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


@builtin("scorer", "judge")
class ReferenceJudge:
    """Grades a free-text answer against the reference with a language model.

    Metrics:
      correct: 1 for a correct answer, else 0.
      partial: 1 for a partly correct answer, else 0.
      declined: 1 if the answer declined and was not correct, else 0.
      grounded: 1 if every claim is supported by the source documents (only when
                documents are given).

    Options:
      model: the judge model (required). Choose one that is not under test, or
             check the judge against a person's grades on part of the set.
      provider: "anthropic" (default) or "openai".
      documents: source documents for judging groundedness.
      rules_file: your own grading rules, replacing the built-in ones. The record
                  stores a hash of the rules in use.
      max_tokens: the judge's output limit (default 16000).
      pricing: the judge model's prices, as for a runner's model, so its spend is
               estimated before the run and recorded after it.
      client: a client to use, instead of one built from the environment.
    """

    costs_money = True

    def __init__(
        self,
        model: str | None = None,
        provider: str = "anthropic",
        documents: list[str] | str | None = None,
        rules_file: str | None = None,
        max_tokens: int = 16000,
        pricing: dict[str, float] | None = None,
        client: Any = None,
        base_dir: Path | None = None,
    ) -> None:
        if not model:
            raise ValueError("The judge scorer needs a 'model' option.")
        if provider not in ("anthropic", "openai"):
            raise ValueError("The judge's provider must be 'anthropic' or 'openai'.")
        self.model, self.provider, self.max_tokens = model, provider, int(max_tokens)
        self.pricing = pricing
        # What the judge spent, summed across threads and written to the record.
        self._lock = threading.Lock()
        self.spent = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0 if pricing else None}
        docs = _read(documents, base_dir)
        self.documents = _documents_block(docs)
        self.rules = _read(rules_file, base_dir)[0][1] if rules_file else judge_rules(bool(docs))
        self.schema = _verdict_schema(bool(docs))
        self.metrics = ("correct", "partial", "declined", *(("grounded",) if docs else ()))
        from .canonical import digest

        # What the record shows about the judge, so a reader knows how answers were graded.
        self.judge = {
            "model": model,
            "provider": provider,
            "rules_hash": digest(self.rules),
            "documents": [name for name, _ in docs],
        }
        self.client = client

    def prepare(self) -> None:
        if self.client is None:
            make = _anthropic_client if self.provider == "anthropic" else _openai_client
            self.client = make("judge")

    def _ask(self, prompt: str) -> tuple[dict[str, Any] | None, str]:
        self.prepare()
        if self.provider == "anthropic":
            system = []
            if self.documents:
                # The documents are the same for every judgment, so they are cached.
                system.append({"type": "text", "text": f"SOURCE DOCUMENTS:\n\n{self.documents}",
                               "cache_control": {"type": "ephemeral"}})
            system.append({"type": "text", "text": self.rules})
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": self.schema}},
            ) as stream:
                message = stream.get_final_message()
            u = message.usage
            cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
            cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
            self._add(u.input_tokens + cache_read + cache_write, u.output_tokens,
                      _cost(self.pricing, u.input_tokens, u.output_tokens, cache_read, cache_write))
            if message.stop_reason == "refusal":
                return None, "The judge declined to grade this answer."
            text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
        else:
            instructions = (f"SOURCE DOCUMENTS:\n\n{self.documents}\n\n" if self.documents else "") + self.rules
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=prompt,
                max_output_tokens=self.max_tokens,
                text={"format": {"type": "json_schema", "name": "verdict", "schema": self.schema, "strict": True}},
            )
            u = response.usage
            cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
            self._add(u.input_tokens, u.output_tokens, _cost(self.pricing, u.input_tokens - cached, u.output_tokens, cached, 0))
            text = response.output_text
        try:
            return json.loads(text), ""
        except json.JSONDecodeError:
            return None, "The judge's reply was not valid JSON."

    def _add(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        with self._lock:
            self.spent["calls"] += 1
            self.spent["input_tokens"] += int(input_tokens)
            self.spent["output_tokens"] += int(output_tokens)
            if self.spent["cost_usd"] is not None:
                self.spent["cost_usd"] += cost

    def estimate_cost(self, case: Case) -> float | None:
        """A rough cost of grading one answer to this case."""
        fresh = _tokens(self.rules) + _tokens(_text(case.input)) + _tokens(_text(case.reference)) + 400
        return _estimate(self.pricing, _tokens(self.documents), fresh, 500)

    def score(self, case: Case, output: Any) -> dict[str, Any]:
        prompt = f"QUESTION:\n{_text(case.input)}\n\nREFERENCE:\n{_text(case.reference)}\n\nANSWER:\n{_text(output)}"
        v, problem = self._ask(prompt)
        if v is None:
            return {**{m: 0.0 for m in self.metrics}, "note": problem}
        verdict = v.get("verdict")
        scores: dict[str, Any] = {
            "correct": 1.0 if verdict == "correct" else 0.0,
            "partial": 1.0 if verdict == "partial" else 0.0,
            # A correct answer that mentions something missing is not a decline.
            "declined": 1.0 if v.get("declined") and verdict != "correct" else 0.0,
            "note": str(v.get("note", "")),
        }
        if "grounded" in self.metrics:
            scores["grounded"] = 1.0 if v.get("grounded") else 0.0
        return scores
