from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseSettings

__all__ = ["Settings", "get_settings"]


class Settings(BaseSettings):
    class Config:
        env_file = Path(__file__).parent.parent / ".env"

    title: str = "EasyBot"
    version: str = "v0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    project_root: Path = Path(__file__).parent.parent
    static_root: Path = project_root / "static"

    bot_token: str

    user_statechart_source: Path = static_root / "user-logic.yml"
    bot_statechart_source: Path = static_root / "flip-flop.yml"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
