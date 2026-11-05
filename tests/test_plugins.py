import json
from pathlib import Path

import pytest

from trialmark import (
    ModelEntry,
    PassMark,
    RunOutput,
    decision,
    load_config,
    load_record,
    load_with,
    make_runner,
    make_scorer,
    parse_test_set,
    render,
    run_config,
    run_trial,
)
from trialmark import plugins
from trialmark.cli import main

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"


def tiny_set():
    return parse_test_set({"name": "t", "version": "1", "cases": [
        {"id": "a", "input": "Q one", "reference": "Answer One.", "tags": ["easy"]},
        {"id": "b", "input": "Q two", "reference": "answer two", "tags": ["hard"]},
    ]})


class FixedRunner:
    """A runner written in a test, passed directly without registering it."""

    def __init__(self, answers):
        self.answers = answers

    def run(self, model, case):
        return RunOutput(output=self.answers[model.id][case.id], cost_usd=0.01, latency_ms=5)


class BrokenRunner:
    def run(self, model, case):
        raise RuntimeError("provider unavailable")


def test_run_trial_with_objects_passed_directly():
    ts = tiny_set()
    runner = FixedRunner({"good": {"a": "answer one", "b": "Answer two!"}, "bad": {"a": "answer one", "b": "no"}})
    record = run_trial(
        ts, PassMark(metric="correct"),
        [ModelEntry(id="good", runner="fixed"), ModelEntry(id="bad", runner="fixed")],
        runners={"fixed": runner}, scorers=[make_scorer("exact-match")], repeats=2, concurrency=3,
    )
    assert len(record.results) == 8
    assert decision(record).chosen == "good"
    assert record.parsed_pass_mark().metric == "correct"


def test_failed_calls_are_recorded_and_scored_zero():
    record = run_trial(
        tiny_set(), PassMark(metric="correct"), [ModelEntry(id="m", runner="broken")],
        runners={"broken": BrokenRunner()}, scorers=[make_scorer("exact-match")], repeats=1,
    )
    assert all(r.error and "provider unavailable" in r.error for r in record.results)
    assert all(r.metrics == {"correct": 0.0} for r in record.results)
    d = decision(record)
    assert d.chosen is None
    assert "2 calls failed" in d.verdict_for("m").reasons


def test_scores_outside_zero_to_one_are_refused():
    class BadScorer:
        metrics = ("x",)

        def score(self, case, output):
            return {"x": 5}

    with pytest.raises(ValueError, match="between 0 and 1"):
        run_trial(tiny_set(), PassMark(metric="x"), [ModelEntry(id="m", runner="echo")],
                  runners={"echo": make_runner("echo")}, scorers=[BadScorer()], repeats=1)


def test_a_model_must_name_a_provided_runner():
    with pytest.raises(ValueError, match="was not provided"):
        run_trial(tiny_set(), PassMark(metric="correct"), [ModelEntry(id="m", runner="nope")],
                  runners={}, scorers=[make_scorer("exact-match")])


def test_echo_runner_settings():
    ts = tiny_set()
    echo = make_runner("echo")
    assert echo.run(ModelEntry(id="m"), ts.cases[0]).output == "Answer One."
    assert echo.run(ModelEntry(id="m", settings={"answer": "input"}), ts.cases[0]).output == "Q one"
    assert echo.run(ModelEntry(id="m", settings={"wrong_tags": ["easy"]}), ts.cases[0]).output == ""


def test_python_runner_from_a_file():
    runner = make_runner("python")
    model = ModelEntry(id="m", settings={"callable": str(EXAMPLES / "my_model.py") + ":answer"})
    case = parse_test_set({"name": "t", "version": "1", "cases": [
        {"id": "c", "input": "How long does confidentiality last?", "reference": ""}]}).cases[0]
    assert runner.run(model, case).output == "Three years after termination."
    with pytest.raises(ValueError, match="no 'callable'"):
        runner.run(ModelEntry(id="m"), case)


