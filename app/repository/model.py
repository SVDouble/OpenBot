from typing import Any, Generic, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.repository.core import Repository

__all__ = ["BaseModelRepository", "BaseRoModelRepository", "BaseRwModelRepository"]

ModelClass = TypeVar("ModelClass", bound=BaseModel)


class BaseModelRepository(Generic[ModelClass]):
    ex: int | None
    key: str

    def __init__(self, core: Repository):
        self.core = core

    def _make_key(self, id_: int | str | UUID, **kwargs) -> str:
        return f"{self.key}:{id_}"

    async def save(self, obj: ModelClass) -> None:
        key = self._make_key(obj)
        await self.core.set_pickle(key, obj, ex=self.ex)

    async def load(
        self, id_: int | str | UUID | ModelClass, **kwargs
    ) -> ModelClass | None:
        key = self._make_key(id_, **kwargs)
        return await self.core.get_pickle(key)

    async def remove(self, id_: int | str | UUID | ModelClass, **kwargs) -> None:
        key = self._make_key(id_, **kwargs)
        await self.core.remove_pickle(key)


class BaseRoModelRepository(BaseModelRepository[ModelClass]):
    model: Type[ModelClass]
    url: str

    id_field = "id"

    def _make_url(self, id_: int | str | UUID | ModelClass, **kwargs):
        return f"{self.url}/{id_}/"

    def _make_key(self, id_: int | str | UUID | ModelClass, **kwargs) -> str:
        if isinstance(id_, self.model):
            id_ = getattr(id_, self.id_field)
        id_ = str(id_)
        return f"{self.key}:{id_!r}"

    async def _extract(self, data: Any) -> Any:
        if isinstance(data, list):
            return data[0]
        return data

    async def _get_retrieve_kwargs(
        self, id_: int | str | UUID | ModelClass, **kwargs
    ) -> dict:
        return {}

    async def _retrieve(
        self, id_: int | str | UUID | ModelClass, **kwargs
    ) -> ModelClass | None:
        request_kwargs = await self._get_retrieve_kwargs(id_, **kwargs)
        response = await self.core.httpx.get(
            self._make_url(id_, **kwargs), **request_kwargs
        )
        if response.is_success and (data := response.json()) is not None:
            return self.model.parse_obj(await self._extract(data))

    async def get(
        self, id_: int | str | UUID | ModelClass, **kwargs
    ) -> ModelClass | None:
        if (obj := await self.load(id_, **kwargs)) is not None:
            return obj
        if (obj := await self._retrieve(id_, **kwargs)) is not None:
            await self.save(obj)
            return obj
        raise RuntimeError(f"Could not get {self.model.__name__}")


class BaseRwModelRepository(BaseRoModelRepository[ModelClass]):
    async def _get_create_kwargs(
        self, id_: int | str | UUID | ModelClass, **kwargs
    ) -> dict:
        return {}

    async def create(self, id_: int | str | UUID | ModelClass, **kwargs) -> ModelClass:
        request_kwargs = await self._get_create_kwargs(id_, **kwargs)
        response = await self.core.httpx.post(f"{self.url}/", **request_kwargs)
        response.raise_for_status()
        return self.model.parse_obj(response.json())

    async def get_or_create(
        self, id_: int | str | UUID | ModelClass, **kwargs
    ) -> ModelClass:
        if (obj := await self.get(id_, **kwargs)) is not None:
            return obj
        if (obj := await self.create(id_, **kwargs)) is not None:
            await self.save(obj)
            return obj
        raise RuntimeError(f"Could not create {self.model.__name__}")
