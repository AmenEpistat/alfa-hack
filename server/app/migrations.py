"""Small additive SQLite migration for databases created before company profiles."""
from sqlalchemy import inspect, text


def ensure_legacy_company_columns(engine):
    if engine.dialect.name != 'sqlite' or 'companies' not in inspect(engine).get_table_names():
        return
    columns = {item['name'] for item in inspect(engine).get_columns('companies')}
    with engine.begin() as connection:
        if 'data' not in columns:
            connection.execute(text("ALTER TABLE companies ADD COLUMN data JSON NOT NULL DEFAULT '{}'"))
        for name in ('created_at', 'updated_at'):
            if name not in columns:
                connection.execute(text(f'ALTER TABLE companies ADD COLUMN {name} DATETIME'))
                connection.execute(text(f'UPDATE companies SET {name} = CURRENT_TIMESTAMP WHERE {name} IS NULL'))
