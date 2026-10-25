# Парсер → ранкер → агент инсайдов

Единый вызов находится в `backend.py`. Он вызывает существующие Python-модули напрямую, без HTTP-запросов между этапами.

## Подготовка

Из корня проекта установите модули в одно окружение:

```powershell
.\parser\.venv\Scripts\python.exe -m pip install -e .\parser -e .\ranking_module -e .\server
```

Установка зависимостей ранкера может быть тяжёлой: PyTorch, Sentence Transformers и FAISS. Первый реальный запуск также загружает веса bi-encoder и cross-encoder. Эти операции автоматически при проверке интеграции не выполнялись.

Настройки шлюза GLM и SearXNG читаются из `parser/.env`. Данные компаний находятся в `inputs/csv/df_Uid_data_hack.csv`, аналитика и манифест — в `parser/inputs/analytics` и `parser/config/analytics_manifest.json`. По умолчанию PDF берутся из подготовленного кэша; первичное извлечение разрешается только явным `allow_pdf_processing: true`.

PDF-стек: `pdfplumber` / `pdfminer.six` для текста и таблиц, PDFium для рендеринга, системный Tesseract для OCR. После смены движка кэш PDF нужно подготовить один раз; изолированный вызов без веб-поиска и LLM описан в `parser/README.md`. Для Tesseract вне PATH задайте `ALPHA_TESSERACT_CMD`.

Для веб-поиска:

```powershell
docker compose --env-file .\parser\.env -f .\parser\compose.yaml up -d searxng
```

FAISS-индексы ранкера в `ranking_module/cache/news` и `ranking_module/cache/analytics` необязательны для запуска: при отсутствии актуальных кандидатов существующий ранкер использует cross-encoder по текущим материалам. Для больших корпусов заранее подготовьте индексы штатными скриптами из `ranking_module/scripts`. Конфигурация разрешается относительно каталога `ranking_module`, а не текущего рабочего каталога.

## Вызов из backend

```python
from backend import InferenceService

service = InferenceService(tenant_id="customer-123")
result = service.handle({
    "action": "run",
    "company_id": "U_2521",
    "audience_type": "cfo",
    "min_insights": 5,
})
```

Вместо `company_id` можно передать `profile` — готовый профиль после preprocessing. Ранкеру по умолчанию передаётся очищенный датасет с теми же идентификаторами и признаками. Собственный датасет можно настроить аргументом конструктора `companies` (DataFrame или путь к CSV в формате ранкера), а пути — `project_dir`, `csv_path`, `cache_dir`, `output_dir`.

Для готового JSON парсера пропустите сбор и передайте `ranking_input`:

```python
import json
from pathlib import Path
from backend import InferenceService

parser_json = json.loads(Path("путь/04_ranker_input.json").read_text(encoding="utf-8-sig"))
result = InferenceService().handle({
    "action": "run",
    "audience_type": (parser_json.get("target_audience") or {}).get("type", "decision_maker"),
    "ranking_input": parser_json,
})
```

Этот вызов запускает настоящий ранкер и GLM. Для проверки только ранжирования используйте `action: "rank"`. Для обработки уже готовых наборов используйте `action: "generate"`, исходный `ranking_input` и результат ранкера в `ranking_result`. Старый вариант `generate` с JSON `topics` без `ranking_result` сохранён; `ranked_input` также принимается как прежнее имя входного поля.

Через HTTP тот же запрос отправляется в `POST /api/pipeline/run`. Старые `/api/parser/collect`, `/api/ranking/run`, `/api/insight-agent/generate` сохранены. Последний теперь принимает необязательный `ranking_result` рядом с исходным `ranking_input`.

```powershell
.\parser\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000
```

Для CLI сохраните тело запроса в `request.json`:

```powershell
.\parser\.venv\Scripts\python.exe backend.py --request request.json --response response.json
```

## Что соединяет адаптер

Выход ранкера `sets[]` содержит выбранные `item_id`, оценки и причины отбора, но не все поля для цитат. `pipeline_adapter.ranked_for_insights` восстанавливает точные исходные записи из parser JSON, включая `version_id`, `chunk_id`, страницы, имя PDF и качество извлечения. Неизвестные ID и изменения текста отклоняются. Watchlist и профиль клиента сохраняются: `sets[].company` — объект наблюдения, а не замена клиенту.

Генератор получает только отобранные источники и описание наборов. Его существующий планировщик выбирает события внутри одного набора, обязательно используя новости и аналитику; программная проверка запрещает смешивать наборы. Writer получает только допустимые фрагменты. У инсайда сохраняются `rank_set_ids`. Количество статей по-прежнему определяется содержательными связями и проверяется относительно `min_insights`; склейка не превращает механически каждый набор в обязательную статью.

## Ответ и сохранение

`handle()` возвращает JSON-совместимый dict с `status`, `stage`, `run_id`, `ranking_input`, `ranking_result`, `ranked_input`, `insights` и `artifacts` (поля зависят от выполненных этапов). Статьи: `result["insights"]["insights"]`.

Все этапы нового вызова сохраняются в `output/runs/<tenant_hash>/<run_id>/`:

- `00_request.json`, `01_preprocessing.json` — параметры и профиль;
- `02_sources.json`, `03_parser.json` — корпус и результат сбора, когда выполнялся парсер;
- `04_ranker_input.json` — исходные материалы для ранкера;
- `05_ranking.json` — результат `sets[]`;
- `05_ranked.json` — восстановленные источники и границы наборов для агента;
- `06_insights.json`, `insights/*.md` — проверенные инсайды, статьи и пояснения к источникам.

`partial` сохраняет ограничения исходного сбора. Пустой результат ранкера останавливает генерацию без вызовов GLM. Установка зависимостей, реальные веса/индексы, live SearXNG и модельный шлюз проверяются отдельно. Подготовленные PDF/CSV и одинаковые запросы генерации используют файловый кэш.

