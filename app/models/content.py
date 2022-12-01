from datetime import datetime
from enum import unique, Enum
from functools import cached_property, total_ordering
from re import sub
from typing import Any, Callable, Type, Self, Sequence

from pydantic import BaseModel, PrivateAttr

from app.exceptions import ValidationError
from app.utils import get_settings

__all__ = ["Content"]

settings = get_settings()


@total_ordering
class Content(BaseModel):
    class Config:
        keep_untouched = (cached_property,)

    @unique
    class Type(str, Enum):
        TEXT = "text"
        BOOLEAN = "boolean"
        NUMBER = "number"
        NUMBER_RANGE = "number_range"
        DATE = "date"
        DATE_RANGE = "date_range"
        LOCATION = "location"
        TAG = "tag"
        CITY = "city"
        UNIVERSITY = "university"
        PHOTO = "photo"
        FILE = "file"

    type: Type
    value: Any
    options: Sequence[Any] | None = None
    _payload: Any | None = PrivateAttr(default=None)

    def __lt__(self: Self, other: Self) -> bool:
        order = [
            self.Type.NUMBER,
            self.Type.NUMBER_RANGE,
            self.Type.DATE,
            self.Type.DATE_RANGE,
            self.Type.BOOLEAN,
            self.Type.TEXT,
            self.Type.LOCATION,
            self.Type.TAG,
            self.Type.CITY,
            self.Type.UNIVERSITY,
            self.Type.PHOTO,
            self.Type.FILE,
        ]
        return (order.index(self.type), self.value) < (
            order.index(other.type),
            other.value,
        )

    def __eq__(self: Self, other: Any | None) -> bool:
        if not isinstance(other, Content):
            return False

        if self.type != other.type:
            return False

        try:
            return self.payload == other.payload
        except ValidationError:
            return self.value == other.value

    def __hash__(self):
        try:
            return hash((self.type, self.payload))
        except ValidationError:
            return hash((self.type, self.value))

    def dehydrate(self) -> dict:
        payload = self.payload
        type_ = self.type.value

        if type_ in ("photo", "file"):
            return {
                "type": type_,
                f"{type_}_url": payload.get_file().file_path,
                "metadata": {
                    "file_unique_id": payload.file_unique_id,
                    "file_id": payload.file_id,
                    "bot": settings.bot.username,
                },
            }

        if isinstance(payload, datetime):
            payload = payload.isoformat()
        return {"type": type_, type_: payload}

    @cached_property
    def payload(self) -> Any:
        if self._payload is None:
            self.clean()
        return self._payload

    def clean(self):
        ct: Type[Content.Type] = Content.Type
        codes: Type[ValidationError.Code] = ValidationError.Code

        def require(arg, type_):
            if not isinstance(arg, type_):
                raise ValueError(
                    f"Invalid content type supplied: {type(arg)} (required: {type_})"
                )

        def parse_number(number: str) -> float:
            require(number, str)
            number = sub("[A-Za-zа-яА-ЯёЁ]", "", number)
            try:
                return float(number)
            except ValueError:
                raise ValidationError(codes.INVALID_VALUE)

        def parse_date(date_: str) -> datetime:
            require(date_, str)
            patterns = ["%d.%m.%Y", "%m.%Y", "%Y"]
            for pattern in patterns:
                try:
                    return datetime.strptime(date_, pattern)
                except ValueError:
                    continue
            raise ValidationError(codes.INVALID_VALUE)

        def parse_range(parse_arg: Callable[[str], Any], range_: str) -> dict:
            require(range_, str)
            # handle the case when only upper bound is specified
            try:
                upper = parse_arg(range_)
            except ValidationError:
                pass
            else:
                if upper <= 0:
                    raise ValidationError(codes.INVALID_VALUE)
                return dict(lower=upper, upper=upper, bounds="[]")

            try:
                lower, upper, *garbage = range_.split("-")
            except ValueError:
                raise ValidationError(codes.TOO_FEW_ARGS)
            if len(garbage) > 0:
                raise ValidationError(codes.TOO_MANY_ARGS)
            try:
                lower = parse_arg(lower)
            except ValidationError as exc:
                raise ValidationError(codes.INVALID_FIRST_ARG) from exc
            try:
                upper = parse_arg(upper)
            except ValidationError as exc:
                raise ValidationError(codes.INVALID_SECOND_ARG) from exc
            if lower > upper:
                raise ValidationError(codes.INVALID_ORDER)
            elif lower <= 0:
                raise ValidationError(codes.INVALID_VALUE)
            return dict(lower=lower, upper=upper, bounds="[]")

        match self.type:
            case ct.TEXT:
                require(self.value, str)
                self._payload = self.value
            case ct.BOOLEAN:
                require(self.value, bool)
                self._payload = self.value
            case ct.NUMBER:
                if isinstance(self.value, int | float):
                    self._payload = self.value
                else:
                    self._payload = parse_number(self.value)
            case ct.NUMBER_RANGE:
                self._payload = parse_range(parse_number, self.value)
            case ct.DATE:
                self._payload = parse_date(self.value)
            case ct.DATE_RANGE:
                self._payload = parse_range(parse_date, self.value)
            case ct.LOCATION:
                loc = self.value
                if not (
                    isinstance(loc, dict)
                    and loc.keys() == {"longitude", "latitude"}
                    and all(isinstance(value, float) for value in loc.values())
                ):
                    raise ValidationError(codes.INVALID_VALUE)
                self._payload = loc
            case _:
                # TODO: check university, city and tag types
                self._payload = self.value

        if self._payload is None:
            raise ValidationError(codes.INVALID_VALUE)

        if self.options is not None and self._payload not in self.options:
            raise ValidationError(codes.INVALID_VALUE)
