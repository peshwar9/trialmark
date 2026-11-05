"""Trialmark 0.5: scorers for each kind of task, the confusion report, and a
starter for every task and provider."""

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from trialmark import ModelEntry, PassMark, load_config, make_runner, make_scorer, parse_test_set, run_trial
from trialmark.cli import main
from trialmark.confusion import confusion, confusion_report
from trialmark.estimate import estimate_run
from trialmark.scorers import numbers_in, parse_json_output, predicted_label
from trialmark.starters import PROVIDERS, TASKS, build

ROOT = Path(__file__).parent.parent


def case(reference, input="x", id="a", tags=()):
    return parse_test_set({"name": "t", "version": "1", "cases": [
        {"id": id, "input": input, "reference": reference, "tags": list(tags)}]}).cases[0]


# --- Starters ---------------------------------------------------------------------


@pytest.mark.parametrize("task", list(TASKS))
@pytest.mark.parametrize("provider", list(PROVIDERS))
def test_examples_match_what_init_writes(task, provider):
    folder = ROOT / "examples" / "starters" / f"{task}-{provider}"
    built = build(task, provider)
    assert sorted(p.name for p in folder.iterdir()) == sorted(built)
    for name, text in built.items():
        assert (folder / name).read_text() == text, f"examples/starters/{task}-{provider}/{name} is out of date"


@pytest.mark.parametrize("task", list(TASKS))
@pytest.mark.parametrize("provider", list(PROVIDERS))
def test_every_starter_estimates_without_a_key(task, provider, tmp_path, capsys, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    target = tmp_path / "s"
    assert main(["init", task, "--provider", provider, "--dir", str(target)]) == 0
    capsys.readouterr()
    assert main(["run", str(target / "config.json")]) == 0
    out = capsys.readouterr().out
    assert "Nothing run. Add --yes" in out and "unknown" not in out
    est = estimate_run(load_config(target / "config.json"))
    assert 0 < est.known_total < 6


@pytest.mark.parametrize("task", ["extraction", "classification", "calculation"])
def test_a_perfect_model_passes_the_scored_starters(task, tmp_path):
    # These starters need no judge. A stand-in model that gives each reference
    # back must score 100%, which proves the references and the scorers agree.
    target = tmp_path / "s"
    main(["init", task, "--dir", str(target)])
    cfg = load_config(target / "config.json")
    for m in cfg.models:
        m.runner = "echo"
    record = run_trial(cfg.test_set, cfg.pass_mark, cfg.models, {"echo": make_runner("echo")}, cfg.scorers, repeats=1)
    assert all(v == 1.0 for r in record.results for v in r.metrics.values()), [
        (r.case_id, r.metrics, r.note) for r in record.results if min(r.metrics.values()) < 1
    ]


def test_init_names_the_folder_after_task_and_provider(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "classification", "--provider", "openai"]) == 0
    assert (tmp_path / "trialmark-classification-openai" / "tickets.csv").exists()
    assert main(["init", "summarization"]) == 0  # the American spelling works too
    assert (tmp_path / "trialmark-summarisation-anthropic" / "notes.json").exists()
    assert main(["init", "poetry"]) == 2


# --- Scorers ------------------------------------------------------------------------


def test_json_output_is_read_from_fences_and_sentences():
    assert parse_json_output('```json\n{"a": 1}\n```') == ({"a": 1}, True)
    assert parse_json_output('Here you go: {"a": 1}. Done.') == ({"a": 1}, True)
    assert parse_json_output("no json here") == (None, False)


def test_fields_compare_numbers_as_numbers():
    s = make_scorer("fields")
    c = case({"total": 1250, "currency": "GBP", "ref": "A-12"})
    assert s.score(c, '{"total": "1,250.00", "currency": "gbp", "ref": "A-12"}')["all_fields_correct"] == 1.0
    got = s.score(c, '{"total": 1251, "currency": "GBP", "ref": "A-13"}')
    assert got["fields_correct"] == pytest.approx(1 / 3) and "total" in got["note"] and "ref" in got["note"]
    assert make_scorer("fields", {"tolerance": 0.01}).score(c, '{"total": 1251, "currency": "GBP", "ref": "A-12"}')["all_fields_correct"] == 1.0


def test_label_reads_the_category_from_a_sentence():
    labels = ["billing", "technical", "account", "feedback"]
    assert predicted_label("Category: Billing.", labels) == "billing"
    assert predicted_label("technical", labels) == "technical"
    assert predicted_label("I'd say account, though billing is involved", labels) == "account"
    assert predicted_label("No idea", labels) == ""
    s = make_scorer("label", {"labels": labels})
    assert s.score(case("billing"), "Billing")["correct"] == 1.0
    out = s.score(case("billing"), "This is technical")
    assert out["correct"] == 0.0 and out["note"] == "label: technical"


