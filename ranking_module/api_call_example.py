from ranking_module.src.alfa_insights.api import health, run_ranking, validate_payload

# health-check (без моделей)
status = health(config="config.yaml")

# предвалидация (лёгкая, без моделей)
warnings = validate_payload(payload_dict)

# основной вызов
result = run_ranking(
    payload=payload_dict,  # ranking_input JSON как dict (или путь)
    companies=companies_df,  # DataFrame (или путь к CSV)
    config="config.yaml",  # путь к config.yaml (или AppConfig)
    overrides=None,  # опционально: {"runtime":{"device":"cpu"}}
)
