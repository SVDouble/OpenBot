from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import ruamel.yaml
from pydantic import BaseModel, Field, ValidationError, validator

__all__ = [
    "Event",
    "Contract",
    "Transition",
    "State",
    "StatechartDefinition",
    "Statechart",
]


class Event(BaseModel):
    class Scope(str, Enum):
        INTERNAL = "internal"
        INCOMING = "incoming"
        OUTGOING = "outgoing"

    name: str
    scope: Scope = Scope.INTERNAL
    value: Any


class Contract(BaseModel):
    before: str | None
    after: str | None
    always: str | None

    @validator("*", pre=True)
    def allow_one_key(cls, v: dict):
        if sum(value is not None for value in v.values()) != 1:
            raise ValidationError("Only one key must be specified")
        return v


class Transition(BaseModel):
    target: str | None
    event: str | None
    guard: str | None
    action: str | None
    contract: list[Contract] = Field(default_factory=list)
    priority: int | Literal["high", "low"] | None


class State(BaseModel):
    name: str
    type: Literal["final", "shallow history", "deep history"] | None
    on_entry: str | None = Field(alias="on entry")
    on_exit: str | None = Field(alias="on exit")
    transitions: list[Transition] = Field(default_factory=list)
    contract: list[Contract] = Field(default_factory=list)
    initial: str | None
    parallel_states: list["State"] = Field(
        alias="parallel states", default_factory=list
    )
    states: list["State"] = Field(default_factory=list)
    memory: str | None


class StatechartDefinition(BaseModel):
    name: str
    preamble: str | None
    root_state: State = Field(alias="root state")

    @classmethod
    def load(cls, path: Path):
        with open(path) as f:
            data = ruamel.yaml.YAML(typ="safe", pure=True).load(f)
        return cls.parse_obj(data)


class Statechart(BaseModel):
    id: UUID
    bot: UUID
    name: str
    code: StatechartDefinition
