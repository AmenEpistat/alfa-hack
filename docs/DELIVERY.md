# Состав поставки

| Требование | Артефакт |
| --- | --- |
| Назначение решения, архитектура, компоненты | `README.md`, схема и раздел 3 |
| Окружение, пошаговый запуск и проверка | `README.md`, `scripts/start.sh`, `docs/ACCEPTANCE.md` |
| Конфигурации и переменные | `.env.example`, `docs/CONFIGURATION.md`, конфиги модулей |
| Единый Docker-запуск | `compose.yaml` с профилем `search`; `compose.synthetic.yaml` для автономного тестового сценария |
| Версии языка и ключевых зависимостей | Digest в Dockerfile/Compose, `docker/requirements.lock`, `client/package-lock.json`, `flake.lock`, `docs/REPRODUCIBILITY.md` |
| Сторонние компоненты, модели, данные, сервисы и имитации | `THIRD_PARTY_NOTICES.md` |
| Синтетические данные и аккаунты | `demo/fixtures`, `demo/README.md`, штатные seed-аккаунты `anna` и `ilya` |
| Сквозной сценарий | `demo/verify.py` через HTTP; `demo/check_local.py` через ASGI; ручные шаги в `docs/ACCEPTANCE.md` |
| API и схемы | Таблица в README; `/docs`, `/redoc`, `/openapi.json` работающего API |
| Модель данных | `docs/DATA_MODEL.md`, `server/app/models.py`, JSON-схемы модулей |

Комплект позволяет проверить приложение на вымышленных данных с явно обозначенными заменами внешних ML-компонентов. Проверка настоящего сбора, OCR, ранжирования и LLM требует материалов кейса, сети и разрешённого ключа. Эти внешние ресурсы не включены и не подменяются утверждением о пройденном живом E2E.
