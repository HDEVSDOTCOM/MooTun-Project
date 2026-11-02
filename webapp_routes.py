"""Static web shell and the bounded, rollback-only financial reads."""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import database
import media
from repository import (
    category_totals,
    delete_transaction_by_id,
    get_transaction,
    get_savings_goal,
    list_month_transactions,
    list_recent_transactions,
    monthly_summary,
    monthly_totals_series,
    update_transaction,
)
from taxonomy import categories
from webapp_edit import MAX_BODY_BYTES, parse_edit_body
from webapp_auth import (
    ERROR_MESSAGES,
    OwnerQuery,
    QueryRule,
    WebAppError,
    is_web_path,
    owner_with_query,
    require_webapp,
    verified_owner,
)


# Vite build output (frontend/ -> webapp/dist/), produced on deploy and gitignored.
ROOT = Path(__file__).resolve().parent / "webapp" / "dist"
BANGKOK = ZoneInfo("Asia/Bangkok")
router = APIRouter()
# Client-side routes that return the SPA shell. Must match TABS in frontend/src/components/TabBar.tsx.
SPA_TABS = ("summary", "analysis", "transactions", "savings", "settings")
# Vite emits flat, hashed file names. No slashes, no leading dot, fixed extensions.
ASSET_NAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}\.(?:js|css|woff2?|svg|png|webp)")
ASSET_TYPES = {
    "js": "text/javascript", "css": "text/css", "woff2": "font/woff2", "woff": "font/woff",
    "svg": "image/svg+xml", "png": "image/png", "webp": "image/webp",
}
MONTH_LIMIT = 500
ANALYTICS_MONTHS = ("3", "6", "12")
MONTH = QueryRule(re.compile(r"(?:19|20)[0-9]{2}-(?:0[1-9]|1[0-2])"), required=True)
TYPE = QueryRule(re.compile(r"income|expense"))
# SDK 2.31.2's init/login use the LINE API/Access origins and its translation CDN.
# The SDK loads platform bridge extensions from static.line-scdn.net.
# No UTS/analytics origin, wildcard, inline script, or eval permission is granted.
CSP = (
    "default-src 'none'; base-uri 'none'; object-src 'none'; "
    "script-src 'self' https://static.line-scdn.net; style-src 'self'; "
    "font-src 'self'; img-src 'self' data:; "
    "connect-src 'self' https://api.line.me https://access.line.me "
    "https://liffsdk.line-scdn.net; "
    "frame-src https://access.line.me https://liff.line.me; "
    "frame-ancestors 'none'; form-action 'none'"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def bangkok_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BANGKOK).isoformat()


class ReadOnlyViolation(SQLAlchemyError):
    pass


class ReadOnlySession(Session):
    """Prevent an accidental explicit ORM flush/commit as well as autoflush."""

    def flush(self, objects=None) -> None:
        raise ReadOnlyViolation("Web sessions cannot flush")

    def commit(self) -> None:
        raise ReadOnlyViolation("Web sessions cannot commit")


def _only_select(state) -> None:
    if not state.is_select or state.is_insert or state.is_update or state.is_delete:
        raise ReadOnlyViolation("Web sessions only allow SELECT")


def _read_session() -> Iterator[Session]:
    session = ReadOnlySession(bind=database.engine, autoflush=False, expire_on_commit=False)
    event.listen(session, "do_orm_execute", _only_select)
    try:
        yield session
    except SQLAlchemyError:
        raise WebAppError(503, "DATA_UNAVAILABLE") from None
    finally:
        try:
            session.rollback()
        finally:
            session.close()


def read_session(owner: Annotated[str, Depends(verified_owner)]) -> Iterator[Session]:
    # Authentication (including query validation) completes before session creation.
    yield from _read_session()


def read_session_after(authenticate):
    """A read session that opens only after ``authenticate`` (cached per request) succeeds."""

    # A default (not Annotated) because postponed annotations cannot see the closure.
    def dependency(_: OwnerQuery = Depends(authenticate)) -> Iterator[Session]:
        yield from _read_session()

    return dependency


Owner = Annotated[str, Depends(verified_owner)]
ReadSession = Annotated[Session, Depends(read_session)]

month_query = owner_with_query({"month": MONTH, "type": TYPE})
months_query = owner_with_query({"months": QueryRule(re.compile("|".join(ANALYTICS_MONTHS)))})
MonthQuery = Annotated[OwnerQuery, Depends(month_query)]
MonthsQuery = Annotated[OwnerQuery, Depends(months_query)]
MonthSession = Annotated[Session, Depends(read_session_after(month_query))]
MonthsSession = Annotated[Session, Depends(read_session_after(months_query))]


def _month_param(query: OwnerQuery) -> tuple[int, int]:
    year, month = query.params["month"].split("-")
    return int(year), int(month)


