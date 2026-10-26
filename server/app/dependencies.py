from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from .accounts import ACCOUNT_AUDIENCES
from .database import get_db
from .models import User


def get_user_id(
    authorization: str | None = Header(default=None),
    user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> str:
    token = authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else user_id
    if token not in ACCOUNT_AUDIENCES or db.get(User, token) is None:
        raise HTTPException(status_code=401, detail="Войдите в аккаунт, чтобы продолжить.")
    return token
