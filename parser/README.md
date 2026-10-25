# Parser

Внутренний модуль backend.py. Собирает внешние публикации, аналитические PDF и новости конкурентов.
Основной код — src/alpha_parser; входные PDF — inputs/analytics; настройки — config и .env.
Данные OCR — data/tessdata. SQL и HTTP-сервер не используются.
Общий вызов, кеширование и формат этапов описаны в ../README.md.
