from fastapi import status

from app.domain.models import RecoverableError

ERROR_STATUS_BY_CODE = {
    "query_empty": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "query_too_long": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "query_plan_invalid_output": status.HTTP_502_BAD_GATEWAY,
    "query_planner_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "retriever_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "extractor_invalid_output": status.HTTP_502_BAD_GATEWAY,
    "extractor_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "classifier_invalid_output": status.HTTP_502_BAD_GATEWAY,
    "classifier_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "evidence_validator_invalid_output": status.HTTP_502_BAD_GATEWAY,
    "evidence_validator_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "nvidia_rag_retrieval_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "recommendation_invalid_output": status.HTTP_502_BAD_GATEWAY,
    "recommendation_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def response_status(errors: list[RecoverableError]) -> int:
    for error in errors:
        mapped_status = ERROR_STATUS_BY_CODE.get(error.code)
        if mapped_status is not None:
            return mapped_status
    return status.HTTP_200_OK
