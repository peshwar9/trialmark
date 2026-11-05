import json
from importlib import resources
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
from referencing import Registry, Resource  # noqa: E402

from trialmark.cli import main  # noqa: E402

ROOT = Path(__file__).parent.parent


def schema(name):
    return json.loads(resources.files("trialmark").joinpath(f"schemas/{name}.schema.json").read_text())


def validator(name):
    registry = Registry().with_resources(
        (f"https://github.com/peshwar9/trialmark/schemas/{n}.schema.json", Resource.from_contents(schema(n)))
        for n in ("testset", "passmark", "run-record")
    )
    return jsonschema.Draft202012Validator(schema(name), registry=registry)


@pytest.mark.parametrize("name", ["testset", "passmark", "run-record"])
def test_schemas_are_valid(name):
    jsonschema.Draft202012Validator.check_schema(schema(name))


def test_examples_match_the_schemas(tmp_path, monkeypatch):
    validator("testset").validate(json.loads((ROOT / "examples" / "testset.json").read_text()))
    for record in (ROOT / "examples" / "run-record.json", ROOT / "tests" / "fixtures" / "record-0.2.json"):
        validator("run-record").validate(json.loads(record.read_text()))
    monkeypatch.chdir(ROOT)
    out = tmp_path / "r.json"
    assert main(["run", str(ROOT / "examples" / "config.json"), "--output", str(out)]) == 0
    validator("run-record").validate(json.loads(out.read_text()))


def test_a_bad_pass_mark_is_rejected():
    with pytest.raises(jsonschema.ValidationError):
        validator("passmark").validate({"metric": "correct", "choose": "luckiest"})


def test_schema_command(capsys):
    assert main(["schema", "passmark"]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "Trialmark pass mark"
