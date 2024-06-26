from typing import Any, Generic, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel, TypeAdapter

from app.repository.core import Repository
from app.utils import get_logger, get_settings

__all__ = [
    "BaseModelRepository",
    "BaseRoModelRepository",
    "BaseRwModelRepository",
    "ID",
]

logger = get_logger(__file__)
settings = get_settings()

ModelClass = TypeVar("ModelClass", bound=BaseModel)
ID = int | str | UUID | ModelClass


class BaseModelRepository(Generic[ModelClass]):
    model: Type[ModelClass]
    id_field = "id"
    ex: int | None
    key: str

    def __init__(self, core: Repository):
        self.core = core

    @staticmethod
    def _extract_id(id_: ID) -> str:
        if not isinstance(id_, BaseModel):
            return str(id_)
        if (obj_id := getattr(id_, "id", None)) is None:
            return str(id_)
        return str(obj_id)

    def _make_key(self, id_: ID | list[ID] | None, **kwargs) -> str:
        if id_ is None:
            raise RuntimeError("Cannot make a key without an id")
        if isinstance(id_, list):
            id_ = self._make_ref(kwargs)
            return f"{self.key}:list[{id_}]"
        id_ = self._extract_id(id_)
        return f"{self.key}:id[{id_}]"

    def _make_ref(self, kwargs: dict) -> str:
        ref = hash(frozenset((k, self._extract_id(v)) for k, v in kwargs.items()))
        return f"{self.key}:ref[{ref}]"

    async def save(
        self, obj: ModelClass | list[ModelClass], id_: ID = None, **kwargs
    ) -> None:
        key = self._make_key(obj, **kwargs)
        await self.core.set_pickle(key, obj, ex=self.ex)

        if id_ is None and kwargs:
            ref = self._make_ref(kwargs)
            await self.core.db.set(ref, key, ex=self.ex)

    async def load(self, id_: ID | None, **kwargs) -> ModelClass | None:
        key = None
        if id_ is not None:
            key = self._make_key(id_, **kwargs)
        elif ref := self._make_ref(kwargs):
            key = await self.core.db.get(ref)
        if key:
            return await self.core.get_pickle(key)

    async def remove(self, id_: ID | None, **kwargs) -> None:
        key = self._make_key(id_, **kwargs)
        await self.core.remove_pickle(key)


class BaseRoModelRepository(BaseModelRepository[ModelClass]):
    url: str

    def _make_url(self, id_: ID | None, **kwargs):
        if id_ is None:
            return f"{self.url}/"
        return f"{self.url}/{id_}/"

    def _extract(
        self, data: Any, id_: ID | None, *, many: bool = False, **kwargs
    ) -> Any:
        if many:
            return data
        if isinstance(data, list):
            return data[0]
        return data

    async def _get_retrieve_kwargs(
        self, id_: ID | None, *, context: dict = None, many: bool = False, **kwargs
    ) -> dict | None:
        params = kwargs
        if id_ is None:
            params["bot"] = settings.bot_id
        return {"params": params}

    async def _retrieve(
        self,
        id_: ID | None = None,
        *,
        context: dict = None,
        many: bool = False,
        **kwargs,
    ) -> ModelClass | list[ModelClass] | None:
        request_kwargs = await self._get_retrieve_kwargs(
            id_, context=context, many=many, **kwargs
        )
        if id_ is None and not request_kwargs:
            return None
        response = await self.core.httpx.get(
            self._make_url(id_, **kwargs), **(request_kwargs or {})
        )
        if response.is_success and (data := response.json()) is not None:
            if not data:
                return None
            data = self._extract(data, id_, many=many, **kwargs)
            parse_as_type = list[self.model] if isinstance(data, list) else self.model
            return TypeAdapter(parse_as_type).validate_python(data)

    async def get(
        self,
        id_: ID | None = None,
        *,
        context: dict = None,
        many: bool = False,
        **kwargs,
    ) -> ModelClass | list[ModelClass] | None:
        if (obj := await self.load(id_, **kwargs)) is not None:
            return obj
        obj = await self._retrieve(id_, context=context, many=many, **kwargs)
        if obj is not None:
            if not many:
                await self.save(obj, id_, **kwargs)
            return obj
        if many:
            return []
        return None


class BaseRwModelRepository(BaseRoModelRepository[ModelClass]):
    async def _get_create_kwargs(
        self, id_: ID | None, *, context: dict = None, **kwargs
    ) -> dict | None:
        if isinstance(id_, self.model):
            data = id_.model_dump_json(exclude_none=True, by_alias=True)
            headers = {"Content-Type": "application/json"}
            return {"headers": headers, "content": data}
        return None

    async def create(
        self, id_: ID | None, *, context: dict = None, **kwargs
    ) -> ModelClass:
        request_kwargs = (
            await self._get_create_kwargs(id_, context=context, **kwargs) or {}
        )
        if not request_kwargs:
            raise RuntimeError(f"Cannot create {self.model.__name__}: no content given")
        response = await self.core.httpx.post(f"{self.url}/", **request_kwargs)
        response.raise_for_status()
        obj = self.model.model_validate(response.json())
        await self.save(obj, id_, **kwargs)
        return obj

    async def get_or_create(
        self, id_: ID | None = None, *, context: dict = None, **kwargs
    ) -> ModelClass:
        if (obj := await self.get(id_, context=context, **kwargs)) is not None:
            return obj
        if (obj := await self.create(id_, context=context, **kwargs)) is not None:
            return obj
        raise RuntimeError(f"Could not get or create {self.model.__name__}")

    async def _get_patch_kwargs(self, obj: ModelClass) -> dict | None:
        new_data = self.model.model_validate_json(
            obj.model_dump_json(exclude_none=True)
        ).model_dump()
        old_data = (old_obj := await self.load(obj)) and old_obj.model_dump() or {}
        if keys := {k for k, v in new_data.items() if v != old_data.get(k)}:
            return {
                "headers": {"Content-Type": "application/json"},
                "content": obj.model_dump_json(include=keys),
            }

    async def patch(self, obj: ModelClass) -> ModelClass:
        if not (request_kwargs := await self._get_patch_kwargs(obj)):
            return obj
        path = f"{self.url}/{getattr(obj, self.id_field)}/"
        response = await self.core.httpx.patch(path, **request_kwargs)
        response.raise_for_status()
        obj = self.model.model_validate(response.json())
        await self.save(obj)
        return obj

    async def _get_delete_kwargs(
        self, id_: ID, *, context: dict = None, **kwargs
    ) -> dict | None:
        return None

    async def delete(self, id_: ID, context: dict = None, **kwargs) -> None:
        if isinstance(id_, self.model):
            id_ = getattr(id_, self.id_field)
        requests_kwargs = await self._get_delete_kwargs(id_, context=context, **kwargs)
        requests_kwargs = requests_kwargs or {}
        response = await self.core.httpx.delete(f"{self.url}/{id_}/", **requests_kwargs)
        # ignore if the object has already been deleted
        if response.status_code != 404:
            response.raise_for_status()
        await self.remove(id_)
