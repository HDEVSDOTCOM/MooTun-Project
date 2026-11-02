"""Month list and analytics reads for the MINI App (Phase 2C backend)."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

import repository
import webapp_routes as routes
from models import Transaction
from test_webapp import (  # noqa: F401  (``web`` is a pytest fixture)
    A,
    B,
    NOW,
    QUERY_PATHS,
    TOKEN_B,
    TOKEN_EMPTY,
    assert_secure,
    headers,
    seed,
    web,
)


def add(engine, *rows):
    with Session(engine) as session:
        for owner, kind, satang, category, occurred_on in rows:
            session.add(Transaction(line_user_id=owner, transaction_type=kind, amount_satang=satang,
                                    category=category, description=None, occurred_on=occurred_on,
                                    created_at=NOW))
        session.commit()


def test_month_transactions_scoped_ordered_and_filtered(web):
    client, engine, _ = web
    seed(engine)
    add(engine, (A, "expense", 999, "เดินทาง", date(2026, 9, 30)),
        (A, "expense", 101, "เดินทาง", date(2026, 11, 1)))
    response = client.get("/api/me/transactions?month=2026-10", headers=headers())
    assert response.status_code == 200
    assert_secure(response)
    body = response.json()
    assert {key: body[key] for key in ("year_ce", "year_be", "month", "type", "limit", "truncated")} == {
        "year_ce": 2026, "year_be": 2569, "month": 10, "type": None, "limit": 500, "truncated": False,
    }
    assert [item["occurred_on"] for item in body["items"]] == ["2026-10-02", "2026-10-01"]
    assert [item["amount_baht"] for item in body["items"]] == ["20.50", "100.01"]
    assert all(isinstance(item["id"], int) and "line_user_id" not in item for item in body["items"])

    income = client.get("/api/me/transactions?month=2026-10&type=income", headers=headers()).json()
    assert income["type"] == "income"
    assert [item["category"] for item in income["items"]] == ["รายรับ A"]

    other = client.get("/api/me/transactions?month=2026-10", headers=headers(TOKEN_B)).json()
    assert [item["category"] for item in other["items"]] == ["อาหาร B"]
    empty = client.get("/api/me/transactions?month=2026-10", headers=headers(TOKEN_EMPTY)).json()
    assert empty["items"] == [] and empty["truncated"] is False


def test_month_transactions_caps_at_limit_and_flags_truncation(web, monkeypatch):
    client, engine, _ = web
    monkeypatch.setattr(routes, "MONTH_LIMIT", 2)
    add(engine, *[(A, "expense", 100 + day, "อาหาร", date(2026, 10, day)) for day in (1, 2, 3)])
    body = client.get("/api/me/transactions?month=2026-10", headers=headers()).json()
    assert body["truncated"] is True and body["limit"] == 2
    assert [item["occurred_on"] for item in body["items"]] == ["2026-10-03", "2026-10-02"]


def test_monthly_series_spans_year_boundary_and_fills_empty_months(web, monkeypatch):
    client, engine, _ = web
    # 2026-01-31 18:00 UTC is already February 1 in Bangkok.
    monkeypatch.setattr(routes, "utc_now", lambda: datetime(2026, 1, 31, 18, 0, tzinfo=timezone.utc))
    add(engine, (A, "income", 50000, "เงินเดือน", date(2025, 12, 25)),
        (A, "expense", 1234, "อาหาร", date(2025, 12, 31)),
        (A, "expense", 1, "อาหาร", date(2026, 2, 1)),
        (A, "expense", 7777, "อาหาร", date(2025, 8, 31)),
        (B, "expense", 9999, "อาหาร", date(2026, 1, 15)))
    body = client.get("/api/me/analytics/monthly?months=3", headers=headers()).json()
    assert body["months"] == 3
    assert body["items"] == [
        {"year_ce": 2025, "year_be": 2568, "month": 12, "income_baht": "500.00", "expense_baht": "12.34",
         "income_satang": 50000, "expense_satang": 1234},
        {"year_ce": 2026, "year_be": 2569, "month": 1, "income_baht": "0.00", "expense_baht": "0.00",
         "income_satang": 0, "expense_satang": 0},
        {"year_ce": 2026, "year_be": 2569, "month": 2, "income_baht": "0.00", "expense_baht": "0.01",
         "income_satang": 0, "expense_satang": 1},
    ]
    assert len(client.get("/api/me/analytics/monthly", headers=headers()).json()["items"]) == 6


def test_category_totals_ordered_with_exact_shares(web):
    client, engine, _ = web
    add(engine, (A, "expense", 200, "อาหาร", date(2026, 10, 1)),
        (A, "expense", 100, "อาหาร", date(2026, 10, 2)),
        (A, "expense", 150, "เดินทาง", date(2026, 10, 3)),
        (A, "expense", 150, "ของใช้", date(2026, 10, 4)),
        (A, "income", 999, "เงินเดือน", date(2026, 10, 5)),
        (A, "expense", 5000, "อาหาร", date(2026, 9, 30)),
        (B, "expense", 5000, "อาหาร", date(2026, 10, 1)))
    body = client.get("/api/me/analytics/categories?month=2026-10", headers=headers()).json()
    assert body["type"] == "expense"
    assert body["total_baht"] == "6.00" and body["total_satang"] == 600
    assert body["items"] == [
        {"category": "อาหาร", "amount_baht": "3.00", "amount_satang": 300, "transaction_count": 2,
         "share_percent": "50.00"},
        {"category": "ของใช้", "amount_baht": "1.50", "amount_satang": 150, "transaction_count": 1,
         "share_percent": "25.00"},
        {"category": "เดินทาง", "amount_baht": "1.50", "amount_satang": 150, "transaction_count": 1,
         "share_percent": "25.00"},
    ]
    income = client.get("/api/me/analytics/categories?month=2026-10&type=income", headers=headers()).json()
    assert [item["category"] for item in income["items"]] == ["เงินเดือน"]
    empty = client.get("/api/me/analytics/categories?month=2026-10", headers=headers(TOKEN_EMPTY)).json()
    assert empty["items"] == [] and empty["total_baht"] == "0.00"


def test_category_share_rounds_half_up(web):
    client, engine, _ = web
    add(engine, (A, "expense", 1, "ก", date(2026, 10, 1)), (A, "expense", 2, "ข", date(2026, 10, 1)))
    items = client.get("/api/me/analytics/categories?month=2026-10", headers=headers()).json()["items"]
    assert [item["share_percent"] for item in items] == ["66.67", "33.33"]


@pytest.mark.parametrize("path", [
    "/api/me/transactions", "/api/me/transactions?type=income",
    "/api/me/transactions?month=2026-13", "/api/me/transactions?month=2026-1",
    "/api/me/transactions?month=1800-01", "/api/me/transactions?month=2026-10-01",
    "/api/me/transactions?month=2026-10&type=all", "/api/me/transactions?month=2026-10&type=",
    "/api/me/transactions?month=2026-10&month=2026-09",
    "/api/me/transactions?month=2026-10&line_user_id=" + B,
    "/api/me/transactions?month=2026-10&limit=5000",
    "/api/me/analytics/monthly?months=24", "/api/me/analytics/monthly?months=6&months=6",
    "/api/me/analytics/monthly?month=2026-10",
    "/api/me/analytics/categories", "/api/me/analytics/categories?month=２０２６-10",
    "/api/me/analytics/categories?month=2026-10&user_id=" + B,
])
def test_query_allowlist_rejects_before_any_sql(web, path):
    client, _, state = web
    response = client.get(path, headers=headers())
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"
    assert len(state["calls"]) == 1
    assert not state["sql"]
    assert_secure(response)


@pytest.mark.parametrize("path", QUERY_PATHS)
def test_new_reads_require_authentication_before_validation(web, path):
    client, _, state = web
    for bad in (f"{path}&x=1" if "?" in path else f"{path}?x=1", path):
        response = client.get(bad)
        assert response.status_code == 401
    assert not state["calls"] and not state["sql"]


@pytest.mark.parametrize("path", QUERY_PATHS)
def test_authentication_runs_once_and_session_opens_after_it(web, path, monkeypatch):
    client, _, state = web
    opened = []
    original = routes._read_session

    def tracked():
        opened.append(len(state["calls"]))
        yield from original()

    monkeypatch.setattr(routes, "_read_session", tracked)
    assert client.get(path, headers=headers()).status_code == 200
    assert len(state["calls"]) == 1
    assert opened == [1]


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("path", ["/api/me/transactions", "/api/me/analytics/monthly",
                                  "/api/me/analytics/categories"])
def test_new_reads_are_get_only(web, method, path):
    client, _, state = web
    response = client.request(method, path, headers=headers())
    assert response.status_code == 405
    assert not state["sql"] and not state["calls"]


def test_repository_rejects_invalid_arguments():
    with pytest.raises(ValueError):
        repository.list_month_transactions(A, 2026, 10, "transfer")
    with pytest.raises(ValueError):
        repository.list_month_transactions(A, 2026, 10, limit=501)
    with pytest.raises(ValueError):
        repository.monthly_totals_series(A, 2026, 10, 13)
    with pytest.raises(ValueError):
        repository.category_totals(A, 2026, 13, "expense")
