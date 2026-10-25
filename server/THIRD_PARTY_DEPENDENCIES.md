# Third-party dependencies

Сторонние зависимости backend-сервера Alfa Hack и их назначение.

## Runtime

- Python 3.11+
- FastAPI - веб-фреймворк для HTTP API.
- Uvicorn - ASGI-сервер для запуска FastAPI.
- SQLAlchemy - ORM и работа с базой данных.
- Pydantic - валидация входных и выходных данных.
- pydantic-settings - загрузка настроек из переменных окружения и `.env`.
- httpx - HTTP-клиент для внешних API.
- feedparser - обработка RSS/Atom-лент.
- trafilatura - извлечение текста и метаданных веб-страниц.
- pandas - обработка табличных данных.
- NumPy - численные операции и работа с массивами.
- PyYAML - чтение YAML-конфигураций.
- jsonschema - проверка JSON-документов по схемам.
- orjson - быстрая сериализация и десериализация JSON.
- scikit-learn - вспомогательные алгоритмы машинного обучения.
- sentence-transformers - создание текстовых embeddings.
- FAISS - поиск ближайших векторов.
- Tesseract OCR - распознавание текста на отсканированных PDF.
- Tesseract language data `rus` и `eng` - языковые модели OCR.

## Python dependencies

Основные Python-зависимости задаются в:

```text
server/pyproject.toml
```

Текущий список:

```toml
dependencies = [
    "fastapi==0.162.0",
    "uvicorn[standard]==0.54.0",
    "sqlalchemy==2.1.16",
    "pydantic==2.14.1",
    "pydantic-settings>=2,<3",
    "pymupdf>=1.26,<2",
    "trafilatura>=2,<3",
    "feedparser>=6,<7",
    "httpx>=0.28,<1",
]
```

Дополнительные зависимости, используемые модулями для ранжирования и парсинга:

```text
pandas
numpy
pyyaml
jsonschema
orjson
scikit-learn
sentence-transformers
faiss
```

Их версии могут задаваться через `flake.nix` или отдельную конфигурацию окружения.

## Назначение зависимостей

| Зависимость | Используется для |
|---|---|
| `fastapi` | Создание REST API |
| `uvicorn` | Запуск backend-сервера |
| `sqlalchemy` | Работа с SQLite и ORM-моделями |
| `pydantic` | Валидация API-запросов и ответов |
| `pydantic-settings` | Загрузка конфигурации из `.env` |
| `httpx` | Запросы к LLM, поисковым сервисам и внешним источникам |
| `feedparser` | Парсинг RSS и Atom |
| `trafilatura` | Извлечение основного текста статей |
| `pandas` | Подготовка данных компаний для ranking-модуля |
| `numpy` | Работа с числовыми массивами |
| `pyyaml` | Чтение `config.yaml` ranking-модуля |
| `jsonschema` | Проверка JSON по схемам |
| `orjson` | Оптимизированная работа с JSON |
| `scikit-learn` | Подготовка признаков и вспомогательные алгоритмы ranking-модуля |
| `sentence-transformers` | Генерация embeddings |
| `faiss` | Индексация и поиск по embeddings |
| `tesseract` | OCR для PDF без текстового слоя |


## Использование NixOS

Системная конфигурация, необходимая для запуска backend-сервера расположена в:

```text
flake.nix
```

