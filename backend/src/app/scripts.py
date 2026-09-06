from __future__ import annotations

import subprocess
from pathlib import Path


def check() -> None:
    root = Path(__file__).resolve().parents[2]
    commands = [
        ["ruff", "format", "--check", "."],
        ["ruff", "check", "."],
        ["mypy", "src", "tests"],
        ["lint-imports"],
        ["pytest", "-m", "not integration"],
    ]
    for command in commands:
        subprocess.run(command, cwd=root, check=True)
