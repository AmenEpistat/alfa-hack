# alfa-insights — ranking module

Модуль ранжирования новостей и аналитики по компаниям: из `ranking_input` (новости + PDF-аналитика + watchlist) и датасета компаний собирает **5–10 наборов** вида `{company, news[2–5], analytics[1–3]}`.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
pip install -e "." # CPU
# pip install -e ".[dev,gpu]" # GPU (faiss-gpu + torch CUDA)