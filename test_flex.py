from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal

import pytest

import flex
import media
from flex import MonthTotal, deleted_card, transaction_card
from messages import HELP_TOPIC_TEXT
from parser import IncompleteCommand, UnresolvedCommand, parse_command
from postback import HELP_TOPICS

EXPENSE = {"id": 7, "type": "expense", "amount": Decimal("50"), "category": "อาหาร", "note": "ข้าวมันไก่",
           "date": date(2026, 11, 1)}
INCOME = {"id": 8, "type": "income", "amount": Decimal("20000"), "category": "เงินเดือน", "note": "เงินเดือน",
          "date": date(2026, 11, 1)}
TOTAL = MonthTotal(125000, 312500)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _texts(card) -> list[str]:
    return [node["text"] for node in _walk(card) if node.get("type") == "text"]


def _actions(card) -> list[dict]:
    return [node["action"] for node in _walk(card) if isinstance(node.get("action"), dict)]


def _node_with_text(card, text):
    return next(node for node in _walk(card) if node.get("type") == "text" and node.get("text") == text)


def test_record_card_expense():
    card = transaction_card("record", EXPENSE, TOTAL, liff_id="LIFF", image_url=None)
    texts = _texts(card)
    assert card["type"] == "bubble"
    assert texts[0] == "จดแล้ว! ✅"
    for expected in ("รายจ่าย", "1 พ.ย. 69", "ข้าวมันไก่", "-฿50", "อาหารเดือนนี้ ฿1,250", "40% ของรายจ่าย"):
        assert expected in texts
    pill = next(node for node in _walk(card) if node.get("type") == "box"
                and any(c.get("text") == "รายจ่าย" for c in node.get("contents", [])))
    assert pill["backgroundColor"] == "#D81B72"
    actions = _actions(card)
    assert {"type": "postback", "data": "a=del&t=7"} in [{k: a[k] for k in ("type", "data")} for a in actions if a["type"] == "postback"]
    assert any(a.get("uri") == f"https://liff.line.me/LIFF/transactions?edit={EXPENSE['id']}" for a in actions)


def test_income_card_is_green_and_signed_plus():
    card = transaction_card("record", INCOME, MonthTotal(2000000, 2000000), liff_id=None, image_url=None)
    texts = _texts(card)
    assert "+฿20,000" in texts and "100% ของรายรับ" in texts
    assert _node_with_text(card, "+฿20,000")["color"] == "#1F9E74"


def test_edit_and_restore_titles():
    assert _texts(transaction_card("edit", EXPENSE, TOTAL, liff_id=None, image_url=None))[0] == "แก้แล้ว ✏️"
    assert _texts(transaction_card("restore", EXPENSE, TOTAL, liff_id=None, image_url=None))[0] == "เอาคืนมาแล้ว ↩️"
    with pytest.raises(ValueError):
        transaction_card("other", EXPENSE, TOTAL, liff_id=None, image_url=None)


def test_note_fallback_uses_category():
    card = transaction_card("record", {**EXPENSE, "note": "ไม่ระบุรายการ"}, TOTAL, liff_id=None, image_url=None)
    assert "ไม่ระบุรายการ" not in _texts(card)
    assert _texts(card).count("อาหาร") >= 1


def test_no_liff_id_omits_edit_button():
    card = transaction_card("record", EXPENSE, TOTAL, liff_id=None, image_url=None)
    assert not any(a.get("type") == "uri" for a in _actions(card))


def test_image_only_when_url_given():
    without = transaction_card("record", EXPENSE, TOTAL, liff_id=None, image_url=None)
    assert not any(node.get("type") == "image" for node in _walk(without))
    url = "https://x.example/media/pig-record.0123abcd.png"
    with_image = transaction_card("record", EXPENSE, TOTAL, liff_id=None, image_url=url)
    assert any(node.get("type") == "image" and node.get("url") == url for node in _walk(with_image))


def test_deleted_card():
    action_id = "0123456789abcdef0123456789abcdef"
    card = deleted_card(EXPENSE, MonthTotal(75000, 262500), action_id=action_id, image_url=None)
    assert _texts(card)[0] == "ลบแล้ว 🗑️"
    assert _node_with_text(card, "-฿50")["decoration"] == "line-through"
    assert "a=del" not in json.dumps(card)
    datas = [a.get("data") for a in _actions(card)]
    assert f"a=undo&id={action_id}" in datas
    assert "อาหารเดือนนี้ ฿750" in _texts(card)


@pytest.mark.parametrize(("total", "percent"), [
    (MonthTotal(0, 0), 0), (MonthTotal(1, 3), 33), (MonthTotal(1, 8), 13), (MonthTotal(1, 200), 1),
])
def test_month_total_percent(total, percent):
    assert total.percent == percent


def test_zero_total_has_no_filled_bar():
    card = transaction_card("record", EXPENSE, MonthTotal(0, 0), liff_id=None, image_url=None)
    assert "0% ของรายจ่าย" in _texts(card)
    assert not any("width" in node and node.get("backgroundColor") == "#D81B72" and node.get("type") == "box"
                   and "%" in str(node.get("width")) for node in _walk(card))


def test_long_text_card_limits():
    tx = {**EXPENSE, "note": "ก" * 500, "category": "ข" * 100}
    for card in (transaction_card("record", tx, TOTAL, liff_id="LIFF", image_url="https://x/m.png"),
                 deleted_card(tx, TOTAL, action_id="0" * 32, image_url="https://x/m.png")):
        assert len(json.dumps(card, ensure_ascii=False).encode()) <= 10_240


def test_quick_replies():
    help_items = flex.help_quick_reply()
    assert [item["action"]["data"] for item in help_items] == [f"a=help&t={t}" for t in HELP_TOPICS]
    assert [item["action"]["label"] for item in help_items] == [
        "จดรายจ่าย", "จดรายรับ", "เงินออม", "แก้หรือลบ", "ความเป็นส่วนตัว", "ปัญหาอื่นๆ"]
    assert all(item["type"] == "action" and len(item["action"]["label"]) <= 20 for item in help_items)
    assert [i["action"]["text"] for i in flex.direction_quick_reply()] == ["รายจ่าย", "รายรับ"]
    assert [i["action"]["text"] for i in flex.confirm_quick_reply()] == ["ยืนยัน", "ยกเลิก"]
    assert all(i["action"]["type"] == "message" for i in flex.confirm_quick_reply())


def test_media_url(tmp_path, monkeypatch):
    (tmp_path / "pig-record.0123abcd.png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path)
    assert media.media_url("record", "https://x") == "https://x/media/pig-record.0123abcd.png"
    assert media.media_url("restore", "https://x") == "https://x/media/pig-record.0123abcd.png"
    assert media.media_url("delete", "https://x") is None
    assert media.media_url("record", None) is None
    assert media.MEDIA_NAME.fullmatch("pig-edit.89abcdef.png")
    assert not media.MEDIA_NAME.fullmatch("pig-edit.png")


def test_help_topic_examples_parse():
    assert set(HELP_TOPIC_TEXT) == set(HELP_TOPICS)
    for text in HELP_TOPIC_TEXT.values():
        for command in re.findall(r'"([^"]+)"', text):
            result = parse_command(command)
            assert not isinstance(result, (UnresolvedCommand, IncompleteCommand)), command