def _transaction_item(item) -> dict:
    return {
        "id": item.id,
        "transaction_type": item.transaction_type,
        "amount_baht": money(item.amount),
        "category": item.category,
        "description": item.description,
        "occurred_on": item.occurred_on.isoformat(),
        "created_at": bangkok_timestamp(item.created_at),
    }


def _satang_baht(satang: int) -> str:
    return money(Decimal(satang) / Decimal(100))


def _shell(request: Request) -> FileResponse:
    require_webapp(request)
    index = ROOT / "index.html"
    if not index.is_file():
        raise WebAppError(503, "WEBAPP_UNAVAILABLE")
    return FileResponse(index, media_type="text/html")


@router.get("/app/", include_in_schema=False)
def shell(request: Request):
    return _shell(request)


@router.get("/app/assets/{name}", include_in_schema=False)
def asset(name: str, request: Request):
    require_webapp(request)
    path = ROOT / "assets" / name
    if ASSET_NAME.fullmatch(name) is None or not path.is_file():
        raise WebAppError(404, "NOT_FOUND")
    return FileResponse(path, media_type=ASSET_TYPES[name.rsplit(".", 1)[1]])


# Card artwork for chat Flex messages; LINE fetches these, so no WEBAPP_ENABLED gate.
@router.get("/media/{name}", include_in_schema=False)
def card_media(name: str):
    path = media.MEDIA_DIR / name
    if media.MEDIA_NAME.fullmatch(name) is None or not path.is_file():
        raise WebAppError(404, "NOT_FOUND")
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/app/config.json", include_in_schema=False)
def frontend_config(request: Request):
    config = require_webapp(request)
    return {"liff_id": config.liff_id, "environment": "Developing"}


# Declared after /app/config.json so the literal path wins.
@router.get("/app/{tab}", include_in_schema=False)
def tab_shell(tab: str, request: Request):
    if tab not in SPA_TABS:
        require_webapp(request)
        raise WebAppError(404, "NOT_FOUND")
    return _shell(request)


@router.get("/api/me/summary")
def summary(owner: Owner, session: ReadSession):
    now = utc_now()
    local = now.astimezone(BANGKOK)
    totals = monthly_summary(owner, local.year, local.month, session=session)
    return {
        "currency": "THB",
        "timezone": "Asia/Bangkok",
        "year_ce": local.year,
        "year_be": local.year + 543,
        "month": local.month,
        "income_baht": money(totals["income"]),
        "expense_baht": money(totals["expense"]),
        "balance_baht": money(totals["balance"]),
        "transaction_count": totals["transaction_count"],
        "as_of": now.isoformat(),
    }


@router.get("/api/me/transactions/recent")
def recent(owner: Owner, session: ReadSession):
    now = utc_now()
    items = list_recent_transactions(owner, limit=5, session=session)
    return {
        "limit": 5,
        "items": [_transaction_item(item) for item in items],
        "as_of": now.isoformat(),
    }


@router.get("/api/me/transactions")
def month_transactions(query: MonthQuery, session: MonthSession):
    now = utc_now()
    year, month = _month_param(query)
    transaction_type = query.params.get("type")
    items = list_month_transactions(
        query.owner, year, month, transaction_type, limit=MONTH_LIMIT, session=session
    )
    return {
        "year_ce": year,
        "year_be": year + 543,
        "month": month,
        "type": transaction_type,
        "limit": MONTH_LIMIT,
        "truncated": len(items) > MONTH_LIMIT,
        "items": [_transaction_item(item) for item in items[:MONTH_LIMIT]],
        "as_of": now.isoformat(),
    }


@router.get("/api/me/analytics/monthly")
def analytics_monthly(query: MonthsQuery, session: MonthsSession):
    now = utc_now()
    local = now.astimezone(BANGKOK)
    months = int(query.params.get("months", "6"))
    series = monthly_totals_series(query.owner, local.year, local.month, months, session=session)
    return {
        "months": months,
        "items": [
            {
                "year_ce": row["year"],
                "year_be": row["year"] + 543,
                "month": row["month"],
                "income_baht": _satang_baht(row["income"]),
                "expense_baht": _satang_baht(row["expense"]),
                "income_satang": row["income"],
                "expense_satang": row["expense"],
            }
            for row in series
        ],
        "as_of": now.isoformat(),
    }


@router.get("/api/me/analytics/categories")
def analytics_categories(query: MonthQuery, session: MonthSession):
    now = utc_now()
    year, month = _month_param(query)
    transaction_type = query.params.get("type", "expense")
    rows = category_totals(query.owner, year, month, transaction_type, session=session)
    total = sum(row["satang"] for row in rows)
    return {
        "year_ce": year,
        "year_be": year + 543,
        "month": month,
        "type": transaction_type,
        "total_baht": _satang_baht(total),
        "total_satang": total,
        "items": [
            {
                "category": row["category"],
                "amount_baht": _satang_baht(row["satang"]),
                "amount_satang": row["satang"],
                "transaction_count": row["transaction_count"],
                "share_percent": money(Decimal(row["satang"]) * 100 / Decimal(total)),
            }
            for row in rows
        ],
        "as_of": now.isoformat(),
    }


