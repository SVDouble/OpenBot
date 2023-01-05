from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import AnyUrl, BaseSettings
from pydantic import PostgresDsn as BasePostgresDsn
from pydantic import SecretStr

from app.models.bot import Bot

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

    bot: Bot

    postgres_url: PostgresDsn
    redis_url: AnyUrl
    redis_db: int

    backend_api_url: AnyUrl
    backend_api_verify: Path | bool = True
    backend_api_username: SecretStr
    backend_api_password: SecretStr

    cache_ex_bot = 60
    cache_ex_account = 60 * 60
    cache_ex_user = 60 * 60
    cache_ex_statechart = 60
    cache_ex_referral_link = 60 * 60
    cache_ex_content = 60 * 60
    cache_ex_role = 60 * 60
    cache_ex_question = 60

    inline_half_width = 15
    inline_full_width = 36
