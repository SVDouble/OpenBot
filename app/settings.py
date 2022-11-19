from functools import lru_cache
from pathlib import Path

from pydantic import BaseSettings

from app.utils import get_logger

__all__ = ["Settings", "get_settings"]

logger = get_logger(__name__)


class Settings(BaseSettings):
    class Config:
        env_file = ".env"

    title: str = "EasyBot"
    version: str = "v0.1.0"
    project_root: Path = Path(__file__).parent.parent


@lru_cache()
def get_settings() -> Settings:
    return Settings()
