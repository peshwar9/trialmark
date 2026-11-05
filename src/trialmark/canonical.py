"""Canonical JSON under RFC 8785 (the JSON Canonicalization Scheme), and the hashes built on it.

Two programs in different languages that hash the same value must get the same
hash. Sorting keys is not enough: languages print numbers differently (1.0 or
1, 1e21 or 1e+21). RFC 8785 fixes one form: keys sorted by their UTF-16 code
units, no spaces, the shortest string escapes, and numbers printed the way
JavaScript prints them.

Hashes written by Trialmark 0.1 and 0.2 used Python's sorted json.dumps and
carry the prefix "sha256:". They are still checked with that method. New hashes
carry the prefix "jcs-sha256:".
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from typing import Any

PREFIX = "jcs-sha256:"
LEGACY_PREFIX = "sha256:"


def _number(x: int | float) -> str:
    if isinstance(x, int):
        if abs(x) > 2**53:
            raise ValueError(f"The integer {x} is too large for canonical JSON; store it as a string.")
        return str(x)
    if math.isnan(x) or math.isinf(x):
        raise ValueError("Canonical JSON cannot hold NaN or infinity.")
    if x == 0:
        return "0"
    # Python's repr is the shortest form that round-trips, as JavaScript's is;
    # only the layout differs, which the ECMAScript rules below decide.
    sign, digits, exponent = Decimal(repr(x)).normalize().as_tuple()
    s = "".join(map(str, digits))
    k = len(s)
    n = exponent + k  # the position of the decimal point
    if k <= n <= 21:
        out = s + "0" * (n - k)
    elif 0 < n <= 21:
        out = s[:n] + "." + s[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + s
    else:
        e = n - 1
        mantissa = s if k == 1 else s[0] + "." + s[1:]
        out = f"{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"
    return ("-" if sign else "") + out


def canonical(value: Any) -> str:
    """Serialise a JSON value under RFC 8785."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical(v) for v in value) + "]"
    if isinstance(value, dict):
        for k in value:
            if not isinstance(k, str):
                raise ValueError("Canonical JSON keys must be strings.")
        keys = sorted(value, key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical(value[k]) for k in keys) + "}"
    raise ValueError(f"Canonical JSON cannot hold a {type(value).__name__}.")


def _legacy(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return PREFIX + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def matches(stored: str, value: Any) -> bool:
    """Whether a stored hash, of either scheme, is the hash of this value."""
    if stored.startswith(PREFIX):
        return stored == digest(value)
    if stored.startswith(LEGACY_PREFIX):
        return stored == LEGACY_PREFIX + hashlib.sha256(_legacy(value).encode("utf-8")).hexdigest()
    return False
