# Сторонние компоненты и источники

Перечень зависимостей не заменяет условия их лицензий. Полные версии Python-зависимостей и SHA256 находятся в `docker/requirements.lock`, клиентские зависимости — в `client/package-lock.json`. При распространении проверяйте поставляемые пакеты и их LICENSE.

- UI: React, React DOM (MIT), MobX, mobx-react-lite (MIT), Ant Design (MIT), Lucide (ISC), react-markdown, remark-gfm (MIT).
- Сборка: Vite (MIT), TypeScript (Apache-2.0), Sass (MIT), Node.js и nginx; базовые образы и системные пакеты содержат собственные notices.
- API: FastAPI (MIT), Uvicorn (BSD), SQLAlchemy (MIT), Pydantic и pydantic-settings (MIT), SQLite (public domain), HTTPX (BSD).
- Документы и OCR: pdfplumber/pdfminer.six (MIT), pypdfium2/PDFium (BSD и дополнительные notices PDFium), Tesseract и языковые данные rus/eng (Apache-2.0), trafilatura (Apache-2.0), feedparser (BSD).
- Ранжирование: numpy, pandas, scipy, scikit-learn, FAISS CPU, sentence-transformers, transformers, PyTorch, orjson, PyYAML, jsonschema. Лицензии и версии следует сверять с фактически установленными пакетами lockfile.
- Конфигурация embedding-моделей: `intfloat/multilingual-e5-small`, reranker `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` в `ranking_module/config.yaml`. Веса скачиваются отдельно; проверяйте model cards и лицензии моделей перед распространением.
- Генеративная LLM: внешняя разрешённая модель через `ALPHA_LLM_BASE_URL` и `ALPHA_LLM_MODEL`; семейство по умолчанию GLM-5.3-Flash. Веса и ключи не распространяются с проектом. Поддержка вызова в коде не означает, что внешний сервис проверен в этой сессии.
- Датасеты: обезличенные материалы хакатона (в том числе `ranking_module/data/companies.csv`) и загружаемые командой исходные CSV/PDF. Права определяются условиями кейса; не публикуйте исходные закрытые материалы по умолчанию.
- Внешние публикации остаются собственностью издателей. Банк представлен собственными аналитическими материалами и отдельным продуктовым каталогом `insides/alfa_products.json`; каталог продуктов не является аналитическим доказательством.
- SVG категорий подготовлены в коде проекта в стиле существующих трёх иллюстраций; каталог и генератор находятся в `server/static/insight-categories` и `assets/insight-categories`.
- Смоделировано: вход с токеном-ID пользователя, начальные статьи и статическая банковская сводка. Реальные банковские операции, подключение к счетам, промышленная авторизация и автоматическая выдача продуктов не реализованы.
