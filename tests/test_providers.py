"""The model runners and the judge, against stand-in clients, so no API key or
network is needed."""

import json
from types import SimpleNamespace as NS

import pytest

from trialmark import ModelEntry, PassMark, decision, make_runner, make_scorer, parse_test_set, run_trial
from trialmark.providers import NO_PRICING


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class FakeAnthropic:
    def __init__(self, reply="an answer", stop_reason="end_turn", usage=(100, 20, 0, 0)):
        self.calls = []
        self.reply, self.stop_reason, self.usage = reply, stop_reason, usage
        self.messages = self

    def stream(self, **params):
        self.calls.append(params)
        reply = self.reply(params) if callable(self.reply) else self.reply
        i, o, cr, cw = self.usage
        return FakeStream(NS(
            content=[NS(type="thinking", thinking=""), NS(type="text", text=reply)],
            stop_reason=self.stop_reason,
            stop_details=NS(category="cyber") if self.stop_reason == "refusal" else None,
            usage=NS(input_tokens=i, output_tokens=o, cache_read_input_tokens=cr, cache_creation_input_tokens=cw),
        ))


class FakeOpenAI:
    def __init__(self, reply="an answer", usage=(100, 20, 40), status="completed"):
        self.calls = []
        self.reply, self.usage, self.status = reply, usage, status
        self.responses = self

    def create(self, **params):
        self.calls.append(params)
        reply = self.reply(params) if callable(self.reply) else self.reply
        i, o, cached = self.usage
        return NS(output_text=reply, status=self.status, incomplete_details=NS(reason="max_output_tokens"),
                  usage=NS(input_tokens=i, output_tokens=o, input_tokens_details=NS(cached_tokens=cached)))


def case(input="What is the notice period?", reference="Sixty days."):
    return parse_test_set({"name": "t", "version": "1", "cases": [{"id": "a", "input": input, "reference": reference}]}).cases[0]


PRICES = {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5}


def test_anthropic_runner_request_and_cost(tmp_path):
    (tmp_path / "contract.md").write_text("The notice period is sixty days.")
    client = FakeAnthropic(usage=(100, 20, 1000, 0))
    runner = make_runner("anthropic", {"client": client}, base_dir=tmp_path)
    model = ModelEntry(id="claude-sonnet-5-5", settings={
        "documents": ["contract.md"], "system": "Answer briefly.", "effort": "low", "pricing": PRICES})
    out = runner.run(model, case())
    p = client.calls[0]
    assert p["model"] == "claude-sonnet-5-5" and p["max_tokens"] == 16000
    assert "temperature" not in p
    assert p["output_config"] == {"effort": "low"}
    assert p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "sixty days" in p["system"][0]["text"] and p["system"][1]["text"] == "Answer briefly."
    assert out.output == "an answer" and out.error is None and out.note == ""
    assert out.cost_usd == pytest.approx((100 * 2 + 20 * 10 + 1000 * 0.2) / 1e6)
    assert out.input_tokens == 1100


def test_anthropic_runner_reports_refusals_and_missing_prices():
    runner = make_runner("anthropic", {"client": FakeAnthropic(stop_reason="refusal")})
    out = runner.run(ModelEntry(id="m"), case())
    assert "declined" in out.error and "cyber" in out.error
    assert out.cost_usd == 0 and out.note == NO_PRICING
    cut = make_runner("anthropic", {"client": FakeAnthropic(stop_reason="max_tokens")}).run(ModelEntry(id="m"), case())
    assert "max_tokens" in cut.error


def test_openai_runner_request_and_cost():
    client = FakeOpenAI(usage=(1000, 20, 400))
    runner = make_runner("openai", {"client": client})
    out = runner.run(ModelEntry(id="gpt-x", settings={"system": "Be brief.", "pricing": PRICES}), case())
    p = client.calls[0]
    assert p["instructions"] == "Be brief." and p["input"] == "What is the notice period?"
    assert out.cost_usd == pytest.approx((600 * 2 + 20 * 10 + 400 * 0.2) / 1e6)
    incomplete = make_runner("openai", {"client": FakeOpenAI(status="incomplete")}).run(ModelEntry(id="m"), case())
    assert "incomplete" in incomplete.error


