from functools import lru_cache

from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, NUMRANGE, TSTZRANGE
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

from app.models import ContentType
from app.utils import get_settings

__all__ = ["Session", "get_profile", "get_profile_class", "content_type_to_column"]

settings = get_settings()

engine = create_engine(settings.postgres_url)
Session = sessionmaker(engine)

content_type_to_column = {
    ContentType.TEXT: Text,
    ContentType.INTEGER: Integer,
    ContentType.FLOAT: Float,
    ContentType.NUMBER_RANGE: NUMRANGE,
    ContentType.DATE: DateTime,
    ContentType.DATE_RANGE: TSTZRANGE,
    ContentType.LOCATION: JSONB,
    ContentType.TAG: UUID,
    ContentType.CITY: UUID,
    ContentType.UNIVERSITY: UUID,
    ContentType.PHOTO: Text,
    ContentType.FILE: Text,
}


def add_column(table_name, column):
    column_name = column.compile(dialect=engine.dialect)
    column_type = column.type.compile(engine.dialect)
    engine.execute(
        "ALTER TABLE %s ADD COLUMN %s %s" % (table_name, column_name, column_type)
    )


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
