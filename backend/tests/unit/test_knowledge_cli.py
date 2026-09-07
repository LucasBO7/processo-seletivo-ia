from pathlib import Path

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
