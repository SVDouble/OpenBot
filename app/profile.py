from functools import lru_cache

from sqlalchemy import UUID, Column, DateTime, MetaData, Table, create_engine, func
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

from app.utils import get_settings

__all__ = ["Session", "get_profile"]

settings = get_settings()

engine = create_engine(settings.postgres_url)
Session = sessionmaker(engine)


@lru_cache()
def get_profile_class(role: str):
    meta = MetaData()
    table_name = f"{role}@{settings.bot.username}"
    table = Table(
        table_name,
        meta,
        Column(
            "id",
            UUID,
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
    meta.create_all(engine, tables=[table])
    base = automap_base()
    base.prepare(autoload_with=engine)
    return getattr(base.classes, table_name)


def get_profile(session: Session, role: str, user_id: UUID):
    class_ = get_profile_class(role)
    profile = session.query(class_).get(user_id)
    if profile is None:
        profile = class_(id=user_id)
        session.add(profile)
    return profile
