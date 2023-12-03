import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import PostgresDsn, AnyUrl, ConfigDict
from pydantic import SecretStr
from pydantic_settings import BaseSettings

from app.models.bot import Bot

__all__ = ["Settings"]


class Settings(BaseSettings):
    model_config = ConfigDict(extra="ignore")

    title: str = "EasyBot"
    version: str = "v0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    project_root: Path = Path(__file__).parent.parent
    static_root: Path = project_root / "static"

    bot_id: UUID
    bot: Bot | None = None

    postgres_url: PostgresDsn
    redis_url: AnyUrl
    redis_db: int

    backend_api_url: AnyUrl
    backend_api_verify: Path | bool = True
    backend_api_username: SecretStr
    backend_api_password: SecretStr

    cache_ex_bot: int = 60
    cache_ex_account: int = 60 * 60
    cache_ex_user: int = 60 * 60
    cache_ex_statechart: int = 60
    cache_ex_referral_link: int = 60 * 60
    cache_ex_content: int = 60 * 60
    cache_ex_role: int = 60 * 60
    cache_ex_question: int = 60
    cache_ex_suggestions: int = 60
    cache_ex_answers: int = 60 * 60
    cache_ex_feedbacks: int = 60 * 60
    cache_ex_match: int = 60 * 60

    check_user_inactivity: bool = True
    check_user_inactivity_time: datetime.time = datetime.time(hour=4)
