import pytest

from trialmark.canonical import canonical, digest, matches


@pytest.mark.parametrize(
    "value, expected",
    [
        # Number examples from RFC 8785, appendix B and section 3.2.2.3.
        (333333333.33333329, "333333333.3333333"),
        (1e30, "1e+30"),
        (4.50, "4.5"),
        (2e-3, "0.002"),
        (0.000000000000000000000000001, "1e-27"),
        (-0.0, "0"),
        (1e21, "1e+21"),
        (1e20, "100000000000000000000"),
        (1e-7, "1e-7"),
        (0.000001, "0.000001"),
        (10.0, "10"),
        (-1.5, "-1.5"),
        (5e-324, "5e-324"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
        (9007199254740992, "9007199254740992"),
    ],
)
def test_numbers(value, expected):
    assert canonical(value) == expected


def test_rfc_8785_example_object():
    # The example in RFC 8785, section 3.2.3: keys sorted by UTF-16 code units.
    value = {
        "€": "Euro Sign",
        "\r": "Carriage Return",
        "דּ": "Hebrew Letter Dalet With Dagesh",
        "1": "One",
        "\U0001f600": "Emoji: Grinning Face",
        "\u0080": "Control",
        "ö": "Latin Small Letter O With Diaeresis",
    }
    keys = ["\r", "1", "\u0080", "ö", "€", "\U0001f600", "דּ"]
    out = canonical(value)
    positions = [out.index('"' + (k if k != "\r" else "\\r") + '"') for k in keys]
    assert positions == sorted(positions)


def test_structure_and_strings():
    assert canonical({"b": [1, True, None], "a": "x\ny\u0001"}) == '{"a":"x\\ny\\u0001","b":[1,true,null]}'


def test_rejects_what_json_cannot_hold():
    for bad in (float("nan"), float("inf"), 2**60, {1: "x"}, {1, 2}):
        with pytest.raises(ValueError):
            canonical(bad)


def test_both_hash_schemes_are_checked():
    value = {"a": 1.0, "b": "c"}
    assert matches(digest(value), value)
    legacy = "sha256:" + __import__("hashlib").sha256(b'{"a":1.0,"b":"c"}').hexdigest()
    assert matches(legacy, value)
    assert not matches("md5:abc", value)
    assert not matches(digest({"a": 2}), value)
