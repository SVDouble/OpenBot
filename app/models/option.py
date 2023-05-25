from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.content import Content
from app.utils import get_settings

__all__ = ["Option"]

settings = get_settings()


class Option(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    bot: UUID = settings.bot_id
    name: str
    emoji: str = ""
    label: str = ""
    content: Content
    is_dynamic: bool = False

    row: int
    column: int

    is_active: bool = Field(default=False, exclude=True)
    is_dummy: bool = Field(default=False, exclude=True)

    def __init__(self, **kwargs):
        if "content" not in kwargs:
            kwargs["content"] = Content(type="text", text=kwargs["name"])
        super().__init__(**kwargs)

    def __str__(self):
        prefix = f"{self.prefix} " if self.prefix else ""
        return f"{prefix}{self.name}"

    def __len__(self):
        return len(self.name) + 2

    @property
    def prefix(self):
        if self.is_active:
            return "✅"
        return self.emoji

    async def generate_content(self, cache, repo) -> Content | None:
        from app.engine.logic import render_template
        from app.models import ContentType, ContentValidator

        match self.content.type:
            case ContentType.TEXT:
                text = await render_template(cache, repo, self.content.text)
                return Content(owner=cache.user.id, type=self.content.type, text=text)
            case ContentType.PHOTO:
                # use metadata to fetch image from the source
                if (metadata := self.content.metadata) and (
                    source := metadata.get("source")
                ):
                    if isinstance(source, dict) and source.get("type") == "profile":
                        tg_context = cache.interpreter.context.get("tg_context")
                        if tg_context is None:
                            raise ValueError("Telegram context not found")
                        profile_photo = await cache.user.get_profile_photo(tg_context)
                        if profile_photo:
                            validator = ContentValidator(
                                type=self.content.type, value=profile_photo[-1]
                            )
                            return await validator.get_content()
                        raise ValueError("Profile picture not found")

        raise RuntimeError("Only dynamic options with text are supported at the moment")
