from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        initials=user.initials,
        role=user.role,
    )


@router.get("/users", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    users = db.scalars(select(User).order_by(User.name)).all()

    return [serialize_user(user) for user in users]


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user = db.scalar(select(User).where(User.id == payload.user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден.",
        )

    # Для демо-проекта токеном является идентификатор пользователя.
    return LoginResponse(
        access_token=user.id,
        user=serialize_user(user),
    )


@router.get("/me", response_model=UserResponse)
def get_current_user(
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = db.scalar(select(User).where(User.id == token))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен.",
        )

    return serialize_user(user)
