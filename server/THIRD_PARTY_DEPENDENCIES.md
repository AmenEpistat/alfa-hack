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
- pdfplumber / pdfminer.six — извлечение текста, координат и таблиц PDF (MIT).
- pypdfium2 / PDFium — рендеринг страниц перед OCR (Apache-2.0 / BSD-3-Clause; PDFium — BSD-style).
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
    "pdfplumber>=0.11.4,<0.12",
    "pypdfium2>=4.30,<6",
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
| `pdfplumber` / `pdfminer.six` | Текст PDF, координаты и таблицы |
| `pypdfium2` / PDFium | Рендеринг страниц для OCR |

## Лицензии PDF-компонентов и закрытая поставка

- `pdfplumber` и `pdfminer.six` — MIT. При распространении сохраняются copyright и текст лицензии.
- `pypdfium2` — Apache-2.0 / BSD-3-Clause; сам PDFium — BSD-style. Вместе с бинарниками нужно передавать лицензии PDFium и включённых в конкретную сборку компонентов (`pypdfium2/BUILD_LICENSES` и лицензии из установленного wheel).
- Tesseract и официальные модели `tessdata` — Apache-2.0. Сохраняются лицензия и применимые уведомления.
- Pillow, используемый для изображений, — MIT-CMU. Сохраняются соответствующие уведомления.

Перечисленные разрешительные лицензии позволяют использовать эти компоненты
в закрытом приложении без требования публиковать собственный код приложения.
Этот раздел касается PDF-стека, а не аудита всех зависимостей платформы.
При формировании дистрибутива сохраняйте LICENSE/NOTICE и metadata пакетов;
не копируйте только `.py`/DLL, исключая сопутствующие лицензии.

Официальные сведения:

- https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt
- https://github.com/pdfminer/pdfminer.six/blob/master/LICENSE
- https://github.com/pypdfium2-team/pypdfium2#licensing
- https://pdfium.googlesource.com/pdfium/+/refs/heads/main/LICENSE
- https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE
- https://github.com/python-pillow/Pillow/blob/main/LICENSE


## Использование NixOS

Системная конфигурация, необходимая для запуска backend-сервера расположена в:

```text
flake.nix
```

