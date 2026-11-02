"""Mini App write API: edit and delete one transaction, plus the category list."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import webapp_routes as routes
from models import Transaction
from taxonomy import categories
from test_webapp import A, B, TOKEN_B, headers, seed, web  # noqa: F401 - web is a fixture

BODY = {"transaction_type": "income", "amount_baht": "99.50", "category": "รายรับอื่นๆ",
        "description": "แก้", "occurred_on": "2026-10-03"}


def _ids(engine, owner):
    with Session(engine) as session:
        return [t.id for t in session.scalars(select(Transaction).where(Transaction.line_user_id == owner)
                                              .order_by(Transaction.id))]


def _patch(client, tx_id, body, token=None, raw=None):
    content = raw if raw is not None else json.dumps(body, ensure_ascii=False).encode()
    return client.patch(f"/api/me/transactions/{tx_id}", content=content,
                        headers={**headers(*([token] if token else [])), "content-type": "application/json"})


def test_items_include_id(web):
    client, engine, _ = web
    seed(engine)
    ids = _ids(engine, A)
    recent = client.get("/api/me/transactions/recent", headers=headers()).json()["items"]
    month = client.get("/api/me/transactions?month=2026-10", headers=headers()).json()["items"]
    assert sorted(i["id"] for i in recent) == ids
    assert sorted(i["id"] for i in month) == ids


def test_get_patch_delete_own_row(web):
    client, engine, _ = web
    seed(engine)
    tx_id = _ids(engine, A)[1]
    got = client.get(f"/api/me/transactions/{tx_id}", headers=headers())
    assert got.status_code == 200 and got.json()["id"] == tx_id
    response = _patch(client, tx_id, BODY)
    assert response.status_code == 200
    assert response.json()["amount_baht"] == "99.50" and response.json()["category"] == "รายรับอื่นๆ"
    with Session(engine) as session:
        row = session.get(Transaction, tx_id)
        assert (row.amount_satang, row.transaction_type, row.description) == (9950, "income", "แก้")
    assert client.delete(f"/api/me/transactions/{tx_id}", headers=headers()).status_code == 204
    assert client.get(f"/api/me/transactions/{tx_id}", headers=headers()).status_code == 404


def test_other_user_and_missing_ids_are_identical_404(web):
    client, engine, _ = web
    seed(engine)
    foreign = _ids(engine, A)[0]
    results = []
    for tx_id, token in ((foreign, TOKEN_B), (999999, None), (0, None), ("1234567890", None)):
        extra = [token] if token else []
        results.append(client.get(f"/api/me/transactions/{tx_id}", headers=headers(*extra)))
        results.append(_patch(client, tx_id, BODY, token=token))
        results.append(client.delete(f"/api/me/transactions/{tx_id}", headers=headers(*extra)))
    assert {r.status_code for r in results} == {404}
    assert len({json.dumps(r.json(), sort_keys=True) for r in results}) == 1
    assert results[0].json()["code"] == "NOT_FOUND"
    # A non-numeric id never reaches these routes: the framework's plain 404, like any unknown path.
    assert client.get("/api/me/transactions/abc", headers=headers()).status_code == 404
    with Session(engine) as session:
        assert session.get(Transaction, foreign).amount_satang == 10001


@pytest.mark.parametrize("change, field", [
    ({"transaction_type": "x"}, "transaction_type"),
    ({"amount_baht": "0"}, "amount_baht"),
    ({"amount_baht": "-1"}, "amount_baht"),
    ({"amount_baht": "1.234"}, "amount_baht"),
    ({"amount_baht": "abc"}, "amount_baht"),
    ({"amount_baht": 50.1}, "amount_baht"),
    ({"amount_baht": "1e3"}, "amount_baht"),
    ({"category": "ไม่มีหมวดนี้"}, "category"),
    ({"category": "อาหาร"}, "category"),  # expense category on an income row
    ({"category": "อาหาร A"}, "category"),  # the row's own expense category is not valid for income
    ({"description": "ก" * 501}, "description"),
    ({"description": 5}, "description"),
    ({"occurred_on": "2026-10-11"}, "occurred_on"),
    ({"occurred_on": "1999-12-31"}, "occurred_on"),
    ({"occurred_on": "2026-13-01"}, "occurred_on"),
    ({"extra": 1}, "body"),
])
def test_patch_validation(web, change, field):
    client, engine, _ = web
    seed(engine)
    tx_id = _ids(engine, A)[1]
    response = _patch(client, tx_id, {**BODY, **change})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_FIELD" and response.json()["field"] == field
    with Session(engine) as session:
        assert session.get(Transaction, tx_id).amount_satang == 2050


@pytest.mark.parametrize("raw", [
    b"[]", b"\"x\"", b"not json", json.dumps({k: v for k, v in BODY.items() if k != "category"}).encode(),
    json.dumps({**BODY, "description": "ก" * 5000}).encode(),
])
def test_patch_bad_body(web, raw):
    client, engine, _ = web
    seed(engine)
    response = _patch(client, _ids(engine, A)[1], None, raw=raw)
    assert response.status_code == 422 and response.json()["field"] == "body"


def test_patch_accepts_today_and_keeps_legacy_category(web):
    client, engine, _ = web
    seed(engine)
    tx_id = _ids(engine, A)[1]  # expense "อาหาร A" is not a taxonomy category
    body = {**BODY, "transaction_type": "expense", "category": "อาหาร A", "description": "",
            "occurred_on": "2026-10-10"}
    response = _patch(client, tx_id, body)
    assert response.status_code == 200
    assert response.json()["category"] == "อาหาร A" and response.json()["description"] is None


def test_write_routes_reject_query_and_missing_token(web):
    client, engine, _ = web
    seed(engine)
    tx_id = _ids(engine, A)[1]
    content = json.dumps(BODY).encode()
    assert client.patch(f"/api/me/transactions/{tx_id}?x=1", content=content, headers=headers()).status_code == 400
    assert client.delete(f"/api/me/transactions/{tx_id}?x=1", headers=headers()).status_code == 400
    assert client.patch(f"/api/me/transactions/{tx_id}", content=content).status_code == 401
    assert client.delete(f"/api/me/transactions/{tx_id}").status_code == 401
    with Session(engine) as session:
        assert session.get(Transaction, tx_id).amount_satang == 2050


def test_item_read_uses_read_only_session(web, monkeypatch):
    client, engine, _ = web
    seed(engine)
    seen = []
    original = routes.get_transaction

    def read(owner, tx_id, *, session):
        seen.append(session)
        return original(owner, tx_id, session=session)

    monkeypatch.setattr(routes, "get_transaction", read)
    assert client.get(f"/api/me/transactions/{_ids(engine, A)[0]}", headers=headers()).status_code == 200
    assert isinstance(seen[0], routes.ReadOnlySession)


def test_categories_route(web):
    client, _, _ = web
    response = client.get("/api/me/categories", headers=headers())
    assert response.status_code == 200
    assert response.json() == {"expense": list(categories("expense")), "income": list(categories("income"))}
    assert client.get("/api/me/categories").status_code == 401


def test_shell_serves_transactions_with_edit_query(web):
    client, _, _ = web
    response = client.get("/app/transactions?edit=5")
    assert response.status_code == 200 and "<!doctype html>" in response.text


def test_body_read_stops_at_the_cap_without_content_length():
    import asyncio
    from starlette.requests import Request
    from webapp_auth import WebAppError
    from webapp_edit import MAX_BODY_BYTES

    pulled = []

    async def receive():
        pulled.append(1)
        return {"type": "http.request", "body": b"x" * 1024, "more_body": len(pulled) < 1000}

    request = Request({"type": "http", "method": "PATCH", "headers": []}, receive)
    with pytest.raises(WebAppError) as caught:
        asyncio.run(routes._read_body(request))
    assert (caught.value.status_code, caught.value.field) == (422, "body")
    assert len(pulled) <= MAX_BODY_BYTES // 1024 + 1
