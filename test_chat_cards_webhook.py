"""Webhook behaviour for chat cards, postbacks, quick replies and loading."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app as app_module
from database import configure_database
from line_api import LineTransportError
from line_fakes import LineRecorder
from messages import HELP_TOPIC_TEXT, format_already_deleted, format_undo_button_expired
from models import PendingTransaction, ProcessedWebhookEvent, Transaction

SECRET = "cards-secret"


@pytest.fixture()
def bot(tmp_path, monkeypatch):
    engine = configure_database(f"sqlite:///{tmp_path / 'cards-webhook.db'}")
    monkeypatch.setattr(app_module, "LINE_CHANNEL_SECRET", SECRET)
    monkeypatch.setattr(app_module, "LINE_CHANNEL_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setenv("MINIAPP_DEVELOPING_LIFF_ID", "123-abc")
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    line = LineRecorder().install(monkeypatch, app_module)
    with TestClient(app_module.app) as client:
        yield client, engine, line
    engine.dispose()


def _post(client, *events):
    body = json.dumps({"events": list(events)}, ensure_ascii=False, separators=(",", ":")).encode()
    signature = base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()
    return client.post("/webhook", content=body,
                       headers={"content-type": "application/json", "x-line-signature": signature})


def _source(user):
    return {"type": "user", "userId": user}


def text(event_id, message, user="U-a"):
    return {"type": "message", "webhookEventId": event_id, "timestamp": 1_793_500_000_000,
            "replyToken": f"rt-{event_id}", "source": _source(user),
            "message": {"type": "text", "id": f"m-{event_id}", "text": message}}


def postback(event_id, data, user="U-a"):
    return {"type": "postback", "webhookEventId": event_id, "timestamp": 1_793_500_000_000,
            "replyToken": f"rt-{event_id}", "source": _source(user), "postback": {"data": data}}


def follow(event_id, user="U-a"):
    return {"type": "follow", "webhookEventId": event_id, "timestamp": 1_793_500_000_000,
            "replyToken": f"rt-{event_id}", "source": _source(user)}


def _last(line) -> dict:
    return line.messages[-1][-1]


def _datas(message) -> list[str]:
    found = []

    def walk(node):
        if isinstance(node, dict):
            action = node.get("action")
            if isinstance(action, dict) and "data" in action:
                found.append(action["data"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(message)
    return found


def _only_tx(engine):
    with Session(engine) as session:
        return list(session.scalars(select(Transaction)))


def test_record_reply_is_flex_with_alt_text(bot):
    client, engine, line = bot
    assert _post(client, text("e1", "ข้าวมันไก่ 50")).status_code == 200
    message = _last(line)
    assert message["type"] == "flex"
    assert message["altText"].startswith("✅ จดแล้ว! รายจ่าย 50 บาท")
    tx = _only_tx(engine)[0]
    assert f"a=del&t={tx.id}" in _datas(message)
    assert "https://liff.line.me/123-abc/transactions" in json.dumps(message)


def test_postback_delete_then_undo_end_to_end(bot):
    client, engine, line = bot
    _post(client, text("e1", "ข้าว 50"))
    tx_id = _only_tx(engine)[0].id
    assert _post(client, postback("e2", f"a=del&t={tx_id}")).status_code == 200
    deleted = _last(line)
    assert deleted["type"] == "flex" and "line-through" in json.dumps(deleted)
    assert _only_tx(engine) == []
    undo = next(d for d in _datas(deleted) if d.startswith("a=undo&id="))
    assert _post(client, postback("e3", undo)).status_code == 200
    restored = _last(line)
    assert restored["type"] == "flex" and "เอาคืนมาแล้ว" in json.dumps(restored, ensure_ascii=False)
    assert [t.id for t in _only_tx(engine)] == [tx_id]


def test_double_delete_postback_second_reports_already_deleted(bot):
    client, engine, line = bot
    _post(client, text("e1", "ข้าว 50"))
    tx_id = _only_tx(engine)[0].id
    _post(client, postback("e2", f"a=del&t={tx_id}"))
    _post(client, postback("e3", f"a=del&t={tx_id}"))
    assert line.replies[-1][1] == format_already_deleted()


def test_stale_undo_button_does_not_restore_other_deletion(bot):
    client, engine, line = bot
    _post(client, text("e1", "ข้าว 50"))
    _post(client, text("e2", "กาแฟ 40"))
    first, second = [t.id for t in _only_tx(engine)]
    _post(client, postback("e3", f"a=del&t={first}"))
    stale = next(d for d in _datas(_last(line)) if d.startswith("a=undo"))
    _post(client, postback("e4", f"a=del&t={second}"))
    _post(client, postback("e5", stale))
    assert line.replies[-1][1] == format_undo_button_expired()
    assert _only_tx(engine) == []


def test_other_users_transaction_id_is_not_found(bot):
    client, engine, line = bot
    _post(client, text("e1", "ข้าว 50", user="U-a"))
    tx_id = _only_tx(engine)[0].id
    _post(client, postback("e2", f"a=del&t={tx_id}", user="U-b"))
    assert line.replies[-1][1] == format_already_deleted()
    assert len(_only_tx(engine)) == 1


@pytest.mark.parametrize("data", ["richmenu=compose", "richmenu=page2", "a=del&t=abc"])
def test_rich_menu_postback_claimed_without_reply(bot, data):
    client, engine, line = bot
    assert _post(client, postback("e1", data)).status_code == 200
    assert line.replies == []
    with Session(engine) as session:
        row = session.get(ProcessedWebhookEvent, "e1")
        assert row is not None and row.response_text is None
    assert _post(client, postback("e1", data)).status_code == 200
    assert line.replies == []


def test_help_topic_postback_replies_topic_text(bot):
    client, _, line = bot
    _post(client, postback("e1", "a=help&t=savings"))
    assert line.replies[-1][1] == HELP_TOPIC_TEXT["savings"]


def test_help_has_quick_reply(bot):
    client, _, line = bot
    _post(client, text("e1", "ช่วยเหลือ"))
    items = _last(line)["quickReply"]["items"]
    assert [i["action"]["data"] for i in items][0] == "a=help&t=expense" and len(items) == 6


def test_direction_prompt_has_quick_reply(bot):
    client, _, line = bot
    _post(client, text("e1", "50"))
    labels = [i["action"]["text"] for i in _last(line)["quickReply"]["items"]]
    assert labels == ["รายจ่าย", "รายรับ"]


def test_delete_prompts_have_confirm_quick_reply(bot):
    client, _, line = bot
    _post(client, text("e1", "ข้าว 50"))
    _post(client, text("e2", "ลบล่าสุด"))
    assert [i["action"]["text"] for i in _last(line)["quickReply"]["items"]] == ["ยืนยัน", "ยกเลิก"]
    _post(client, text("e3", "ยกเลิก"))
    _post(client, text("e4", "ลบข้อมูลทั้งหมด"))
    assert [i["action"]["text"] for i in _last(line)["quickReply"]["items"]] == ["ยืนยัน", "ยกเลิก"]


def test_text_confirmed_delete_replies_with_undo_card(bot):
    client, engine, line = bot
    _post(client, text("e1", "ข้าว 50"))
    _post(client, text("e2", "ลบล่าสุด"))
    _post(client, text("e3", "ยืนยัน"))
    undo = [d for d in _datas(_last(line)) if d.startswith("a=undo&id=")]
    assert undo and _only_tx(engine) == []
    _post(client, postback("e4", undo[0]))
    assert len(_only_tx(engine)) == 1


def test_delete_keeps_pending_draft(bot):
    client, engine, line = bot
    _post(client, text("e1", "ข้าว 50"))
    tx_id = _only_tx(engine)[0].id
    _post(client, text("e2", "80"))
    with Session(engine) as session:
        draft = session.get(PendingTransaction, "U-a")
        before = (draft.draft_id, draft.version)
    _post(client, postback("e3", f"a=del&t={tx_id}"))
    with Session(engine) as session:
        draft = session.get(PendingTransaction, "U-a")
        assert (draft.draft_id, draft.version) == before


def test_redelivery_replays_cached_flex(bot, monkeypatch):
    client, engine, line = bot
    failing = LineRecorder(fail_times=1, error=LineTransportError("down")).install(monkeypatch, app_module)
    assert _post(client, text("e1", "ข้าว 50")).status_code == 502
    first = failing.attempts[0]
    assert _post(client, text("e1", "ข้าว 50")).status_code == 200
    assert failing.messages[-1][-1]["type"] == "flex"
    assert failing.replies[-1][1] == first[1]
    assert len(_only_tx(engine)) == 1


def test_legacy_row_without_messages_replays_text(bot):
    client, engine, line = bot
    with Session(engine) as session:
        session.add(ProcessedWebhookEvent(webhook_event_id="old", response_text="ข้อความเก่า", reply_sent=False))
        session.commit()
    assert _post(client, text("old", "ข้าว 50")).status_code == 200
    assert line.messages[-1] == [{"type": "text", "text": "ข้อความเก่า"}]
    assert _only_tx(engine) == []


def test_loading_called_for_message_and_postback_not_follow(bot):
    client, _, line = bot
    _post(client, text("e1", "ข้าว 50", user="U-x"))
    _post(client, postback("e2", "a=help&t=income", user="U-y"))
    _post(client, follow("e3", user="U-z"))
    assert line.loading == ["U-x", "U-y"]


def test_loading_failure_does_not_block_reply(bot, monkeypatch):
    client, engine, line = bot

    async def broken(*args, **kwargs):
        raise LineTransportError("no loading")

    monkeypatch.setattr(app_module, "start_loading", broken)
    assert _post(client, text("e1", "ข้าว 50")).status_code == 200
    assert line.messages and len(_only_tx(engine)) == 1