def test_exact_match_normalises_by_default():
    ts = tiny_set()
    s = make_scorer("exact-match")
    assert s.score(ts.cases[0], "  answer ONE ") == {"correct": 1.0}
    strict = make_scorer("exact-match", {"normalise": False})
    assert strict.score(ts.cases[0], "answer one") == {"correct": 0.0}


def test_field_scorer():
    case = parse_test_set({"name": "t", "version": "1", "cases": [
        {"id": "c", "input": "doc", "reference": {"term": "12 months", "notice": "30 days", "law": "India"}}]}).cases[0]
    s = make_scorer("fields")
    got = s.score(case, json.dumps({"term": "12 Months", "notice": "60 days", "law": "india"}))
    assert got["fields_correct"] == pytest.approx(2 / 3)
    assert got["all_fields_correct"] == 0.0
    assert s.score(case, "not json") == {"fields_correct": 0.0, "all_fields_correct": 0.0}


def test_csv_loader_matches_json(tmp_path):
    csv_path = tmp_path / "set.csv"
    csv_path.write_text("id,input,reference,tags\na,Q one,Answer One.,easy\nb,Q two,answer two,hard\n")
    assert load_with(csv_path).hash == tiny_set().hash
    with pytest.raises(ValueError, match="'reference' column"):
        bad = tmp_path / "bad.csv"
        bad.write_text("id,input\na,b\n")
        load_with(bad)


def test_unknown_plugins_list_what_exists():
    with pytest.raises(ValueError, match="Available: anthropic, echo, openai, python"):
        make_runner("nonexistent")


def test_a_plugin_cannot_replace_a_built_in(monkeypatch):
    class FakeDist:
        name = "trialmark-evil"
        version = "1"

    class FakeEP:
        name = "echo"
        value = "x:y"
        dist = FakeDist()

    monkeypatch.setattr(plugins, "_entry_points", lambda kind: {"echo": FakeEP()} if kind == "runner" else {})
    with pytest.raises(ValueError, match="name of a built-in runner"):
        make_runner("echo")


def test_installed_plugins_are_found(monkeypatch):
    class FakeDist:
        name = "trialmark-acme"
        version = "0.3"

    class FakeEP:
        name = "acme"
        value = "acme:Runner"
        dist = FakeDist()

        def load(self):
            return FixedRunner

    monkeypatch.setattr(plugins, "_entry_points", lambda kind: {"acme": FakeEP()} if kind == "runner" else {})
    assert isinstance(plugins.make_runner("acme", {"answers": {}}), FixedRunner)
    assert plugins.version_of("runner", "acme") == "trialmark-acme 0.3"
    assert ("acme", "trialmark-acme") in plugins.available()["runner"]


def test_config_run_and_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    config = load_config(EXAMPLES / "config.json")
    record = run_config(config)
    assert decision(record).chosen == "perfect-model"
    assert record.plugins["runners"]["echo"].startswith("trialmark ")
    path = tmp_path / "r.json"
    record.save(path)
    again = load_record(path)
    assert again.models[0].runner == "echo"
    md = render(again, "markdown", by_tag=True)
    assert "## Tag: multi-part" in md and "**Chosen:** perfect-model" in md
    assert json.loads(render(again, "json"))["chosen"] == "perfect-model"


def test_cli_run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "r.json"
    assert main(["run", str(EXAMPLES / "config.json"), "--output", str(out)]) == 0
    assert main(["gate", str(out), "--model", "perfect-model"]) == 0
    assert main(["gate", str(out), "--model", "weak-on-multi-part"]) == 1
    assert main(["plugins"]) == 0
    assert "Chosen     perfect-model" in capsys.readouterr().out


def test_records_from_version_0_1_still_load():
    data = json.loads((EXAMPLES / "run-record.json").read_text())
    for m in data["models"]:
        m.pop("runner", None)
    data.pop("plugins", None)
    from trialmark import parse_record

    record = parse_record(data)
    assert record.models[0].runner == "" and record.plugins == {}
    assert decision(record).chosen == "medium-model"
