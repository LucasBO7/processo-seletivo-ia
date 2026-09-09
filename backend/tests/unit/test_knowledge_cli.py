import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.cli import knowledge
from app.cli.knowledge import _execute, _parser
from app.core.config import Settings


def test_cli_supports_dry_run_filters_and_offline_embeddings() -> None:
    arguments = _parser().parse_args(
        [
            "dry-run",
            "--source-key",
            "nvidia-nim",
            "--fixture-dir",
            "fixtures",
            "--offline-embeddings",
        ]
    )

    assert arguments.command == "dry-run"
    assert arguments.source_key == "nvidia-nim"
    assert arguments.offline_embeddings


async def test_offline_dry_run_needs_no_database_or_qdrant(settings: Settings, capsys) -> None:  # type: ignore[no-untyped-def]
    arguments = _parser().parse_args(
        [
            "dry-run",
            "--source-key",
            "nvidia-nim",
            "--fixture-dir",
            str(Path(__file__).parents[1] / "fixtures" / "knowledge"),
            "--offline-embeddings",
        ]
    )

    assert await _execute(arguments, settings=settings) == 0
    assert '"outcome":"created"' in capsys.readouterr().out


def test_cli_selects_compatible_event_loop_policy_on_windows(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    policy = Mock()
    set_policy = Mock()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        asyncio,
        "WindowsSelectorEventLoopPolicy",
        lambda: policy,
        raising=False,
    )
    monkeypatch.setattr(asyncio, "set_event_loop_policy", set_policy)
    monkeypatch.setattr(knowledge, "_parser", Mock(return_value=Mock()))

    def consume(coroutine) -> int:  # type: ignore[no-untyped-def]
        coroutine.close()
        return 0

    monkeypatch.setattr(asyncio, "run", consume)

    with pytest.raises(SystemExit) as raised:
        knowledge.run()

    assert raised.value.code == 0
    set_policy.assert_called_once_with(policy)