def verdict(v, grounded=True, declined=False):
    return json.dumps({"verdict": v, "grounded": grounded, "declined": declined, "note": f"judged {v}"})


def test_judge_with_documents(tmp_path):
    (tmp_path / "contract.md").write_text("The notice period is sixty days.")
    client = FakeAnthropic(reply=verdict("partial"))
    judge = make_scorer("judge", {"model": "judge-model", "documents": ["contract.md"], "client": client}, base_dir=tmp_path)
    assert judge.metrics == ("correct", "partial", "declined", "grounded")
    got = judge.score(case(), "Sixty days, I think.")
    assert got == {"correct": 0.0, "partial": 1.0, "declined": 0.0, "grounded": 1.0, "note": "judged partial"}
    p = client.calls[0]
    assert p["output_config"]["format"]["type"] == "json_schema"
    assert p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "REFERENCE:\nSixty days." in p["messages"][0]["content"]
    assert judge.judge["model"] == "judge-model" and judge.judge["documents"] == ["contract.md"]
    assert judge.judge["rules_hash"].startswith("jcs-sha256:")


def test_judge_without_documents_has_no_grounded_metric():
    judge = make_scorer("judge", {"model": "j", "client": FakeAnthropic(reply=verdict("correct", declined=True))})
    assert "grounded" not in judge.metrics
    assert "grounded" not in judge.schema["properties"]
    # A correct answer that mentions missing information is not a decline.
    assert judge.score(case(), "x")["declined"] == 0.0


def test_judge_refusal_and_bad_json_score_zero():
    refused = make_scorer("judge", {"model": "j", "client": FakeAnthropic(stop_reason="refusal")})
    got = refused.score(case(), "x")
    assert got["correct"] == 0.0 and "declined to grade" in got["note"]
    garbled = make_scorer("judge", {"model": "j", "client": FakeAnthropic(reply="not json")})
    assert "not valid JSON" in garbled.score(case(), "x")["note"]


def test_judge_through_openai_and_custom_rules(tmp_path):
    (tmp_path / "rules.txt").write_text("Grade strictly.")
    client = FakeOpenAI(reply=json.dumps({"verdict": "correct", "declined": False, "note": "ok"}))
    judge = make_scorer("judge", {"model": "j", "provider": "openai", "rules_file": "rules.txt", "client": client},
                        base_dir=tmp_path)
    assert judge.score(case(), "Sixty days.")["correct"] == 1.0
    p = client.calls[0]
    assert p["instructions"] == "Grade strictly."
    assert p["text"]["format"]["strict"] is True


def test_judge_needs_a_model():
    with pytest.raises(ValueError, match="'model'"):
        make_scorer("judge", {"client": FakeAnthropic()})


def test_a_full_trial_with_runner_and_judge():
    ts = parse_test_set({"name": "t", "version": "1", "cases": [
        {"id": "a", "input": "Q1", "reference": "R1", "tags": ["factual"]},
        {"id": "b", "input": "Q2", "reference": "R2", "tags": ["multi-part"]},
    ]})
    answers = FakeAnthropic(reply=lambda p: "good" if p["model"] == "big" or p["messages"][0]["content"] == "Q1" else "weak")
    grades = FakeAnthropic(reply=lambda p: verdict("correct" if "ANSWER:\ngood" in p["messages"][0]["content"] else "partial"))
    record = run_trial(
        ts, PassMark(metric="correct", tolerance_points=10),
        [ModelEntry(id="big", runner="anthropic", settings={"pricing": PRICES}),
         ModelEntry(id="small", runner="anthropic", settings={"pricing": {"input": 0.1, "output": 0.5}})],
        runners={"anthropic": make_runner("anthropic", {"client": answers})},
        scorers=[make_scorer("judge", {"model": "judge-model", "client": grades})],
        repeats=2, concurrency=4,
    )
    d = decision(record)
    assert d.chosen == "big"
    assert record.judge["model"] == "judge-model"
    small = [r for r in record.results if r.model == "small" and r.case_id == "b"]
    assert all(r.metrics["partial"] == 1.0 and r.note == "judged partial" for r in small)
