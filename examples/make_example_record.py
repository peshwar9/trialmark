"""Writes examples/run-record.json: an illustrative run of three made-up models on
examples/testset.json. The scores are invented to show the format and the
report; they are not measurements of any real model."""

from pathlib import Path

from trialmark import ModelEntry, PassMark, Result, RunRecord, load_test_set

HERE = Path(__file__).parent

# Per model: correct and grounded scores for q1..q5, cost per case, time per case.
MODELS = {
    "large-model": ([1, 1, 1, 1, 1], [1, 1, 1, 1, 1], 0.030, 9000),
    "medium-model": ([1, 1, 1, 0.5, 1], [1, 1, 1, 1, 1], 0.012, 6000),
    "small-model": ([0.5, 1, 1, 0.5, 0], [1, 1, 1, 1, 0], 0.003, 3000),
}


def main() -> None:
    ts = load_test_set(HERE / "testset.json")
    pass_mark = PassMark(metric="correct", tolerance_points=15, floors={"grounded": 0.95}, choose="cheapest")
    record = RunRecord.start(
        ts,
        pass_mark,
        [ModelEntry(id=m, provider="example") for m in MODELS],
        repeats=3,
        judge={"model": "example-judge", "prompt_version": "1"},
    )
    for repeat in range(3):
        for model, (correct, grounded, cost, ms) in MODELS.items():
            for case, c, g in zip(ts.cases, correct, grounded):
                # The medium model misses q1 in one repeat, to show a range.
                if model == "medium-model" and repeat == 2 and case.id == "q1":
                    c = 0.5
                record.add(Result(
                    model=model, repeat=repeat, case_id=case.id, tags=list(case.tags),
                    metrics={"correct": c, "grounded": g}, cost_usd=cost, latency_ms=ms + 100 * repeat,
                ))
    record.run_id = "example"
    record.pass_mark_set_at = "2026-11-05T00:00:00+00:00"
    record.save(HERE / "run-record.json")


if __name__ == "__main__":
    main()
