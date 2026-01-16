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
- Configure scheduled repetition (seconds, minutes, hours, days)
- Filter by days of the week
- Real-time log streaming via WebSocket
- Daily log files

## License

MIT
