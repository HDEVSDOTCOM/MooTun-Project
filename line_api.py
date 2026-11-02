"""Small, framework-independent helpers for the LINE Messaging API."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Final

import httpx


LINE_REPLY_ENDPOINT: Final = "https://api.line.me/v2/bot/message/reply"
LINE_LOADING_ENDPOINT: Final = "https://api.line.me/v2/bot/chat/loading/start"
LINE_TEXT_LIMIT: Final = 5_000
LINE_MESSAGES_PER_REPLY: Final = 5


class LineAPIError(RuntimeError):
    """Base class for errors raised while talking to LINE."""


class LineConfigurationError(LineAPIError):
    """A required LINE credential or request value is missing."""


class LinePayloadError(LineAPIError):
    """A reply cannot be sent because its payload is invalid."""


class LineTransportError(LineAPIError):
    """LINE could not be reached."""


class LineRequestError(LineAPIError):
    """LINE rejected an otherwise valid HTTP request."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        message = f"LINE reply request failed with status {status_code}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)


def verify_webhook_signature(
    body: bytes,
    signature: str,
    channel_secret: str,
) -> bool:
    """Return whether ``signature`` authenticates the exact webhook ``body``.

    The raw bytes from the request must be passed without JSON re-encoding.  A
    missing channel secret is a deployment error, while a missing or malformed
    signature is simply an unauthenticated request and returns ``False``.
    """

    if not channel_secret:
        raise LineConfigurationError("LINE channel secret is not configured")
    if not signature:
        return False

    expected = base64.b64encode(
        hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("ascii")
    return hmac.compare_digest(expected, signature)


# A short alias keeps webhook handlers readable.
is_valid_signature = verify_webhook_signature


async def reply_text(
    reply_token: str,
    text: str,
    channel_access_token: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 10.0,
) -> None:
    """Reply to one webhook event with a LINE text message.

    Supplying ``client`` lets the application reuse a connection pool and makes
    the function straightforward to test.  Credentials never appear in raised
    configuration errors or API-error details.
    """

    if not channel_access_token:
        raise LineConfigurationError("LINE channel access token is not configured")
    if not reply_token:
        raise LinePayloadError("LINE reply token is required")
    if not isinstance(text, str) or not text.strip():
        raise LinePayloadError("LINE reply text must not be empty")
    if len(text) > LINE_TEXT_LIMIT:
        raise LinePayloadError(
            f"LINE reply text exceeds the {LINE_TEXT_LIMIT}-character limit"
        )
    await reply_messages(
        reply_token,
        [{"type": "text", "text": text}],
        channel_access_token,
        client=client,
        timeout=timeout,
    )


async def reply_messages(
    reply_token: str,
    messages: list[dict],
    channel_access_token: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 10.0,
) -> None:
    """Reply with 1-5 prepared LINE message objects (text, Flex, quick replies)."""

    if not channel_access_token:
        raise LineConfigurationError("LINE channel access token is not configured")
    if not reply_token:
        raise LinePayloadError("LINE reply token is required")
    if not isinstance(messages, list) or not 1 <= len(messages) <= LINE_MESSAGES_PER_REPLY:
        raise LinePayloadError(f"LINE reply needs 1-{LINE_MESSAGES_PER_REPLY} messages")
    if not all(isinstance(message, dict) and isinstance(message.get("type"), str) for message in messages):
        raise LinePayloadError("LINE reply messages must be objects with a type")
    await _post(
        LINE_REPLY_ENDPOINT,
        {"replyToken": reply_token, "messages": messages},
        channel_access_token,
        client=client,
        timeout=timeout,
    )


async def start_loading(
    user_id: str,
    channel_access_token: str,
    *,
    seconds: int = 5,
    client: httpx.AsyncClient | None = None,
    timeout: float = 2.0,
) -> None:
    """Show LINE's "..." loading indicator in a one-to-one chat."""

    if not channel_access_token:
        raise LineConfigurationError("LINE channel access token is not configured")
    if not user_id:
        raise LinePayloadError("LINE user id is required")
    await _post(
        LINE_LOADING_ENDPOINT,
        {"chatId": user_id, "loadingSeconds": seconds},
        channel_access_token,
        client=client,
        timeout=timeout,
    )


async def _post(
    url: str,
    payload: dict,
    channel_access_token: str,
    *,
    client: httpx.AsyncClient | None,
    timeout: float,
) -> None:
    headers = {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json",
    }

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=timeout)
    try:
        try:
            response = await active_client.post(
                url,
                headers=headers,
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise LineTransportError("Could not reach LINE Messaging API") from exc

        if response.is_error:
            # LINE's short error message is useful for debugging.  Do not copy
            # request headers or payloads because they contain credentials and
            # one-time reply tokens.
            detail = _safe_error_detail(response)
            raise LineRequestError(response.status_code, detail)
    finally:
        if owns_client:
            await active_client.aclose()


def _safe_error_detail(response: httpx.Response) -> str:
    """Extract LINE's public error message without reflecting request data."""

    try:
        body = response.json()
    except (ValueError, TypeError):
        return ""
    if not isinstance(body, dict):
        return ""
    message = body.get("message")
    return message[:300] if isinstance(message, str) else ""
