# Конфигурация

Корневой `.env` читает Docker Compose и передаёт в API только перечисленные в `compose.yaml` переменные. Произвольное добавление переменной в `.env` не делает её доступной контейнеру. После изменения настроек: `docker compose up -d --force-recreate api`. Не используйте реальные ключи в `VITE_*`, build args или Git.

| Переменная | Значение по умолчанию / назначение |
| --- | --- |
| `APP_PORT` | `8080`, порт живого интерфейса на `127.0.0.1` |
| `SYNTHETIC_PORT` | `8081`, порт отдельного синтетического стенда |
| `ALPHA_LLM_BASE_URL` | `https://api.alfahack-gateway26.ru/v1`, совместимый шлюз |
| `ALPHA_LLM_API_KEY` | Пусто; нужен для живой генерации и чата |
| `ALPHA_LLM_MODEL` | Пусто; точный ID доступной модели провайдера |
| `ALPHA_LLM_FAMILY` | `GLM-5.3-Flash`; семейство не заменяет ID модели |
| `ALPHA_LLM_FALLBACK_BASE_URL` | Пусто; дополнительный адрес шлюза |
| `ALPHA_LLM_TIMEOUT`, `ALPHA_LLM_CONNECT_TIMEOUT` | `45`, `5` секунд |
| `ALPHA_LLM_MAX_OUTPUT_TOKENS` | `4096` в Compose |
| `ALPHA_LLM_REASONING_EFFORT` | `low`; допустимы `low`, `high`, `max` |
| `ALPHA_LLM_THINKING_PROTOCOL` | `legacy`; также поддержан `openrouter` |
| `ALPHA_LLM_THINKING_MODE` | `default`; также `instant`, `minimal` |
| `ALPHA_LLM_LENGTH_RETRIES` | `1`; допустимо `0` или `1` |
| `ALPHA_DAILY_BUDGET_RUB` | `500`; локальный учёт расходов |
| `ALPHA_ALLOW_UNKNOWN_COST` | `true` в Compose; разрешает вызовы без известных тарифов |
| `ALPHA_INPUT_RUB_PER_MILLION`, `ALPHA_OUTPUT_RUB_PER_MILLION` | Пусто; тарифы провайдера на миллион токенов |
| `ALPHA_OCR_ENABLED`, `ALPHA_OCR_LANGUAGE` | `true`, `rus+eng` |
| `ALPHA_SEARXNG_URL` | `http://searxng:8080`; внутренний сервис профиля `search` |
| `SEARXNG_SECRET` | Локальное демонстрационное значение из `.env.example`; заменить перед внешним размещением поиска |
| `DATABASE_URL` | В Compose фиксирован `sqlite:////app/state/backend.db`; для изменения нужен override Compose |
| `HF_HOME`, `HF_HUB_CACHE` | В Dockerfile: `/app/.cache/huggingface` и подкаталог `hub` |
| `ALPHA_TESSDATA`, `TESSDATA_PREFIX` | В Dockerfile: `/usr/share/tesseract-ocr/5/tessdata` |
| `VITE_API_URL` | Build arg `/api` для Docker; публичный адрес API, не секрет |
| `VITE_PROXY_TARGET` | Только локальная разработка Vite; по умолчанию `http://127.0.0.1:8000` |
| `VITE_DEMO_MODE` | `true` для статической Netlify-сборки; не включает API-стенд |
| `VITE_SYNTHETIC_MODE` | `true` только в синтетической сборке: баннер и метки тестового сценария |
| `ALPHA_SYNTHETIC_DEMO` | `1` только для отдельной точки входа `demo.app:app` |
| `ALPHA_SYNTHETIC_WORKDIR` | Внутренний параметр локального теста: временные кэш и артефакты |

Без тарифов и при `ALPHA_ALLOW_UNKNOWN_COST=true` локальный бюджет не гарантирует ограничение списаний. Счёт провайдера и ограничения ключа действуют независимо.

| Файл | Содержимое |
| --- | --- |
| `ranking_module/config.yaml` | Модели, CPU, веса оценок, размеры наборов, пути ранкера |
| `parser/config/sources.json` | Источники публикаций |
| `parser/config/analytics_manifest.json` | Имена и метаданные девяти исходных PDF |
| `parser/config/searxng/settings.yml` | JSON-поиск и настройки внутреннего SearXNG |
| `parser/src/alpha_parser/config.py` | Остальные ограничения сбора, OCR, кэша и LLM |
| `insides/alfa_products.json` | Каталог продуктов для рекомендаций |
| `docker/nginx.conf` | Проксирование, размер запроса, ожидание ответа API 600 секунд |
| `client/.env.example` | Публичные настройки клиента для разработки |

При запуске Python без Docker API ищет файл настроек парсера в `parser/.env`; корневой `.env` сам по себе не экспортируется в shell. Основная инструкция использует Docker и не требует ручного экспорта ключей. Подписанной авторизации и переменных `ALPHA_DEMO_ACCESS_CODE`, `ALPHA_SESSION_SECRET`, `ALPHA_CORS_ORIGINS` в текущей реализации нет.
