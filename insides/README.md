# Insides

generate_insights(ranked_json, client, audience_type="cfo", min_insights=5) формирует отдельные инсайты из сочетаний
событий нескольких источников. Ранжирование выполняется до вызова. Цитаты, документальные
основания и признаки компании проверяются кодом; минимальное число принятых статей — пять.

JSON хранит lead, events, synthesis, source_summaries, foundation, markdown и sources_markdown.
Каждая статья имеет AI-плашку, выжимку на 1–2 предложения, основной текст и источники.
Экспорт save_articles из export.py сохраняет пары article.md / article_sources.md.
Модель и постоянный кеш подключает backend.py. Старых CLI и одиночной генерации нет.

У каждого нового инсайта обязательный category_id (целое 1–10) и category с каноническими
id, slug, name, description, image_key, image_description. Модель выбирает одну категорию
по главному совместному выводу; backend подставляет её название и привязку к иллюстрации.
Справочник — categories.py. В Markdown название отображается после AI-плашки.
Это бизнес-категория, независимая от primary_topic (типов источников news/pdf/competitors).
Встроенных файлов картинок нет: frontend сопоставляет image_key своей иллюстрации.

Роль читателя audience_type обязательна. План и статьи учитывают её задачи; роль —
не право доступа. Каталог alfa_products.json передаётся в модель. Минимум один продукт
в каждом инсайте подтверждается ID и точной цитатой возможности; название и URL
подставляются кодом. В Markdown есть блок продукта; в JSON — product_recommendations,
target_audience и self_check. Контракт: output.schema.json. Подробнее: ../ARCHITECTURE.md.

Код модуля:
- generation.py — планирование, генерация, повторное выполнение и отчёт.
- validation.py — проверка фактов, цитат, признаков компании и продуктов.
- prompts.py — сообщения для модели и привязка цитат.
- markdown.py / export.py — оформление и сохранение статей.
