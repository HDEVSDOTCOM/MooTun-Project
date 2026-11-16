"""The 'แก้แล้ว' card strikes through what an edit replaced (LINE cannot change the old card)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

import flex
from database import init_db
from flex import MonthTotal, transaction_card
from messages import edit_changes, format_edit_confirmation
from models import Base, Transaction
from repository import (
    EDIT_DIFF_WINDOW,
    add_transaction,
    recent_edit_before,
    update_latest_transaction,
    update_transaction,
)

NOW = datetime(2026, 11, 16, 5, 0, tzinfo=timezone.utc)
AFTER = {"id": 7, "type": "expense", "amount": Decimal("70"), "category": "อาหาร", "note": "ข้าวมันไก่",
         "date": date(2026, 11, 16)}
TOTAL = MonthTotal(7000, 7000)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'history.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def _tx(db, user="U-a"):
    item = add_transaction(user, "expense", "50", "เครื่องดื่ม", description="ชานม",
                           occurred_on=date(2026, 11, 15), session=db)
    db.flush()
    return item


def _patch(db, tx_id, now=NOW, **overrides):
    fields = dict(transaction_type="expense", amount="70", category="อาหาร", description="ข้าวมันไก่",
                  occurred_on=date(2026, 11, 16))
    fields.update(overrides)
    return update_transaction("U-a", tx_id, session=db, now=now, **fields)


# --- repository ---

def test_by_id_edit_keeps_what_it_replaced(db):
    tx = _tx(db)
    _patch(db, tx.id)
    row = db.get(Transaction, tx.id)
    assert row.edited_at == NOW
    assert json.loads(row.edited_from) == {"type": "expense", "amount_satang": 5000, "category": "เครื่องดื่ม",
                                           "description": "ชานม", "occurred_on": "2026-11-15"}
    assert recent_edit_before(row, now=NOW + timedelta(minutes=3)) == {
        "type": "expense", "amount": Decimal("50"), "category": "เครื่องดื่ม", "note": "ชานม",
        "date": date(2026, 11, 15)}


def test_chat_edit_keeps_what_it_replaced(db):
    tx = _tx(db)
    update_latest_transaction("U-a", "expense", "60", "เครื่องดื่ม", description="ชานม", session=db, now=NOW)
    before = recent_edit_before(db.get(Transaction, tx.id), now=NOW)
    assert before is not None and before["amount"] == Decimal("50")


def test_second_edit_replaces_the_first_snapshot(db):
    tx = _tx(db)
    _patch(db, tx.id, amount="70")
    _patch(db, tx.id, amount="80", now=NOW + timedelta(minutes=1))
    before = recent_edit_before(db.get(Transaction, tx.id), now=NOW + timedelta(minutes=1))
    assert before["amount"] == Decimal("70")


def test_snapshot_is_ignored_once_the_window_passes(db):
    tx = _tx(db)
    _patch(db, tx.id)
    row = db.get(Transaction, tx.id)
    assert recent_edit_before(row, now=NOW + EDIT_DIFF_WINDOW) is not None
    assert recent_edit_before(row, now=NOW + EDIT_DIFF_WINDOW + timedelta(seconds=1)) is None


def test_never_edited_or_broken_snapshot_gives_nothing(db):
    tx = _tx(db)
    assert recent_edit_before(tx, now=NOW) is None
    tx.edited_from, tx.edited_at = "{not json", NOW
    assert recent_edit_before(tx, now=NOW) is None
    tx.edited_from = json.dumps({"type": "expense"})
    assert recent_edit_before(tx, now=NOW) is None


def test_naive_edited_at_from_sqlite_is_read_as_utc(db):
    tx = _tx(db)
    _patch(db, tx.id)
    row = db.get(Transaction, tx.id)
    row.edited_at = NOW.replace(tzinfo=None)
    assert recent_edit_before(row, now=NOW) is not None


def test_init_db_adds_edit_columns_to_an_old_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, line_user_id VARCHAR(128) NOT NULL,"
            " transaction_type VARCHAR(16) NOT NULL, amount_satang BIGINT NOT NULL, category VARCHAR(100) NOT NULL,"
            " description VARCHAR(500), occurred_on DATE NOT NULL, created_at DATETIME NOT NULL)"))
    init_db(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("transactions")}
    assert {"edited_from", "edited_at"} <= columns
    init_db(engine)  # idempotent
    engine.dispose()


# --- wording ---

def test_edit_changes_lists_only_old_values_that_changed():
    before = {**AFTER, "amount": Decimal("50"), "category": "เครื่องดื่ม", "note": "ชานม", "date": date(2026, 11, 15)}
    assert edit_changes(before, AFTER) == ["-฿50", "เครื่องดื่ม", "ชานม", "15 พ.ย. 69"]
    assert edit_changes(AFTER, AFTER) == []
    assert edit_changes(None, AFTER) == []


def test_type_flip_shows_the_old_sign_and_an_added_note_shows_none():
    before = {**AFTER, "type": "income", "note": None}
    assert edit_changes(before, AFTER) == ["+฿70", "ไม่มีรายการ"]


def test_alt_text_names_the_old_values():
    before = {**AFTER, "amount": Decimal("50")}
    assert "เดิม: -฿50" in format_edit_confirmation(AFTER, before=before)
    assert "เดิม" not in format_edit_confirmation(AFTER)


# --- card ---

def _struck(card):
    spans = [span for node in _walk(card) for span in node.get("contents", []) if span.get("type") == "span"]
    return [span["text"] for span in spans if span.get("decoration") == "line-through"]


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def test_edit_card_strikes_through_the_old_values():
    before = {**AFTER, "amount": Decimal("50"), "category": "เครื่องดื่ม"}
    card = transaction_card("edit", AFTER, TOTAL, liff_id=None, image_url=None, before=before)
    assert _struck(card) == ["-฿50", "เครื่องดื่ม"]
    line = next(node for node in _walk(card) if node.get("type") == "text" and node.get("contents"))
    assert line["text"] == "เดิม -฿50 · เครื่องดื่ม" and line["wrap"] is True
    assert line["contents"][0]["text"].startswith("เดิม")
    assert all(span["color"] == flex.STRUCK for span in line["contents"] if span.get("decoration"))
    assert "-฿70" in [node.get("text") for node in _walk(card)]


def test_edit_card_without_changes_has_no_old_line():
    for before in (None, AFTER):
        card = transaction_card("edit", AFTER, TOTAL, liff_id=None, image_url=None, before=before)
        assert _struck(card) == []


def test_only_the_edit_card_takes_before():
    with pytest.raises(ValueError):
        transaction_card("record", AFTER, TOTAL, liff_id=None, image_url=None, before={**AFTER, "amount": 1})
