from __future__ import annotations

import sys
from typing import Any

import httpx

from app.evaluation.models import (
    EvaluationDataset,
    EvaluationPrediction,
    PredictedPlan,
    PredictionSet,
    RankedNvidiaItem,
)

PROFILE_FIELDS = (
    "product",
    "business_model",
    "sector",
    "target_audience",
    "ai_use_cases",
    "technologies",
    "infrastructure",
    "external_dependencies",
    "technical_needs",
    "claims",
)


def collect_live_predictions(dataset: EvaluationDataset, api_url: str) -> PredictionSet:
    endpoint = f"{api_url.rstrip('/')}/api/v1/search"
    predictions: list[EvaluationPrediction] = []
    with httpx.Client(timeout=300) as client:
        for case in dataset.cases:
            print(f"evaluation_case_started case_id={case.id}", file=sys.stderr)
            response = client.post(endpoint, json={"query": case.query})
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError(f"invalid API response for case {case.id}")
            predictions.append(_from_api(case.id, payload))
            print(
                f"evaluation_case_finished case_id={case.id} status={response.status_code}",
                file=sys.stderr,
            )
    return PredictionSet(version=f"live-{dataset.version}", predictions=predictions)


def _from_api(case_id: str, payload: dict[str, Any]) -> EvaluationPrediction:
    raw_plan = payload.get("query_plan")
    plan: dict[str, Any] = raw_plan if isinstance(raw_plan, dict) else {}
    raw_filters = plan.get("filters")
    filters: dict[str, Any] = raw_filters if isinstance(raw_filters, dict) else {}
    profiles = payload.get("validated_profiles") or payload.get("structured_profiles") or []
    profile_facts = _profile_facts(profiles if isinstance(profiles, list) else [])
    classifications = (
        payload.get("validated_classifications") or payload.get("classifications") or []
    )
    classification = _classification(classifications)
    evidence = payload.get("claim_validations") or []
    evidence_statuses = {
        str(item.get("claim_key")): str(item.get("status"))
        for item in evidence
        if isinstance(item, dict) and item.get("claim_key") and item.get("status")
    }
    chunks = [
        chunk
        for context in payload.get("nvidia_contexts", [])
        if isinstance(context, dict)
        for chunk in context.get("chunks", [])
        if isinstance(chunk, dict)
    ]
    before = sorted(
        chunks,
        key=lambda chunk: float(
            chunk.get("scores", {}).get("hybrid_score", 0)
            if isinstance(chunk.get("scores"), dict)
            else 0
        ),
        reverse=True,
    )
    return EvaluationPrediction(
        case_id=case_id,
        plan=PredictedPlan(
            status=str(plan.get("status", "missing")),
            filters={
                str(key): [str(value) for value in values]
                for key, values in filters.items()
                if isinstance(values, list)
            },
        ),
        ranked_startups=[
            str(item.get("name"))
            for item in payload.get("candidate_startups", [])
            if isinstance(item, dict) and item.get("name")
        ],
        profile_facts=profile_facts,
        classification=classification,
        evidence_statuses=evidence_statuses,
        nvidia_before_rerank=[_ranked_item(item) for item in before],
        nvidia_after_rerank=[_ranked_item(item) for item in chunks],
        citation_urls=_citation_urls(payload),
        recommended_technologies=[
            str(item.get("technology"))
            for item in payload.get("recommendations", [])
            if isinstance(item, dict) and item.get("technology")
        ],
    )


def _profile_facts(profiles: list[Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {field: [] for field in PROFILE_FIELDS}
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        for field in PROFILE_FIELDS:
            raw = profile.get(field)
            facts = raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else []
            result[field].extend(
                str(fact["value"]) for fact in facts if isinstance(fact, dict) and fact.get("value")
            )
    return {field: values for field, values in result.items() if values}


def _classification(classifications: Any) -> str:
    if not isinstance(classifications, list) or not classifications:
        return "missing"
    first = classifications[0]
    if not isinstance(first, dict):
        return "missing"
    return str(first.get("category") or "uncertain")


def _ranked_item(chunk: dict[str, Any]) -> RankedNvidiaItem:
    return RankedNvidiaItem(
        source_key=str(chunk.get("source_key", "missing")),
        source_url=str(chunk.get("source_url", "")),
    )


def _citation_urls(payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for source in payload.get("selected_sources", []):
        if isinstance(source, dict) and source.get("source_url"):
            urls.append(str(source["source_url"]))
    for context in payload.get("nvidia_contexts", []):
        if isinstance(context, dict):
            for chunk in context.get("chunks", []):
                if isinstance(chunk, dict) and chunk.get("source_url"):
                    urls.append(str(chunk["source_url"]))
    return list(dict.fromkeys(urls))
