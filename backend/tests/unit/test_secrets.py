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
    secret_pattern = re.compile(r"(?:sk-|cohere[_-]?api[_-]?key\s*=\s*[^#\s])", re.IGNORECASE)
    offenders: list[str] = []
    for path in root.rglob("*"):
        if path.resolve() == Path(__file__).resolve():
            continue
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".md", ".toml", ".yaml", ".yml", ".example"}:
            continue
        if secret_pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