@router.get("/api/me/savings")
def savings(owner: Owner, session: ReadSession):
    now = utc_now()
    goal = get_savings_goal(owner, session=session)
    result = None
    if goal is not None:
        progress = (Decimal(goal.saved_satang) * 100 / Decimal(goal.target_satang))
        result = {
            "title": goal.title,
            "target_baht": money(goal.target_amount),
            "saved_baht": money(goal.saved_amount),
            "remaining_baht": money(goal.remaining_amount),
            "progress_percent": money(min(Decimal(100), max(Decimal(0), progress))),
            "deadline": goal.deadline.isoformat() if goal.deadline else None,
        }
    return {"goal": result, "as_of": now.isoformat()}


# The :int path convertor keeps "recent" and other words off these routes (405, not 404).
MAX_TX_ID = 999_999_999


def _tx_id(value: int) -> int:
    # Ids fit the INTEGER column; anything larger is simply not found.
    if not 0 < value <= MAX_TX_ID:
        raise WebAppError(404, "NOT_FOUND")
    return value


@router.get("/api/me/transactions/{tx_id:int}")
def transaction_item(tx_id: int, owner: Owner, session: ReadSession):
    item = get_transaction(owner, _tx_id(tx_id), session=session)
    if item is None:
        raise WebAppError(404, "NOT_FOUND")
    return _transaction_item(item)


def _apply_edit(owner: str, tx_id: int, raw: bytes) -> dict:
    today = utc_now().astimezone(BANGKOK).date()
    try:
        with database.session_scope() as session:
            current = get_transaction(owner, tx_id, session=session)
            if current is None:
                raise WebAppError(404, "NOT_FOUND")
            fields = parse_edit_body(
                raw, today=today, current_type=current.transaction_type, current_category=current.category,
            )
            item = update_transaction(
                owner, tx_id,
                transaction_type=fields.transaction_type, amount=fields.amount_baht,
                category=fields.category, description=fields.description,
                occurred_on=fields.occurred_on, session=session,
            )
            return _transaction_item(item)
    except SQLAlchemyError:
        raise WebAppError(503, "DATA_UNAVAILABLE") from None


def _apply_delete(owner: str, tx_id: int) -> None:
    try:
        with database.session_scope() as session:
            if not delete_transaction_by_id(owner, tx_id, session=session):
                raise WebAppError(404, "NOT_FOUND")
    except SQLAlchemyError:
        raise WebAppError(503, "DATA_UNAVAILABLE") from None


async def _read_body(request: Request) -> bytes:
    # Count while streaming: a chunked request has no Content-Length to check up front.
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise WebAppError(422, "INVALID_FIELD", "body")
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > MAX_BODY_BYTES:
            raise WebAppError(422, "INVALID_FIELD", "body")
    return bytes(raw)


@router.patch("/api/me/transactions/{tx_id:int}")
async def edit_transaction(tx_id: int, owner: Owner, request: Request):
    target = _tx_id(tx_id)
    raw = await _read_body(request)
    return await run_in_threadpool(_apply_edit, owner, target, raw)


@router.delete("/api/me/transactions/{tx_id:int}", status_code=204)
async def remove_transaction(tx_id: int, owner: Owner):
    await run_in_threadpool(_apply_delete, owner, _tx_id(tx_id))
    return Response(status_code=204)


@router.get("/api/me/categories")
def category_list(owner: Owner):
    return {"expense": list(categories("expense")), "income": list(categories("income"))}


def register_webapp(app: FastAPI) -> None:
    def error_response(status_code: int, code: str, field: str | None = None) -> JSONResponse:
        content = {"code": code, "message": ERROR_MESSAGES[code]}
        if field is not None:
            content["field"] = field
        return JSONResponse(status_code=status_code, content=content)

    @app.exception_handler(WebAppError)
    async def web_error(request: Request, exc: WebAppError):
        return error_response(exc.status_code, exc.code, exc.field)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        web_path = is_web_path(request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            if not web_path:
                raise
            # Unexpected web failures must also be sanitized and non-cacheable.
            # Do not format/log exceptions that could embed credentials or data.
            code = "DATA_UNAVAILABLE" if request.url.path.startswith("/api/me/") else "WEBAPP_UNAVAILABLE"
            response = error_response(503, code)
        if web_path:
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Content-Security-Policy"] = CSP
            if request.url.path.startswith("/api/me/"):
                response.headers["Vary"] = "Authorization"
        return response

    app.include_router(router)
