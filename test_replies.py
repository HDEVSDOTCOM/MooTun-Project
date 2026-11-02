from __future__ import annotations

from replies import Reply, as_reply

CARD = {"type": "bubble", "body": {"type": "box", "layout": "vertical", "contents": []}}
QUICK = ({"type": "action", "action": {"type": "message", "label": "ยืนยัน", "text": "ยืนยัน"}},)


def test_to_messages_text_only():
    assert Reply("สวัสดี").to_messages() == [{"type": "text", "text": "สวัสดี"}]


def test_to_messages_flex_uses_truncated_alt_text():
    messages = Reply("ก" * 450, flex=CARD).to_messages()
    assert len(messages) == 1
    message = messages[0]
    assert message["type"] == "flex" and message["contents"] == CARD
    assert len(message["altText"]) == 400 and message["altText"].endswith("…")
    assert Reply("สั้น", flex=CARD).to_messages()[0]["altText"] == "สั้น"


def test_quick_reply_attached_to_last_message():
    text_message = Reply("ลบไหม", quick_reply=QUICK).to_messages()[-1]
    assert text_message["quickReply"] == {"items": list(QUICK)}
    flex_message = Reply("ลบไหม", flex=CARD, quick_reply=QUICK).to_messages()[-1]
    assert flex_message["quickReply"] == {"items": list(QUICK)}
    assert "quickReply" not in Reply("x").to_messages()[0]


def test_as_reply_wraps_str_and_passes_reply():
    reply = Reply("x", flex=CARD)
    assert as_reply(reply) is reply
    assert as_reply("ข้อความ") == Reply("ข้อความ")
