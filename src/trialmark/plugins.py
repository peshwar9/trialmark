"""The four customisation points, and how Trialmark finds plugins for them.

A plugin is a class (or, for a loader or report, a function) that follows one of
the interfaces below. Trialmark finds plugins in two places:

1. Its own built-in plugins.
2. Installed packages that declare an entry point in one of these groups:

       trialmark.runners    trialmark.scorers    trialmark.loaders    trialmark.reports

   For example, in a plugin package's pyproject.toml:

       [project.entry-points."trialmark.runners"]
       acme = "trialmark_acme:AcmeRunner"

A plugin may not take the name of a built-in one. From Python, a plugin object
can also be passed directly, without registering it at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from . import __version__
from .record import ModelEntry, RunRecord
from .testset import Case, TestSet

GROUPS = {
    "runner": "trialmark.runners",
    "scorer": "trialmark.scorers",
    "loader": "trialmark.loaders",
    "report": "trialmark.reports",
}


# --- Interfaces -----------------------------------------------------------------


@dataclass
class RunOutput:
    """What a runner returns for one case.

    Leave latency_ms as None to let Trialmark time the call. Set error instead of
    raising when the model call failed in a way the record should show.
    """

    output: Any
    cost_usd: float = 0.0
    latency_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


@runtime_checkable
class Runner(Protocol):
    """Calls one model on one case's input.

    Constructed once per run with the options from the configuration. `run` may
    be called from several threads at once when concurrency is above one.
    """

    def run(self, model: ModelEntry, case: Case) -> RunOutput: ...


@runtime_checkable
class Scorer(Protocol):
    """Scores one output against the case's reference.

    `metrics` names every metric `score` can return, each between 0 and 1, so a
    failed call can be scored 0 on all of them. Like a runner, a scorer is
    constructed once per run and may be called from several threads.
    """

    metrics: tuple[str, ...]

    def score(self, case: Case, output: Any) -> dict[str, float]: ...


# A loader reads a test set from a file: (path, **options) -> TestSet.
Loader = Callable[..., TestSet]

# A report writer renders a record: (record, by_tag: bool) -> str.
ReportWriter = Callable[[RunRecord, bool], str]


# --- Registry -------------------------------------------------------------------

_BUILTINS: dict[str, dict[str, Any]] = {kind: {} for kind in GROUPS}


def builtin(kind: str, name: str):
    """Decorator that registers a built-in plugin."""

    def register(obj):
        _BUILTINS[kind][name] = obj
        return obj

    return register


def _entry_points(kind: str) -> dict[str, metadata.EntryPoint]:
    return {ep.name: ep for ep in metadata.entry_points(group=GROUPS[kind])}


def _ensure_builtins() -> None:
    # Importing the modules runs their @builtin decorators.
    from . import builtins  # noqa: F401


def find(kind: str, name: str) -> Any:
    """Return the plugin class or function registered under a name."""
    if kind not in GROUPS:
        raise ValueError(f"Unknown plugin kind '{kind}'.")
    _ensure_builtins()
    eps = _entry_points(kind)
    if name in _BUILTINS[kind]:
        if name in eps:
            raise ValueError(
                f"The installed package '{eps[name].dist.name if eps[name].dist else '?'}' declares a {kind} "
                f"named '{name}', which is the name of a built-in {kind}. Rename the plugin."
            )
        return _BUILTINS[kind][name]
    if name in eps:
        return eps[name].load()
    known = sorted({*_BUILTINS[kind], *eps})
    raise ValueError(f"No {kind} named '{name}'. Available: {', '.join(known) or 'none'}.")


def version_of(kind: str, name: str) -> str:
    _ensure_builtins()
    if name in _BUILTINS[kind]:
        return f"trialmark {__version__}"
    ep = _entry_points(kind).get(name)
    if ep is not None and ep.dist is not None:
        return f"{ep.dist.name} {ep.dist.version}"
    return "unknown"


def available() -> dict[str, list[tuple[str, str]]]:
    """Every plugin Trialmark can find, by kind, with where it comes from."""
    _ensure_builtins()
    out: dict[str, list[tuple[str, str]]] = {}
    for kind in GROUPS:
        rows = [(n, "built in") for n in sorted(_BUILTINS[kind])]
        for n, ep in sorted(_entry_points(kind).items()):
            if n not in _BUILTINS[kind]:
                rows.append((n, ep.dist.name if ep.dist else ep.value))
        out[kind] = rows
    return out


def make_runner(name: str, options: dict[str, Any] | None = None) -> Runner:
    obj = find("runner", name)(**(options or {}))
    if not isinstance(obj, Runner):
        raise ValueError(f"Runner '{name}' has no run(model, case) method.")
    return obj


def make_scorer(name: str, options: dict[str, Any] | None = None) -> Scorer:
    obj = find("scorer", name)(**(options or {}))
    if not isinstance(obj, Scorer) or not getattr(obj, "metrics", None):
        raise ValueError(f"Scorer '{name}' needs a non-empty `metrics` and a score(case, output) method.")
    return obj


def load_with(path: str | Path, loader: str | None = None, options: dict[str, Any] | None = None) -> TestSet:
    """Load a test set, choosing the loader from the file extension unless one is named."""
    name = loader or Path(path).suffix.lstrip(".").lower() or "json"
    return find("loader", name)(path, **(options or {}))


def render(record: RunRecord, fmt: str = "text", by_tag: bool = False) -> str:
    return find("report", fmt)(record, by_tag)
