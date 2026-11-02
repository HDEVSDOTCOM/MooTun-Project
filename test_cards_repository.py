"""Repository support for chat cards: one-tap delete with undo, month totals, cache."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

import repository
from database import init_db
from models import Base, PendingAction, PendingTransaction, ProcessedWebhookEvent, Transaction
from repository import (
    DeleteOutcome,
    PendingActionConflictError,
    RestoreOutcome,
    add_transaction,
    category_month_total,
    create_pending_action,
    create_pending_transaction,
    delete_transaction_with_undo,
    get_transaction,
    mark_webhook_processed,
    restore_deleted_transaction,
    set_webhook_response,
)

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cards.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _tx(db, user="U-a", kind="expense", amount="50", category="อาหาร", day=date(2026, 11, 1), note="ข้าว"):
    item = add_transaction(user, kind, amount, category, description=note, occurred_on=day, session=db)
    db.flush()
    return item


def test_init_db_adds_response_messages_column(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE processed_webhook_events (webhook_event_id VARCHAR(128) PRIMARY KEY, "
            "processed_at DATETIME NOT NULL, response_text VARCHAR(5000), reply_sent BOOLEAN NOT NULL DEFAULT 0)"
        ))
    init_db(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("processed_webhook_events")}
    assert "response_messages" in columns


def test_set_webhook_response_stores_messages_json(db):
    assert mark_webhook_processed("evt-1", session=db)
    set_webhook_response("evt-1", "จดแล้ว", messages_json='[{"type":"text","text":"x"}]', session=db)
    row = db.get(ProcessedWebhookEvent, "evt-1")
    assert row.response_text == "จดแล้ว"
    assert row.response_messages == '[{"type":"text","text":"x"}]'
    set_webhook_response("evt-1", "อีกครั้ง", session=db)
    assert db.get(ProcessedWebhookEvent, "evt-1").response_messages is None


def test_get_transaction_is_user_scoped(db):
    item = _tx(db)
    assert get_transaction("U-a", item.id, session=db).id == item.id
    assert get_transaction("U-b", item.id, session=db) is None
    assert get_transaction("U-a", item.id + 999, session=db) is None


def test_category_month_total_bangkok_bounds(db):
    _tx(db, amount="100", day=date(2026, 10, 31))
    _tx(db, amount="50", day=date(2026, 11, 1))
    _tx(db, amount="25", day=date(2026, 11, 30))
    _tx(db, amount="70", category="เดินทาง", day=date(2026, 11, 5))
    _tx(db, kind="income", amount="999", category="อาหาร", day=date(2026, 11, 5))
    _tx(db, user="U-b", amount="500", day=date(2026, 11, 5))
    assert category_month_total("U-a", "expense", "อาหาร", 2026, 11, session=db) == (7500, 14500)
    assert category_month_total("U-a", "expense", "อาหาร", 2026, 10, session=db) == (10000, 10000)
    assert category_month_total("U-a", "income", "อาหาร", 2026, 11, session=db) == (99900, 99900)
    assert category_month_total("U-c", "expense", "อาหาร", 2026, 11, session=db) == (0, 0)


def _action(db, user="U-a") -> PendingAction | None:
    db.expire_all()
    return db.get(PendingAction, user)


def test_delete_with_undo_no_pending_action(db):
    item = _tx(db)
    snapshot = (item.id, item.transaction_type, item.amount_satang, item.category, item.description, item.occurred_on)
    result = delete_transaction_with_undo("U-a", item.id, now=NOW, session=db)
    assert result.outcome is DeleteOutcome.DELETED
    assert result.transaction.id == snapshot[0]
    assert db.get(Transaction, snapshot[0]) is None
    action = _action(db)
    assert action.action_type == "undo_delete" and action.action_id == result.action_id
    assert (action.snapshot_transaction_id, action.snapshot_transaction_type, action.snapshot_amount_satang,
            action.snapshot_category, action.snapshot_description, action.snapshot_occurred_on) == snapshot
    expires = action.expires_at if action.expires_at.tzinfo else action.expires_at.replace(tzinfo=timezone.utc)
    assert expires == NOW + timedelta(minutes=10)


def test_delete_with_undo_replaces_confirm_delete_all(db):
    item = _tx(db)
    assert create_pending_action("U-a", action_type="confirm_delete_all",
                                 target_transaction_id=repository.DELETE_ALL_TARGET_SENTINEL, now=NOW, session=db)
    result = delete_transaction_with_undo("U-a", item.id, now=NOW, session=db)
    assert result.outcome is DeleteOutcome.DELETED
    assert _action(db).action_type == "undo_delete"


def test_delete_with_undo_replaces_existing_undo(db):
    first, second = _tx(db, note="หนึ่ง"), _tx(db, note="สอง")
    old = delete_transaction_with_undo("U-a", first.id, now=NOW, session=db)
    new = delete_transaction_with_undo("U-a", second.id, now=NOW, session=db)
    assert new.action_id != old.action_id
    assert _action(db).snapshot_transaction_id == second.id


def test_delete_with_undo_other_user_not_found(db):
    item = _tx(db)
    result = delete_transaction_with_undo("U-b", item.id, now=NOW, session=db)
    assert result.outcome is DeleteOutcome.NOT_FOUND and result.action_id is None
    assert db.get(Transaction, item.id) is not None
    assert _action(db, "U-b") is None


def test_delete_with_undo_missing_not_found(db):
    assert delete_transaction_with_undo("U-a", 12345, now=NOW, session=db).outcome is DeleteOutcome.NOT_FOUND
    assert _action(db) is None


def test_delete_with_undo_keeps_pending_draft(db):
    item = _tx(db)
    create_pending_transaction("U-a", transaction_type=None, amount="80", category=None, description=None,
                               occurred_on=date(2026, 11, 2), now=NOW, session=db)
    db.flush()
    before = db.get(PendingTransaction, "U-a")
    draft = (before.draft_id, before.version)
    delete_transaction_with_undo("U-a", item.id, now=NOW, session=db)
    db.expire_all()
    after = db.get(PendingTransaction, "U-a")
    assert (after.draft_id, after.version) == draft


def test_delete_with_undo_conflict(db, monkeypatch):
    item = _tx(db)
    assert create_pending_action("U-a", action_type="confirm_delete", target_transaction_id=item.id,
                                 now=NOW, session=db)
    original = repository._read_any_pending_action

    def bumped(user_id, session):
        action = original(user_id, session)
        session.execute(text("UPDATE pending_actions SET version = version + 1 WHERE line_user_id = 'U-a'"))
        return action

    monkeypatch.setattr(repository, "_read_any_pending_action", bumped)
    with pytest.raises(PendingActionConflictError):
        delete_transaction_with_undo("U-a", item.id, now=NOW, session=db)
    db.expire_all()
    assert db.get(Transaction, item.id) is not None


def test_restore_after_one_tap_delete(db):
    item = _tx(db)
    original_id = item.id
    result = delete_transaction_with_undo("U-a", original_id, now=NOW, session=db)
    action = _action(db)
    restored = restore_deleted_transaction("U-a", action.version, expected_action_id=result.action_id,
                                           now=NOW, session=db)
    assert restored.outcome is RestoreOutcome.RESTORED
    assert restored.transaction.id == original_id
