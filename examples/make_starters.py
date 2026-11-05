"""Writes examples/starters/<task>-<provider>/ from trialmark.starters, the same
files `trialmark init` writes. Run it after changing a starter; a test checks the
two match.

    python examples/make_starters.py
"""

import shutil
from pathlib import Path

from trialmark.starters import PROVIDERS, TASKS, write

HERE = Path(__file__).parent / "starters"

if __name__ == "__main__":
    shutil.rmtree(HERE, ignore_errors=True)
    for task in TASKS:
        for provider in PROVIDERS:
            write(task, provider, HERE / f"{task}-{provider}")
            print(f"wrote examples/starters/{task}-{provider}")
