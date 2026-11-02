"""Test double for the LINE send functions used by app.py (not imported by the app)."""

from __future__ import annotations


def visible_text(messages: list[dict]) -> str:
    """What a user sees first: Flex altText or the text of the last message."""

    last = messages[-1]
    return last.get("altText") or last.get("text", "")


def text_sender(send_text):
    """Adapt a ``(reply_token, text, token)`` fake into a ``reply_messages`` stand-in."""

    async def send(reply_token: str, messages: list[dict], token: str) -> None:
        await send_text(reply_token, visible_text(messages), token)

    return send


class LineRecorder:
    """Records every reply as ``(reply_token, visible_text, access_token)``.

    ``messages`` keeps the full message lists; ``loading`` the user ids passed to
    ``start_loading``.  ``fail_times`` makes the first N sends raise ``error``.
    """

    def __init__(self, replies: list | None = None, *, fail_times: int = 0, error: Exception | None = None):
        self.replies = replies if replies is not None else []
        self.messages: list[list[dict]] = []
        self.loading: list[str] = []
        self.attempts: list[tuple[str, str, str]] = []
        self.fail_times = fail_times
        self.error = error

    async def _record(self, reply_token: str, messages: list[dict], token: str) -> None:
        entry = (reply_token, visible_text(messages), token)
        self.attempts.append(entry)
        if len(self.attempts) <= self.fail_times:
            raise self.error
        self.replies.append(entry)
        self.messages.append(messages)

    async def reply_text(self, reply_token: str, text: str, token: str) -> None:
        await self._record(reply_token, [{"type": "text", "text": text}], token)

    async def reply_messages(self, reply_token: str, messages: list[dict], token: str) -> None:
        await self._record(reply_token, messages, token)

    async def start_loading(self, user_id: str, token: str, **_: object) -> None:
        self.loading.append(user_id)

    def install(self, monkeypatch, app_module) -> "LineRecorder":
        monkeypatch.setattr(app_module, "reply_text", self.reply_text, raising=False)
        monkeypatch.setattr(app_module, "reply_messages", self.reply_messages, raising=False)
        monkeypatch.setattr(app_module, "start_loading", self.start_loading, raising=False)
        return self
