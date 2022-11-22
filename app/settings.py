import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseSettings, AnyUrl

__all__ = ["Settings"]


class Settings(BaseSettings):
    class Config:
        env_file = Path(__file__).parent.parent / ".env"

    title: str = "EasyBot"
    version: str = "v0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    project_root: Path = Path(__file__).parent.parent
    static_root: Path = project_root / "static"

    bot_token: str
    bot_clock_interval: datetime.timedelta = datetime.timedelta(minutes=1)
    user_clock_interval: datetime.timedelta = datetime.timedelta(minutes=1)

    user_statechart_source: Path = static_root / "user.yml"
    bot_statechart_source: Path = static_root / "bot.yml"

    redis_url: AnyUrl = "redis://redis"
    redis_db: int = 0
