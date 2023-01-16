from typing import Any, Generic, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.repository.core import Repository

__all__ = [
    "BaseModelRepository",
    "BaseRoModelRepository",
    "BaseRwModelRepository",
    "ID",
]

ModelClass = TypeVar("ModelClass", bound=BaseModel)
ID = int | str | UUID | ModelClass


class BaseModelRepository(Generic[ModelClass]):
    ex: int | None
    key: str

    def __init__(self, core: Repository):
        self.core = core

    def _make_key(self, id_: ID, **kwargs) -> str:
        return f"{self.key}:{id_}"

    def _make_alias(self, kwargs: dict) -> str:
        def simplify(obj):
            if not isinstance(obj, BaseModel):
                return obj
            if (obj_id := getattr(obj, "id", None)) is None:
                return obj
            return obj_id

        alias = hash(frozenset((k, simplify(v)) for k, v in kwargs.items()))
        return f"{self.key}:alias:{alias}"

    async def save(self, obj: ModelClass, id_: ID = None, **kwargs) -> None:
        key = self._make_key(obj)
        await self.core.set_pickle(key, obj, ex=self.ex)

        if id_ is None and kwargs:
            alias = self._make_alias(kwargs)
            await self.core.db.set(self._make_key(alias), key, ex=self.ex)

    async def load(self, id_: ID | None, **kwargs) -> ModelClass | None:
        if id_ is not None:
            key = self._make_key(id_, **kwargs)
            return await self.core.get_pickle(key)

        alias = self._make_alias(kwargs)
        if key := await self.core.db.get(alias):
            return await self.core.get_pickle(key)

    async def remove(self, id_: ID, **kwargs) -> None:
        key = self._make_key(id_, **kwargs)
        await self.core.remove_pickle(key)


class BaseRoModelRepository(BaseModelRepository[ModelClass]):
    model: Type[ModelClass]
    url: str

    id_field = "id"
    use_deep_retrieval: bool = False

    def _make_url(self, id_: ID | None, **kwargs):
        if id_ is None:
            return f"{self.url}/"
        return f"{self.url}/{id_}/"

    def _make_key(self, id_: ID | None, **kwargs) -> str:
        if id_ is None:
            raise RuntimeError("Cannot make a key without an id")
        if isinstance(id_, self.model):
            id_ = getattr(id_, self.id_field, id_)
        id_ = str(id_)
        return f"{self.key}:{id_!r}"

    def _extract(self, data: Any, id_: ID | None, **kwargs) -> Any:
        if id_ is None or isinstance(data, list):
            return data[0]
        return data

    async def _get_retrieve_kwargs(self, id_: ID | None, **kwargs) -> dict | None:
        return None

    async def _retrieve(self, id_: ID | None = None, **kwargs) -> ModelClass | None:
        request_kwargs = await self._get_retrieve_kwargs(id_, **kwargs) or {}
        response = await self.core.httpx.get(
            self._make_url(id_, **kwargs), **request_kwargs
        )
        if response.is_success and (data := response.json()) is not None:
            if not data:
                return None
            data = self._extract(data, id_, **kwargs)
            if self.use_deep_retrieval and id_ is None:
                new_id = data[self.id_field]
                if new_id is None:
                    raise RuntimeError("Retrieved object does not contain an id")
                return await self._retrieve(data[self.id_field], **kwargs)
            return self.model.parse_obj(data)

    async def get(self, id_: ID | None = None, **kwargs) -> ModelClass | None:
        if (obj := await self.load(id_, **kwargs)) is not None:
            return obj
        if (obj := await self._retrieve(id_, **kwargs)) is not None:
            await self.save(obj)
            return obj


class BaseRwModelRepository(BaseRoModelRepository[ModelClass]):
    async def _get_create_kwargs(self, id_: ID | None, **kwargs) -> dict | None:
        if isinstance(id_, self.model):
            data = id_.json(exclude_none=True)
            headers = {"Content-Type": "application/json"}
            return {"headers": headers, "content": data}
        return None

    async def create(self, id_: ID | None, **kwargs) -> ModelClass:
        request_kwargs = await self._get_create_kwargs(id_, **kwargs) or {}
        if not request_kwargs:
            raise RuntimeError(f"Cannot create {self.model.__name__}: no content given")
        response = await self.core.httpx.post(f"{self.url}/", **request_kwargs)
        response.raise_for_status()
        obj = self.model.parse_obj(response.json())
        await self.save(obj)
        return obj

    async def get_or_create(self, id_: ID | None = None, **kwargs) -> ModelClass:
        if (obj := await self.get(id_, **kwargs)) is not None:
            return obj
        if (obj := await self.create(id_, **kwargs)) is not None:
            return obj
        raise RuntimeError(f"Could not get or create {self.model.__name__}")
