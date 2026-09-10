from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from app.evaluation.live import collect_live_predictions
from app.evaluation.loader import load_dataset, load_predictions, load_thresholds
from app.evaluation.metrics import evaluate
from app.evaluation.report import write_reports

BACKEND_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_ROOT = BACKEND_ROOT / "evaluation"
RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")


def _safe_live_api(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise argparse.ArgumentTypeError(
            "live API must be an HTTP(S) URL without embedded credentials"
        )
    return value.rstrip("/")


def _safe_run_id(value: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "run ID must contain only letters, numbers, dots, underscores, and hyphens"
        )
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="startup-radar-evaluate")
    parser.add_argument("--cases", type=Path, default=EVALUATION_ROOT / "cases.v1.json")
    parser.add_argument("--thresholds", type=Path, default=EVALUATION_ROOT / "thresholds.v1.json")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=EVALUATION_ROOT / "predictions.reference.v1.json",
    )
    parser.add_argument("--output-dir", type=Path, default=EVALUATION_ROOT / "reports")
    parser.add_argument("--run-id", type=_safe_run_id, default="reference-v1")
    parser.add_argument(
        "--live-api",
        type=_safe_live_api,
        help="API base URL; requires RUN_LIVE_EVALUATION=1",
    )
    return parser


def run() -> None:
    raise SystemExit(execute(_parser().parse_args()))


def execute(arguments: argparse.Namespace) -> int:
    run_id = _safe_run_id(arguments.run_id)
    dataset = load_dataset(arguments.cases)
    thresholds = load_thresholds(arguments.thresholds)
    if arguments.live_api:
        live_api = _safe_live_api(arguments.live_api)
        if os.getenv("RUN_LIVE_EVALUATION") != "1":
            raise SystemExit("live evaluation requires RUN_LIVE_EVALUATION=1")
        predictions = collect_live_predictions(dataset, live_api)
        mode: Literal["offline", "live"] = "live"
    else:
        predictions = load_predictions(arguments.predictions)
        mode = "offline"
    report = evaluate(
        dataset,
        predictions,
        thresholds,
        run_id=run_id,
        mode=mode,
    )
    markdown_path, json_path = write_reports(report, arguments.output_dir)
    print(f"evaluation={'passed' if report.passed else 'failed'}")
    print(f"markdown_report={markdown_path}")
    print(f"json_report={json_path}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    run()
