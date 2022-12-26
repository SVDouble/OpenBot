from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    MetaData,
    Table,
    create_engine,
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
table_name = f"profiles@{settings.bot.username}"
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
        "date_created",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column(
        "date_modified",
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
