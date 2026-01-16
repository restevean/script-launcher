"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Script Launcher"
    debug: bool = False

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    data_dir: Path = base_dir / "data"
    logs_dir: Path = base_dir / "logs"

    # Database
    database_url: str = f"sqlite+aiosqlite:///{data_dir}/scripts.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_prefix": "SCRIPT_LAUNCHER_"}


settings = Settings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.logs_dir.mkdir(parents=True, exist_ok=True)
