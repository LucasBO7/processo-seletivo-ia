from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = BACKEND_ROOT / "src" / "app"


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_does_not_import_frameworks() -> None:
    forbidden = {"fastapi", "sqlalchemy", "qdrant_client", "cohere", "langgraph"}
    imports = set().union(*(imported_roots(path) for path in (SOURCE_ROOT / "domain").glob("*.py")))
    assert imports.isdisjoint(forbidden)


def test_application_does_not_import_frameworks_or_infrastructure() -> None:
    forbidden = {"fastapi", "sqlalchemy", "qdrant_client", "cohere"}
    paths = (SOURCE_ROOT / "application").rglob("*.py")
    imports = set().union(*(imported_roots(path) for path in paths))
    assert imports.isdisjoint(forbidden)
    for path in (SOURCE_ROOT / "application").rglob("*.py"):
        assert "app.infrastructure" not in path.read_text(encoding="utf-8")
