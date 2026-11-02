"""By-id edit and delete used by the Mini App edit form."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, PendingAction, PendingTransaction, Transaction
from repository import (
    add_transaction,
    create_pending_action,
    create_pending_transaction,
    delete_transaction_by_id,
    delete_transaction_with_undo,
    update_transaction,
)
from taxonomy import categories

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'edit.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _tx(db, user="U-a", note="ข้าว"):
    item = add_transaction(user, "expense", "50", "อาหาร", description=note,
                           occurred_on=date(2026, 11, 1), session=db)
    db.flush()
    return item


def _edit(db, tx_id, user="U-a", **overrides):
    fields = dict(transaction_type="income", amount="12.34", category="รายรับอื่นๆ",
                  description="  ", occurred_on=date(2026, 10, 30))
    fields.update(overrides)
    return update_transaction(user, tx_id, session=db, **fields)


def test_categories_are_unique_and_end_with_fallback():
    expense, income = categories("expense"), categories("income")
    assert expense[-1] == "อื่นๆ" and income[-1] == "รายรับอื่นๆ"
    assert len(set(expense)) == len(expense) and len(set(income)) == len(income)
    assert "อาหาร" in expense and "อาหาร" not in income


def test_update_transaction_replaces_every_field(db):
    tx = _tx(db)
    created = tx.created_at
    updated = _edit(db, tx.id)
    assert updated is not None and updated.id == tx.id
    assert (updated.transaction_type, updated.amount_satang, updated.category) == ("income", 1234, "รายรับอื่นๆ")
    assert updated.description is None
    assert updated.occurred_on == date(2026, 10, 30)
    assert updated.created_at == created


def test_update_and_delete_other_user_row_returns_none(db):
    tx = _tx(db)
    assert _edit(db, tx.id, user="U-b") is None
    assert delete_transaction_by_id("U-b", tx.id, session=db) is False
    row = db.get(Transaction, tx.id)
    assert (row.amount_satang, row.transaction_type) == (5000, "expense")


@pytest.mark.parametrize("overrides", [
    {"transaction_type": "x"}, {"amount": "0"}, {"amount": "1.234"}, {"category": "  "},
])
def test_update_rejects_bad_values(db, overrides):
    tx = _tx(db)
    with pytest.raises(ValueError):
        _edit(db, tx.id, **overrides)


def test_delete_transaction_by_id_removes_row(db):
    tx = _tx(db)
    assert delete_transaction_by_id("U-a", tx.id, session=db) is True
    assert db.get(Transaction, tx.id) is None
    assert delete_transaction_by_id("U-a", tx.id, session=db) is False


def _write(db, op, tx_id):
    if op == "update":
        assert _edit(db, tx_id) is not None
    else:
        assert delete_transaction_by_id("U-a", tx_id, session=db) is True
    db.flush()


@pytest.mark.parametrize("op", ["update", "delete"])
def test_write_drops_confirm_delete_for_that_row(db, op):
    tx = _tx(db)
    create_pending_transaction("U-a", transaction_type=None, amount="80", category=None,
                               description=None, occurred_on=date(2026, 11, 1), now=NOW, session=db)
    assert create_pending_action("U-a", action_type="confirm_delete", target_transaction_id=tx.id,
                                 now=NOW, session=db)
    _write(db, op, tx.id)
    assert db.get(PendingAction, "U-a") is None
    assert db.get(PendingTransaction, "U-a") is not None


@pytest.mark.parametrize("op", ["update", "delete"])
def test_write_keeps_confirm_delete_for_other_row(db, op):
    tx, other = _tx(db), _tx(db, note="กาแฟ")
    assert create_pending_action("U-a", action_type="confirm_delete", target_transaction_id=other.id,
                                 now=NOW, session=db)
    _write(db, op, tx.id)
    assert db.get(PendingAction, "U-a").target_transaction_id == other.id


@pytest.mark.parametrize("op", ["update", "delete"])
def test_write_keeps_undo_delete(db, op):
    tx, gone = _tx(db), _tx(db, note="กาแฟ")
    delete_transaction_with_undo("U-a", gone.id, now=NOW, session=db)
    db.flush()
    _write(db, op, tx.id)
    assert db.get(PendingAction, "U-a").action_type == "undo_delete"
