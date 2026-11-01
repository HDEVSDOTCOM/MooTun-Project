"""Guards for user-facing reply copy (messages.py)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

import messages
import parser
from parser import IncompleteCommand, UnresolvedCommand, parse_command, parse_followup

PARSER_SOURCE = Path(parser.__file__).read_text(encoding="utf-8")
THAI = r"[^\"\n]*[฀-๿][^\"\n]*"

# Words handled by app.py control flow or as follow-up answers, not by parse_command.
CONTROL_WORDS = {"ยืนยัน", "ยกเลิก", "เลิกทำ"}
FOLLOWUP_ANSWERS = {"รายจ่าย", "รายรับ"}
# Bare command prefixes mentioned in instructions ("พิมพ์ "เสนอแนะ" ตามด้วย...").
PREFIX_WORDS = {"เสนอแนะ", "แก้ไข"}


def _parser_reasons() -> set[str]:
    reasons = set(re.findall(rf'_unresolved\("({THAI})"', PARSER_SOURCE))
    reasons |= set(re.findall(rf'return None, text, "({THAI})"', PARSER_SOURCE))
    for name in ("_invalid_amount_reason", "_transaction_intent_rejection"):
        body = PARSER_SOURCE.split(f"def {name}(", 1)[1].split("\ndef ", 1)[0]
        reasons |= set(re.findall(rf'return "({THAI})"', body))
    reasons |= {parser.FOLLOWUP_CONFLICT_REASON, parser.EDIT_MISSING_DETAILS_REASON, parser.EDIT_INCOMPLETE_REASON}
    return reasons


def test_every_parser_reason_has_friendly_copy():
    reasons = _parser_reasons()
    assert len(reasons) >= 20
    missing = sorted(reasons - set(messages.FRIENDLY_REASONS))
    assert missing == []


def test_friendly_reason_falls_back():
    assert messages.friendly_reason(None) == messages.UNKNOWN_HEADING
    assert messages.friendly_reason("  ") == messages.UNKNOWN_HEADING
    assert messages.friendly_reason("ข้อความใหม่ที่ยังไม่ได้แปล") == "ข้อความใหม่ที่ยังไม่ได้แปล"


def test_unknown_message_shapes():
    full = messages.format_unknown_message()
    assert full.startswith(messages.UNKNOWN_HEADING) and "• ข้าว 50" in full
    assert messages.format_unknown_message("ไม่รู้จักคำสั่ง") == full
    specific = messages.format_unknown_message("กรุณาระบุจำนวนเงินที่ออม")
    assert specific == f'ออมกี่บาทครับ? เช่น "ออม 100"\n\n{messages.HELP_HINT}'


def _all_copy() -> list[str]:
    sample = {"type": "expense", "amount": 50, "category": "อาหาร", "note": "ข้าว", "date": date(2026, 11, 1)}
    goal = {"name": "ทริป", "target": 1000, "saved": 250}
    texts = [
        messages.format_transaction_confirmation(sample),
        messages.format_edit_confirmation(sample),
        messages.format_delete_confirmation_prompt(sample),
        messages.format_delete_success(sample),
        messages.format_delete_all_confirmation_prompt(3),
        messages.format_delete_all_expired(),
        messages.format_delete_not_confirmed_yet(),
        messages.format_recent_transactions([]),
        messages.format_savings_goal_created(goal),
        messages.format_no_savings_goal(),
        messages.format_unknown_message(),
        messages.format_pending_transaction_prompt(amount=50, description=None),
        messages.format_pending_conflict(),
        messages.format_invalid_followup(),
        messages.format_feedback_instruction(),
        messages.format_feedback_invalid_rating(),
        messages.format_onboarding_welcome(),
        messages.format_onboarding_usage(),
    ]
    return texts + list(messages.FRIENDLY_REASONS.values())


def test_suggested_commands_actually_work():
    suggested = {quoted for text in _all_copy() for quoted in re.findall(r'"([^"]+)"', text)}
    assert {"ลบล่าสุด", "ยืนยัน", "เลิกทำ", "ตั้งเป้า 1500 ซื้อหนังสือ", "รายจ่าย"} <= suggested
    for command in sorted(suggested - CONTROL_WORDS - FOLLOWUP_ANSWERS - PREFIX_WORDS):
        result = parse_command(command)
        assert not isinstance(result, (UnresolvedCommand, IncompleteCommand)), command


@pytest.mark.parametrize("answer", sorted(FOLLOWUP_ANSWERS))
def test_suggested_followup_answers_complete_a_draft(answer):
    draft = parse_command("50")
    assert isinstance(draft, IncompleteCommand)
    assert not isinstance(parse_followup(draft, answer, now=date(2026, 11, 1)), (UnresolvedCommand, IncompleteCommand))


def test_dates_and_months_are_short_thai():
    assert messages.format_buddhist_date(date(2026, 11, 1)) == "1 พ.ย. 69"
    assert messages.format_buddhist_date(date(2027, 1, 31)) == "31 ม.ค. 70"
    assert messages.format_buddhist_month(date(2026, 11, 1)) == "เดือนพฤศจิกายน 2569"


def test_summary_overspend_reads_naturally():
    text = messages.format_monthly_summary({"income": 100, "expense": 250, "month": "เดือนนี้"})
    assert "ใช้เกินไป 150 บาท" in text and "-150" not in text
