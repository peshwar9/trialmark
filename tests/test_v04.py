"""Trialmark 0.4: the cost estimate and --yes, --limit and --only, the starters,
the judge's recorded spend, and the judge check."""

import csv
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from trialmark import ModelEntry, PassMark, load_config, make_runner, make_scorer, parse_test_set, run_trial
from trialmark.cli import main
from trialmark.estimate import estimate_run, needs_confirmation
from trialmark.judgecheck import score_grades, verdict_of, write_sample
from trialmark.run import select_cases

ROOT = Path(__file__).parent.parent
TEMPLATES = ROOT / "src" / "trialmark" / "templates"


def test_starters_in_examples_match_the_packaged_templates():
    for provider in ("anthropic", "openai"):
        for name in ("README.md", "config.json", "questions.csv", "contract.md"):
            packaged = (TEMPLATES / provider / name).read_text()
            copy = (ROOT / "examples" / f"quickstart-{provider}" / name).read_text()
            assert packaged == copy, f"examples/quickstart-{provider}/{name} differs from the template"


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_init_writes_a_starter_that_estimates_without_a_key(tmp_path, capsys, monkeypatch, provider):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target = tmp_path / "starter"
    assert main(["init", provider, "--dir", str(target)]) == 0
    assert sorted(p.name for p in target.iterdir()) == ["README.md", "config.json", "contract.md", "questions.csv"]
    capsys.readouterr()
    assert main(["run", str(target / "config.json")]) == 0
    out = capsys.readouterr().out
    assert "Nothing run. Add --yes" in out and "total" in out and "unknown" not in out
    assert not (target / "record.json").exists()
    # Writing over a starter is refused.
    assert main(["init", provider, "--dir", str(target)]) == 2


def test_starter_estimate_is_in_a_sensible_range(tmp_path):
    main(["init", "anthropic", "--dir", str(tmp_path / "s")])
    est = estimate_run(load_config(tmp_path / "s" / "config.json"))
    assert 0.5 < est.known_total < 5
    assert est.answers["claude-haiku-5-5"] < est.answers["claude-sonnet-5-5"]


def test_echo_runs_need_no_yes_but_paid_ones_do(tmp_path):
    cfg = load_config(ROOT / "examples" / "config.json")
    assert needs_confirmation(cfg)  # it uses the python runner, whose cost is unknown
    cfg.runners = {k: v for k, v in cfg.runners.items() if k == "echo"}
    cfg.models = [m for m in cfg.models if m.runner == "echo"]
    assert not needs_confirmation(cfg)


def test_limit_and_only_narrow_the_run_and_its_hash():
    cfg = load_config(ROOT / "examples" / "config.json")
    full_hash = cfg.test_set.hash
    cfg = select_cases(cfg, only=["q2", "q4", "q5"], limit=2)
    assert [c.id for c in cfg.test_set.cases] == ["q2", "q4"]
    assert cfg.test_set.hash != full_hash
    with pytest.raises(ValueError, match="No case with the id zz"):
        select_cases(load_config(ROOT / "examples" / "config.json"), only=["zz"])


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
    def __init__(self, reply):
        self.reply = reply
        self.messages = self

    def stream(self, **params):
        text = self.reply(params) if callable(self.reply) else self.reply
        return FakeStream(NS(content=[NS(type="text", text=text)], stop_reason="end_turn", stop_details=None,
                             usage=NS(input_tokens=1000, output_tokens=200, cache_read_input_tokens=0,
                                      cache_creation_input_tokens=0)))


def test_the_judge_spend_is_recorded_and_reported(capsys):
    ts = parse_test_set({"name": "t", "version": "1", "cases": [
        {"id": "a", "input": "Q", "reference": "R"}, {"id": "b", "input": "Q2", "reference": "R2"}]})
    verdict = json.dumps({"verdict": "correct", "declined": False, "note": "ok"})
    judge = make_scorer("judge", {"model": "j", "client": FakeAnthropic(verdict), "pricing": {"input": 4, "output": 20}})
    record = run_trial(ts, PassMark(metric="correct"), [ModelEntry(id="m", runner="anthropic", settings={"pricing": {"input": 1, "output": 5}})],
                       runners={"anthropic": make_runner("anthropic", {"client": FakeAnthropic("answer")})},
                       scorers=[judge], repeats=1)
    spent = record.judge["spent"]
    assert spent["calls"] == 2 and spent["input_tokens"] == 2000
    assert spent["cost_usd"] == pytest.approx(2 * (1000 * 4 + 200 * 20) / 1e6)
    from trialmark import text_report

    report = text_report(record)
    assert "2 calls, $0.02" in report and "on the judge" in report


def test_judge_check_sample_and_score(tmp_path, capsys, monkeypatch):
    from trialmark import load_record, load_test_set

    monkeypatch.chdir(ROOT)
    run_path = tmp_path / "run.json"
    assert main(["run", str(ROOT / "examples" / "config.json"), "--output", str(run_path), "--yes"]) == 0
    record = load_record(run_path)
    ts = load_test_set(ROOT / "examples" / "testset.json")
    path = tmp_path / "grades.csv"
    n = write_sample(record, ts, path, size=6, seed=3)
    rows = list(csv.DictReader(open(path)))
    assert n == 6 and len(rows) == 6 and all(r["your_verdict"] == "" for r in rows)
    assert "judge" not in rows[0]  # the judge's grade is hidden from the person grading
    # Grade every row as the run did, except one, which is flipped.
    by_key = {(r.case_id, r.model, r.repeat): r for r in record.results}
    for i, row in enumerate(rows):
        v = verdict_of(by_key[(row["case_id"], row["model"], int(row["repeat"]))])
        row["your_verdict"] = v if i else ("incorrect" if v != "incorrect" else "correct")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    a = score_grades(record, path)
    assert (a.graded, a.agreed, len(a.disagreements)) == (6, 5, 1)
    capsys.readouterr()
    assert main(["judge-check", "score", str(run_path), str(path)]) == 0
    assert "agreed with you on 5" in capsys.readouterr().out


def test_judge_check_rejects_bad_grades(tmp_path):
    record = __import__("trialmark").load_record(ROOT / "examples" / "run-record.json")
    p = tmp_path / "g.csv"
    p.write_text("case_id,model,repeat,your_verdict\nq1,large-model,0,maybe\n")
    with pytest.raises(ValueError, match="not one of"):
        score_grades(record, p)
    p.write_text("case_id,model,repeat,your_verdict\nq1,large-model,0,\n")
    with pytest.raises(ValueError, match="No row has a verdict"):
        score_grades(record, p)
