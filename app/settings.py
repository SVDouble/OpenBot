import datetime
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import BaseSettings, AnyUrl, PostgresDsn as BasePostgresDsn

__all__ = ["Settings"]


class PostgresDsn(BasePostgresDsn):
    allowed_schemes = BasePostgresDsn.allowed_schemes | {"postgresql+psycopg"}


class Settings(BaseSettings):
    class Config:
        keep_untouched = (cached_property,)
        env_file = Path(__file__).parent.parent / ".env"

    title: str = "EasyBot"
    version: str = "v0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    project_root: Path = Path(__file__).parent.parent
    static_root: Path = project_root / "static"

    bot_token: str
    bot_username: str
    bot_clock_interval: datetime.timedelta = datetime.timedelta(minutes=1)
    user_clock_interval: datetime.timedelta = datetime.timedelta(minutes=1)

    user_statechart_source: Path = static_root / "user.yml"
    bot_statechart_source: Path = static_root / "bot.yml"

    postgres_url: PostgresDsn
    redis_url: AnyUrl
    redis_db: int

    inline_half_width = 15
    inline_full_width = 36
