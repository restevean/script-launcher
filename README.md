    # Script Launcher

Web application to execute and schedule Python scripts with full control over timing and repetition.

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Run server
uv run uvicorn src.script_launcher.main:app --reload --reload-exclude 'scripts/*' --reload-exclude 'logs/*' --reload-exclude 'data/*' --port 8000
```

Open http://localhost:8000

## Features

- Register Python scripts manually
- **Scheduled Start:** One-time execution at a specific date/time
- **Repetition:** Periodic execution (seconds, minutes, hours, days)
- Filter by days of the week
- Combine scheduled start with repetition (start at X, then repeat every Y)
- Real-time log streaming via WebSocket
- Daily log files

## License

MIT
