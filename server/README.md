# Alfa Hack Backend

Стек:

- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic

## Запуск

### Если вы используете NixOS:

```bash
nix run .#backend
```

### Если вы НЕ используете NixOS:

Перейдите в директорию server:

```bash
cd server
```

Создайте виртуальное окружение:

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
```

### macOS / Linux

```bash
source .venv/bin/activate
```

Установите зависимости:

```bash
pip install -r requirements.txt
```

Запустите сервер:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### После запуска:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Конечные точки 

Используйте Swagger или ReDoc для просмотра конечных точек
