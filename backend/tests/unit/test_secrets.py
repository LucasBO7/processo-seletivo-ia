import os
import re
from pathlib import Path


def test_repository_does_not_contain_provider_secrets() -> None:
    root = Path(__file__).resolve().parents[3]
    excluded = {
        ".git",
        ".mypy_cache",
        ".npm-cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "dist",
        "node_modules",
        "tmp",
    }
    secret_pattern = re.compile(
        r"(?:sk-|(?:cohere|groq)[_-]?api[_-]?key\s*=\s*[^#\s])", re.IGNORECASE
    )
    offenders: list[str] = []
    for directory, directories, filenames in os.walk(root):
        directories[:] = [name for name in directories if name not in excluded]
        for filename in filenames:
            path = Path(directory, filename)
            if path.resolve() == Path(__file__).resolve():
                continue
            if path.suffix.lower() not in {
                ".py",
                ".md",
                ".toml",
                ".yaml",
                ".yml",
                ".example",
            }:
                continue
            if secret_pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                offenders.append(str(path.relative_to(root)))
    assert offenders == []
