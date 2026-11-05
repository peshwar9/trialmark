import json
from pathlib import Path

import pytest

from trialmark import (
    ModelEntry,
    PassMark,
    Result,
    RunRecord,
    decision,
    load_record,
    load_test_set,
    parse_pass_mark,
    parse_test_set,
    summarise,
    text_report,
)
from trialmark.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"


def small_set():
    return parse_test_set({
        "name": "s",
        "version": "1",
        "cases": [
            {"id": "a", "input": "x", "reference": "y", "tags": ["t1"]},
            {"id": "b", "input": "x2", "reference": "y2", "tags": ["t2"]},
        ],
    })


def run(scores, pass_mark, costs=None, repeats=1):
    ts = small_set()
    record = RunRecord.start(ts, pass_mark, [ModelEntry(id=m) for m in scores], repeats=repeats)
    for r in range(repeats):
        for model, per_case in scores.items():
            for case, s in zip(ts.cases, per_case):
                record.add(Result(model=model, repeat=r, case_id=case.id, tags=list(case.tags),
                                  metrics=s, cost_usd=(costs or {}).get(model, 0.01), latency_ms=1000))
    return record


def test_hash_ignores_order_and_name():
    a = small_set()
    b = parse_test_set({"name": "renamed", "version": "2", "cases": list(reversed([
        {"id": "a", "input": "x", "reference": "y", "tags": ["t1"]},
        {"id": "b", "input": "x2", "reference": "y2", "tags": ["t2"]},
    ]))})
    assert a.hash == b.hash
    c = parse_test_set({"name": "s", "version": "1", "cases": [
        {"id": "a", "input": "x", "reference": "CHANGED", "tags": ["t1"]},
        {"id": "b", "input": "x2", "reference": "y2", "tags": ["t2"]},
    ]})
    assert a.hash != c.hash


def test_bad_test_sets_are_rejected():
    with pytest.raises(ValueError, match="more than once"):
        parse_test_set({"name": "s", "version": "1", "cases": [
            {"id": "a", "input": "", "reference": ""}, {"id": "a", "input": "", "reference": ""}]})
    with pytest.raises(ValueError, match="missing 'reference'"):
        parse_test_set({"name": "s", "version": "1", "cases": [{"id": "a", "input": ""}]})


def test_cheapest_within_tolerance_is_chosen():
    pm = PassMark(metric="correct", tolerance_points=10, floors={"grounded": 0.9})
    record = run(
        {
            "big": [{"correct": 1, "grounded": 1}, {"correct": 1, "grounded": 1}],
            "mid": [{"correct": 1, "grounded": 1}, {"correct": 0.8, "grounded": 1}],
            "tiny": [{"correct": 1, "grounded": 1}, {"correct": 1, "grounded": 0}],
        },
        pm,
        costs={"big": 0.1, "mid": 0.02, "tiny": 0.001},
    )
    d = decision(record)
    assert d.chosen == "mid"
    assert not d.verdict_for("tiny").passed
    assert "floor" in d.verdict_for("tiny").reasons[0]


def test_nothing_chosen_when_no_model_passes():
    pm = PassMark(metric="correct", floors={"grounded": 0.99})
    record = run({"m": [{"correct": 1, "grounded": 0}, {"correct": 1, "grounded": 1}]}, pm)
    assert decision(record).chosen is None


def test_range_across_repeats():
    ts = small_set()
    record = RunRecord.start(ts, PassMark(metric="correct"), [ModelEntry(id="m")], repeats=2)
    for r, score in enumerate([1.0, 0.5]):
        for case in ts.cases:
            record.add(Result(model="m", repeat=r, case_id=case.id, metrics={"correct": score}))
    m = summarise(record)[0].metrics["correct"]
    assert (m.mean, m.low, m.high) == (0.75, 0.5, 1.0)


def test_tag_breakdown():
    pm = PassMark(metric="correct")
    record = run({"m": [{"correct": 1}, {"correct": 0}]}, pm)
    assert summarise(record, tag="t1")[0].metrics["correct"].mean == 1
    assert summarise(record, tag="t2")[0].metrics["correct"].mean == 0


def test_pass_mark_cannot_be_changed_after_the_run(tmp_path):
    record = run({"m": [{"correct": 1}, {"correct": 1}]}, PassMark(metric="correct"))
    path = tmp_path / "r.json"
    record.save(path)
    data = json.loads(path.read_text())
    data["pass_mark"]["tolerance_points"] = 50
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="does not match"):
        decision(load_record(path))


def test_results_must_belong_to_the_run():
    record = run({"m": [{"correct": 1}, {"correct": 1}]}, PassMark(metric="correct"))
    with pytest.raises(ValueError, match="not in this run"):
        record.add(Result(model="other", repeat=0, case_id="a", metrics={}))
    with pytest.raises(ValueError, match="outside"):
        record.add(Result(model="m", repeat=5, case_id="a", metrics={}))


def test_parse_pass_mark_rejects_unknown_rule():
    with pytest.raises(ValueError):
        parse_pass_mark({"metric": "correct", "choose": "luckiest"})


def test_round_trip(tmp_path):
    record = run({"m": [{"correct": 1}, {"correct": 0.5}]}, PassMark(metric="correct"), repeats=2)
    path = tmp_path / "r.json"
    record.save(path)
    again = load_record(path)
    assert again.to_dict() == record.to_dict()


def test_example_record_and_cli(capsys):
    ts = load_test_set(EXAMPLES / "testset.json")
    record = load_record(EXAMPLES / "run-record.json")
    assert record.test_set["hash"] == ts.hash
    assert decision(record).chosen == "medium-model"
    assert "Tag: multi-part" in text_report(record, by_tag=True)
    path = str(EXAMPLES / "run-record.json")
    assert main(["gate", path, "--model", "medium-model", "--test-set", str(EXAMPLES / "testset.json")]) == 0
    assert main(["gate", path, "--model", "small-model"]) == 1
    assert main(["validate", str(EXAMPLES / "testset.json")]) == 0
    capsys.readouterr()
