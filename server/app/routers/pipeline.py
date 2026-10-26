"""One backend call for collection, ranking and insight generation."""
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_user_id
from ..accounts import require_audience
from ..publication import store_generated_insights

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend import InferenceRequest, handle_request

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run")
def run(request: InferenceRequest, user_id: str = Depends(get_user_id), db: Session = Depends(get_db)) -> dict:
    require_audience(user_id, request.audience_type)
    result = handle_request(request.model_dump(mode="json"))
    if result["status"] == "failed":
        raise HTTPException(status_code=422 if result["error"]["category"] in {"ValueError", "ValidationError"} else 503,
                            detail=result)
    if isinstance(result.get("insights"), dict):
        result["published_insight_ids"] = store_generated_insights(db, result["insights"], user_id, result["run_id"])
    return result
