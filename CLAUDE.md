# Script Launcher

Web application to execute and schedule Python scripts with full control over timing and repetition.

## Project Structure

```
script_launcher/
├── src/script_launcher/      # Main application code
│   ├── main.py               # FastAPI entry point
│   ├── config.py             # App configuration
│   ├── database.py           # SQLite setup
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── api/                  # REST endpoints
│   ├── services/             # Business logic
│   └── websocket/            # WebSocket handlers
├── static/                   # Frontend (HTML/Tailwind/JS)
├── tests/                    # Test suite
├── logs/                     # Daily log files (generated)
└── data/                     # SQLite database (generated)
```

## Tech Stack

- **Backend:** FastAPI + Python 3.12+
- **Database:** SQLite + SQLAlchemy (async)
- **Scheduler:** APScheduler
- **Frontend:** HTML/CSS (Tailwind) + JavaScript vanilla
- **Real-time:** WebSocket for live logs
- **Package Manager:** uv (always use uv, never pip)

## Initial Setup

```bash
# Create venv with Python 3.12
uv venv --python 3.12

# Install all dependencies (including dev)
uv sync --all-extras
```

## Commands

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras

# Run development server (excludes user scripts/logs/data from hot-reload)
uv run uvicorn src.script_launcher.main:app --reload --reload-exclude 'scripts/*' --reload-exclude 'logs/*' --reload-exclude 'data/*' --port 8000

# Run tests
uv run pytest -v

# Run tests with coverage
uv run pytest -v --cov=src/script_launcher --cov-report=term-missing

# Lint code
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/

# Setup pre-commit hooks
uv run pre-commit install
uv run pre-commit install --hook-type pre-push

# Run pre-commit manually
uv run pre-commit run --all-files
```

## Architecture Notes

- **Single-user:** No authentication required
- **Script model:** Includes schedule configuration (repeat_enabled, interval, weekdays)
- **Execution lock:** Same script cannot run in parallel
- **Logs:** Daily text files with format `TIMESTAMP|SCRIPT_NAME|LEVEL|MESSAGE`
- **WebSocket:** Real-time log streaming to frontend

## UI Layout

Two tabs:
1. **Scripts Tab:** 2 columns (script list | detail/config/actions)
2. **Logs Tab:** Full-width log viewer with filters

## API Endpoints

### Scripts
- `GET /api/scripts` - List all scripts
- `POST /api/scripts` - Create new script
- `GET /api/scripts/{id}` - Get script details
- `PUT /api/scripts/{id}` - Update script
- `DELETE /api/scripts/{id}` - Delete script
- `POST /api/scripts/{id}/enable` - Enable script
- `POST /api/scripts/{id}/disable` - Disable script

### Executions
- `POST /api/scripts/{id}/run` - Run script manually
- `POST /api/scripts/{id}/stop` - Stop running script
- `GET /api/scripts/{id}/status` - Get script execution status
- `GET /api/executions` - List active executions
- `GET /api/executions/{id}` - Get execution details

### Logs
- `GET /api/logs` - Query logs (filterable by date, script, level)
- `GET /api/logs/dates` - Get available log dates

### WebSocket
- `WS /ws/logs` - Real-time log stream (all scripts)
- `WS /ws/logs/{script_id}` - Real-time log stream (specific script)
