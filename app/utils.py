import logging
from functools import lru_cache

from pydantic import BaseModel, validate_model
from rich.console import Console
from rich.logging import RichHandler

__all__ = ["get_logger", "validate"]

console = Console(color_system="256", width=150, style="blue")


@lru_cache()
def get_logger(module_name):
    logger = logging.getLogger(module_name)
    handler = RichHandler(console=console, enable_link_path=False)
    handler.setFormatter(
        logging.Formatter("[ %(threadName)s:%(funcName)s:%(lineno)d ] - %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def validate(model: BaseModel):
    *_, validation_error = validate_model(model.__class__, model.__dict__)
    if validation_error:
        raise validation_error
