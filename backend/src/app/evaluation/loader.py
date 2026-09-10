from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.evaluation.models import EvaluationDataset, PredictionSet, ThresholdSet


def _load[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    return model.model_validate(payload)


def load_dataset(path: Path) -> EvaluationDataset:
    return _load(path, EvaluationDataset)


def load_predictions(path: Path) -> PredictionSet:
    return _load(path, PredictionSet)


def load_thresholds(path: Path) -> ThresholdSet:
    return _load(path, ThresholdSet)
