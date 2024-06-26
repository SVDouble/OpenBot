from enum import Enum, auto, unique

__all__ = ["BotError", "ValidationError", "PublicError", "AccessDeniedError"]


class BotError(Exception):
    pass


class ValidationError(BotError):
    @unique
    class Code(str, Enum):
        INVALID_VALUE = auto()
        TOO_FEW_ARGS = auto()
        TOO_MANY_ARGS = auto()
        INVALID_FIRST_ARG = auto()
        INVALID_SECOND_ARG = auto()
        INVALID_ORDER = auto()

    def __init__(self, code: Code, message: str = None):
        self.code = code
        self.message = message


class PublicError(BotError):
    pass


class AccessDeniedError(PublicError):
    pass
