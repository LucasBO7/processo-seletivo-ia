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
    forbidden = {
        "cohere",
        "fastapi",
        "groq",
        "langchain_groq",
        "langgraph",
        "qdrant_client",
        "sqlalchemy",
    }
    imports = set().union(*(imported_roots(path) for path in (SOURCE_ROOT / "domain").glob("*.py")))
    assert imports.isdisjoint(forbidden)


def test_application_does_not_import_frameworks_or_infrastructure() -> None:
    forbidden = {"cohere", "fastapi", "groq", "langchain_groq", "qdrant_client", "sqlalchemy"}
    paths = (SOURCE_ROOT / "application").rglob("*.py")
    imports = set().union(*(imported_roots(path) for path in paths))
    assert imports.isdisjoint(forbidden)
    for path in (SOURCE_ROOT / "application").rglob("*.py"):
        assert "app.infrastructure" not in path.read_text(encoding="utf-8")


def test_graph_state_and_agents_do_not_import_groq_sdk() -> None:
    paths = [SOURCE_ROOT / "graph" / "state.py"]
    agents = SOURCE_ROOT / "graph" / "agents"
    if agents.exists():
        paths.extend(agents.rglob("*.py"))
    imports = set().union(*(imported_roots(path) for path in paths))
    assert imports.isdisjoint({"groq", "langchain_groq"})
