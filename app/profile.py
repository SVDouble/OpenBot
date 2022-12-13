from typing import Any

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    BigInteger,
    DateTime,
    func,
)
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

from app.utils import get_settings

__all__ = ["Session", "get_profile", "reload_profile_class"]

settings = get_settings()

engine = create_engine(settings.postgres_url)
Session = sessionmaker(engine)

meta = MetaData()
table_name = f"profiles@{settings.bot_username}"
table = Table(
    table_name,
    meta,
    Column(
        "telegram_id",
        BigInteger,
        nullable=False,
        primary_key=True,
    ),
    Column(
        "time_created",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column(
        "time_updated",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
)
meta.create_all(engine)

Profile: Any | None = None


def reload_profile_class():
    global Profile
    base = automap_base()
    base.prepare(autoload_with=engine)
    Profile = getattr(base.classes, table_name)


reload_profile_class()


def get_profile(session: Session, telegram_id: int):
    profile = session.query(Profile).get(telegram_id)
    if profile is None:
        profile = Profile(telegram_id=telegram_id)
        session.add(profile)
    return profile
