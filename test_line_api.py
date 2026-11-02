from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from line_api import LineAPIError, LinePayloadError, reply_messages, reply_text, start_loading

TOKEN = "secret-access-token-xyz"


def _client(status: int = 200, body: dict | None = None):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json=body or {})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


def test_reply_messages_posts_payload():
    client, calls = _client()
    messages = [{"type": "text", "text": "a"}, {"type": "flex", "altText": "b", "contents": {"type": "bubble"}}]
    asyncio.run(reply_messages("rt", messages, TOKEN, client=client))
    assert calls[0].url.path == "/v2/bot/message/reply"
    assert json.loads(calls[0].content) == {"replyToken": "rt", "messages": messages}
    assert calls[0].headers["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize("messages", [[], [{"type": "text", "text": "x"}] * 6, [{"text": "no type"}], ["x"]])
def test_reply_messages_rejects_bad_lists(messages):
    client, calls = _client()
    with pytest.raises(LinePayloadError):
        asyncio.run(reply_messages("rt", messages, TOKEN, client=client))
    assert calls == []


def test_reply_text_still_sends_single_text():
    client, calls = _client()
    asyncio.run(reply_text("rt", "สวัสดี", TOKEN, client=client))
    assert json.loads(calls[0].content)["messages"] == [{"type": "text", "text": "สวัสดี"}]


def test_start_loading_payload():
    client, calls = _client(202)
    asyncio.run(start_loading("U1", TOKEN, client=client))
    assert calls[0].url.path == "/v2/bot/chat/loading/start"
    assert json.loads(calls[0].content) == {"chatId": "U1", "loadingSeconds": 5}


def test_start_loading_error_has_no_token():
    client, _ = _client(500, {"message": "boom"})
    with pytest.raises(LineAPIError) as error:
        asyncio.run(start_loading("U1", TOKEN, client=client))
    assert TOKEN not in str(error.value)


def test_start_loading_requires_user_and_token():
    with pytest.raises(LineAPIError):
        asyncio.run(start_loading("", TOKEN))
    with pytest.raises(LineAPIError):
        asyncio.run(start_loading("U1", ""))