def test_number_scorer():
    assert numbers_in("USD 3,422.40 (12 chairs)") == [3422.4, 12.0]
    s = make_scorer("number", {"tolerance": 0.005})
    assert s.score(case("3422.40"), "£3,422.40")["correct"] == 1.0
    assert s.score(case(3422.40), "3423")["correct"] == 1.0  # within 0.5%
    assert s.score(case(3422.40), "3500")["correct"] == 0.0
    assert s.score(case(98), "The answer is unclear")["note"] == "no number in the answer"
    assert make_scorer("number", {"pick": "last"}).score(case(5), "Of 3 options, pick 5")["correct"] == 1.0
    m = make_scorer("number", {"marker": "Answer:"})
    assert m.score(case(96.5), "2 lamps = 84.00, delivery 12.50.\nAnswer: 96.50")["correct"] == 1.0
    assert m.score(case(96.5), "Total 96.50")["correct"] == 1.0  # no marker: the first number


def test_json_schema_scorer(tmp_path):
    pytest.importorskip("jsonschema")
    schema = {"type": "object", "required": ["total"], "properties": {"total": {"type": "number"}}}
    s = make_scorer("json-schema", {"schema": schema})
    assert s.score(case({}), '{"total": 5}') == {"valid_json": 1.0, "matches_schema": 1.0}
    bad = s.score(case({}), '{"total": "five"}')
    assert bad["valid_json"] == 1.0 and bad["matches_schema"] == 0.0 and "total" in bad["note"]
    assert s.score(case({}), "not json")["valid_json"] == 0.0
    (tmp_path / "s.json").write_text(json.dumps(schema))
    assert make_scorer("json-schema", {"schema_file": "s.json"}, base_dir=tmp_path).score(case({}), '{"total": 1}')["matches_schema"] == 1.0


class FakeStream:
    def __init__(self, m):
        self.m = m

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.m


class FakeAnthropic:
    def __init__(self, marks):
        self.marks, self.calls = marks, []
        self.messages = self

    def stream(self, **p):
        self.calls.append(p)
        body = json.dumps({"items": [{"met": m, "reason": "r"} for m in self.marks]})
        return FakeStream(NS(content=[NS(type="text", text=body)], stop_reason="end_turn", stop_details=None,
                             usage=NS(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0)))


def test_checklist_marks_each_item():
    client = FakeAnthropic([True, False, True])
    s = make_scorer("checklist", {"model": "j", "client": client, "checklist": ["Under 120 words"]})
    out = s.score(case({"checklist": ["Mentions the date", "Names the owner"]}, input="Summarise"), "a summary")
    assert out["checklist_met"] == pytest.approx(2 / 3) and out["all_met"] == 0.0
    assert "2. Mentions the date" in out["note"]
    prompt = client.calls[0]["messages"][0]["content"]
    assert "1. Under 120 words" in prompt and "3. Names the owner" in prompt
    # A reference that is a plain list works, and missing marks count as not met.
    short = make_scorer("checklist", {"model": "j", "client": FakeAnthropic([True])})
    got = short.score(case(["A", "B"]), "x")
    assert got["checklist_met"] == 0.5 and "marked 1 of 2" in got["note"]
    with pytest.raises(ValueError, match="needs checklist items"):
        make_scorer("checklist", {"model": "j", "client": FakeAnthropic([])}).score(case("just text"), "x")


# --- Confusion ---------------------------------------------------------------------


def test_confusion_report(tmp_path):
    ts = parse_test_set({"name": "t", "version": "1", "cases": [
        {"id": "1", "input": "a", "reference": "billing"}, {"id": "2", "input": "b", "reference": "billing"},
        {"id": "3", "input": "c", "reference": "technical"}, {"id": "4", "input": "d", "reference": "technical"},
    ]})

    class Fixed:
        def run(self, model, c):
            return {"1": "billing", "2": "technical", "3": "technical", "4": "no idea"}[c.id]

    record = run_trial(ts, PassMark(metric="correct"), [ModelEntry(id="m", runner="f")], {"f": Fixed()},
                       [make_scorer("label", {"labels": ["billing", "technical"]})], repeats=1)
    [mc] = confusion(record, ts, ["billing", "technical"])
    assert mc.accuracy == 0.5
    b = next(s for s in mc.labels if s.label == "billing")
    t = next(s for s in mc.labels if s.label == "technical")
    assert (b.precision, b.recall) == (1.0, 0.5) and (t.precision, t.recall) == (0.5, 0.5)
    assert mc.matrix[("billing", "technical")] == 1 and mc.matrix[("technical", "(none)")] == 1
    text = confusion_report([mc])
    assert "m: 50% correct over 4 answers" in text and "(none)" in text
    path = tmp_path / "r.json"
    record.save(path)
    (tmp_path / "t.json").write_text(json.dumps({"name": "t", "version": "1", "cases": [
        {"id": c.id, "input": c.input, "reference": c.reference} for c in ts.cases]}))
    assert main(["confusion", str(path), "--test-set", str(tmp_path / "t.json")]) == 0
