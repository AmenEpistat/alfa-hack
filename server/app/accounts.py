"""The two prototype accounts. Audience is determined by the server, not the browser."""
from fastapi import HTTPException
ACCOUNT_AUDIENCES = {'anna': 'cfo', 'ilya': 'treasury_head'}


def audience_for_user(user_id: str) -> str:
    if user_id not in ACCOUNT_AUDIENCES:
        raise HTTPException(401, 'Пользователь не найден.')
    return ACCOUNT_AUDIENCES[user_id]


def require_audience(user_id: str, requested: str):
    if requested != audience_for_user(user_id):
        raise HTTPException(403, 'Роль запроса не соответствует аккаунту.')
