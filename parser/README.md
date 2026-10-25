# Parser

Внутренний модуль backend.py. Собирает внешние публикации, аналитические PDF и новости конкурентов.
Основной код — src/alpha_parser; входные PDF — inputs/analytics; настройки — config и .env.
Данные OCR — data/tessdata. SQL и HTTP-сервер не используются.
Общий вызов, кеширование и формат этапов описаны в ../README.md.

PDF обрабатываются `pdfplumber` / `pdfminer.six` (MIT), страницы для OCR рендерятся
через `pypdfium2` / PDFium. OCR выполняет системный Tesseract (Apache-2.0).
Его команда настраивается через `ALPHA_TESSERACT_CMD` (по умолчанию `tesseract`),
языковые модели — через `ALPHA_TESSDATA`, лимит времени на страницу —
`ALPHA_OCR_TIMEOUT` (60 секунд).

Для закрытой поставки сохраняйте лицензии и уведомления зависимостей;
подробности — в `../server/THIRD_PARTY_DEPENDENCIES.md`.

После смены PDF-движка старое извлечение автоматически перестаёт подходить
текущей сигнатуре кэша. Исходные PDF и исторические JSON не меняются.
Перед использованием `cached_only` один раз подготовьте новый кэш:

Из корня проекта (может быть длительно для сканов):

```python
from backend import PROJECT_DIR
from alpha_parser import ResearchModule

module = ResearchModule(
    workspace=PROJECT_DIR / "parser",
    output_dir=PROJECT_DIR / "output" / "pdf-preparation",
    cache_dir=PROJECT_DIR / "cache",
)
try:
    results = module.ingest_pdfs()
    print([{"file": r.get("document", {}).get("original_filename"),
            "quality": r.get("document", {}).get("quality", r.get("quality")),
            "error": r.get("error")} for r in results])
finally:
    module.store.save_corpus()
```

Этот вызов обрабатывает только PDF из манифеста, без веб-поиска и LLM.
