from datetime import datetime
from functools import cached_property, total_ordering
from re import sub
from typing import Any, Callable, Type, Self, Sequence

from pydantic import BaseModel, PrivateAttr

from app.exceptions import ValidationError
from app.models import ContentType as CT, Content
from app.utils import get_settings

__all__ = ["ContentValidator"]

settings = get_settings()


@total_ordering
class ContentValidator(BaseModel):
    class Config:
        keep_untouched = (cached_property,)

    type: CT
    value: Any
    options: Sequence[Any] | None = None
    _payload: Any | None = PrivateAttr(default=None)

    def __lt__(self: Self, other: Self) -> bool:
        order = [
            CT.INTEGER,
            CT.FLOAT,
            CT.NUMBER_RANGE,
            CT.DATE,
            CT.DATE_RANGE,
            CT.BOOLEAN,
            CT.TEXT,
            CT.LOCATION,
            CT.TAG,
            CT.CITY,
            CT.UNIVERSITY,
            CT.PHOTO,
            CT.FILE,
        ]
        return (order.index(self.type), self.value) < (
            order.index(other.type),
            other.value,
        )

    def __eq__(self: Self, other: Any | None) -> bool:
        if not isinstance(other, ContentValidator):
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

    def get_content(self) -> Content:
        payload = self.payload
        type_ = self.type.value
        metadata = None
        if type_ in ("photo", "file"):
            metadata = {
                "file_unique_id": payload.file_unique_id,
                "file_id": payload.file_id,
            }
            payload = payload.get_file().file_path
        return Content(**{"type": type_, type_: payload, "metadata": metadata})

    @cached_property
    def payload(self) -> Any:
        if self._payload is None:
            self.clean()
        return self._payload

    def clean(self):
        codes: Type[ValidationError.Code] = ValidationError.Code

        def require(arg, type_):
            if not isinstance(arg, type_):
                raise ValueError(
                    f"Invalid content type supplied: {type(arg)} (required: {type_})"
                )

        def parse_integer(integer: str) -> int:
            require(integer, str)
            integer = sub("[A-Za-zа-яА-ЯёЁ]", "", integer)
            try:
                return int(integer)
            except ValueError:
                raise ValidationError(codes.INVALID_VALUE)

        def parse_float(float_: str) -> float:
            require(float_, str)
            float_ = sub("[A-Za-zа-яА-ЯёЁ]", "", float_)
            try:
                return float(float_)
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
            case CT.TEXT:
                require(self.value, str)
                self._payload = self.value
            case CT.BOOLEAN:
                require(self.value, bool)
                self._payload = self.value
            case CT.INTEGER:
                if isinstance(self.value, int):
                    self._payload = self.value
                else:
                    self._payload = parse_integer(self.value)
            case CT.FLOAT:
                if isinstance(self.value, float):
                    self._payload = self.value
                else:
                    self._payload = parse_float(self.value)
            case CT.NUMBER_RANGE:
                self._payload = parse_range(parse_float, self.value)
            case CT.DATE:
                self._payload = parse_date(self.value)
            case CT.DATE_RANGE:
                self._payload = parse_range(parse_date, self.value)
            case CT.LOCATION:
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
