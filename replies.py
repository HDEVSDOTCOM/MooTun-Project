"""A bot reply: plain text (also the Flex altText) plus optional card and quick replies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ALT_TEXT_LIMIT: Final = 400


@dataclass(frozen=True)
class Reply:
    text: str
    flex: dict | None = None
    quick_reply: tuple[dict, ...] = ()

    def to_messages(self) -> list[dict]:
        if self.flex is None:
            message: dict = {"type": "text", "text": self.text}
        else:
            alt = self.text if len(self.text) <= ALT_TEXT_LIMIT else self.text[: ALT_TEXT_LIMIT - 1] + "…"
            message = {"type": "flex", "altText": alt, "contents": self.flex}
        if self.quick_reply:
            message["quickReply"] = {"items": list(self.quick_reply)}
        return [message]


def as_reply(value: str | Reply) -> Reply:
    return value if isinstance(value, Reply) else Reply(value)
