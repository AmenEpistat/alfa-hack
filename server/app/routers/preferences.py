from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Insight, User, UserPreference
from ..schemas import FeedbackRequest, PreferenceResponse

router = APIRouter(
    prefix="/api/preferences",
    tags=["preferences"],
)


def get_or_create_preference(
    db: Session,
    user_id: str,
    insight_id: str,
) -> UserPreference:
    preference = db.scalar(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.insight_id == insight_id,
        )
    )

    if preference is None:
        preference = UserPreference(
            user_id=user_id,
            insight_id=insight_id,
            is_saved=False,
        )
        db.add(preference)
        db.flush()

    return preference


@router.get("", response_model=list[PreferenceResponse])
def get_preferences(
    user_id: str = Query(default="anna"),
    db: Session = Depends(get_db),
) -> list[PreferenceResponse]:
    preferences = db.scalars(
        select(UserPreference).where(UserPreference.user_id == user_id)
    ).all()

    return [
        PreferenceResponse(
            insight_id=item.insight_id,
            is_saved=item.is_saved,
            feedback=item.feedback,
            reason=item.feedback_reason,
        )
        for item in preferences
    ]


@router.post(
    "/{insight_id}/toggle",
    response_model=PreferenceResponse,
)
def toggle_saved(
    insight_id: str,
    user_id: str = Query(default="anna"),
    db: Session = Depends(get_db),
) -> PreferenceResponse:
    user = db.scalar(select(User).where(User.id == user_id))

    insight = db.scalar(select(Insight).where(Insight.id == insight_id))

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Пользователь не найден.",
        )

    if insight is None:
        raise HTTPException(
            status_code=404,
            detail="Инсайт не найден.",
        )

    preference = get_or_create_preference(
        db,
        user_id,
        insight_id,
    )

    preference.is_saved = not preference.is_saved

    db.commit()
    db.refresh(preference)

    return PreferenceResponse(
        insight_id=preference.insight_id,
        is_saved=preference.is_saved,
        feedback=preference.feedback,
        reason=preference.feedback_reason,
    )


@router.post(
    "/feedback",
    response_model=PreferenceResponse,
)
def save_feedback(
    payload: FeedbackRequest,
    user_id: str = Query(default="anna"),
    db: Session = Depends(get_db),
) -> PreferenceResponse:
    user = db.scalar(select(User).where(User.id == user_id))

    insight = db.scalar(select(Insight).where(Insight.id == payload.insight_id))

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Пользователь не найден.",
        )

    if insight is None:
        raise HTTPException(
            status_code=404,
            detail="Инсайт не найден.",
        )

    preference = get_or_create_preference(
        db,
        user_id,
        payload.insight_id,
    )

    preference.feedback = payload.feedback
    preference.feedback_reason = payload.reason

    db.commit()
    db.refresh(preference)

    return PreferenceResponse(
        insight_id=preference.insight_id,
        is_saved=preference.is_saved,
        feedback=preference.feedback,
        reason=preference.feedback_reason,
    )
