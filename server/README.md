# API и ML-интеграция

Основной запуск и данные: [корневой README](../README.md). Docker и переменные: [docker/README.md](../docker/README.md).

Python 3.12; локальная установка из корня:

```sh
python3.12 -m venv server/.venv
server/.venv/bin/python -m pip install -e ./server -e ./parser
server/.venv/bin/python -m uvicorn app.main:app --app-dir server --reload --host 127.0.0.1 --port 8000
```

Для реального ранжирования дополнительно нужен `ranking_module`; полный совместимый CPU-набор зафиксирован в `docker/requirements.lock`. OCR использует Tesseract с русским и английским языком. В Nix есть `nix run .#backend`.

## Контракт

- `GET /api/auth/users` — два аккаунта; `POST /api/auth/login {user_id}` — моковый токен; `GET /api/auth/me?token=...` — восстановление сессии. В user есть `audience_type`.
- Остальные пользовательские ручки принимают `Authorization: Bearer <token>`, прежний `?user_id=` поддержан для совместимости. Это прототип, не промышленная аутентификация.
- `GET /api/insights` — опубликованная подборка роли; пока её нет, общие исходные статьи с `audience_type=null`.
- `GET /api/insights/{id}` — `content` (Markdown), `category_id` (ML-число 1–10), `category_name`, `cover_url`, `cover_background`, `source_ids`, `generation_method`, `audience_type`, `prepared_at`, `expires_at`, `product_recommendations`, `is_saved`. Старые sections/cover/minutes сохранены для совместимости; время чтения не показывается.
- `GET /api/insights/meta/categories` — канонические категории ML вместе с image_key и SVG. Файлы `/api/assets/insight-categories/` публичны и не содержат клиентских данных.
- `GET /api/insights/meta/sources` — источники видимой подборки. `origin=bank` для alpha_pdf, `publisher=Альфа-Банк`, цитаты в `excerpts`.
- `GET /api/insights/meta/profile`, `/meta/purchase-plan` и `/export/purchase-plan.csv` — контекст и исходные данные. Отсутствующий план не заполняется фиктивными закупками.
- `POST /api/insights/ask {insight_id, question, history?}` — ML-чат по сохранённому серверному контексту. Роль привязана к аккаунту. Ненастроенная LLM возвращает ошибку, а не поддельный ответ.
- `GET /api/preferences`, `POST /api/preferences/{id}/toggle`, `POST /api/preferences/feedback` — пользовательские действия; feedback=null снимает оценку.
- `POST /api/pipeline/run` и `/api/insight-agent/generate` — запускают соответствующую обработку и публикуют принятый результат в ленту роли; в ответе `published_insight_ids`. audience_type запроса должен совпадать с ролью аккаунта.

Генерация не запускается при каждом входе автоматически. Исходный объект ML хранится в отдельной таблице GeneratedInsight; существующие статьи/компании не удаляются. Схема старой SQLite дополняется безопасной миграцией профиля компаний.

## Проверки

```sh
PYTHONPATH=server server/.venv/bin/python -m unittest discover -s server/tests -v
```

Тесты используют отдельную временную SQLite и контролируемый результат генерации. Проверяются два аккаунта, разделение подборок, публикация, Markdown, все десять обложек, источник банка, история чата, оценки и миграция. Они не доказывают качество реальной LLM и не расходуют её бюджет.
