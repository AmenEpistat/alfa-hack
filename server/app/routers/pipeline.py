"""One backend call for collection, ranking and insight generation."""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend import InferenceRequest, handle_request

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run")
def run(request: InferenceRequest) -> dict:
    result = handle_request(request.model_dump(mode="json"))
    if result["status"] == "failed":
        raise HTTPException(
            status_code=422
            if result["error"]["category"] in {"ValueError", "ValidationError"}
            else 503,
            detail=result,
        )
    return result
