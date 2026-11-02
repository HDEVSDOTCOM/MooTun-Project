"""Validation for the Mini App edit form's JSON body (no database access)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from taxonomy import categories
from webapp_auth import WebAppError

MAX_BODY_BYTES = 4096
MAX_DESCRIPTION = 500
EARLIEST = date(2000, 1, 1)
FIELDS = frozenset({"transaction_type", "amount_baht", "category", "description", "occurred_on"})
# A JSON string only: numbers would pass through float before we ever see them.
AMOUNT = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,2})?")
ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


@dataclass(frozen=True)
class EditFields:
    transaction_type: str
    amount_baht: str
    category: str
    description: str | None
    occurred_on: date


def _invalid(field: str) -> WebAppError:
    return WebAppError(422, "INVALID_FIELD", field)


def parse_edit_body(raw: bytes, *, today: date, current_type: str, current_category: str) -> EditFields:
    """Strictly validate one edit; raise 422 naming the first bad field."""

    if len(raw) > MAX_BODY_BYTES:
        raise _invalid("body")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise _invalid("body") from None
    if not isinstance(body, dict) or set(body) != FIELDS:
        raise _invalid("body")

    kind = body["transaction_type"]
    if kind not in ("expense", "income"):
        raise _invalid("transaction_type")

    amount = body["amount_baht"]
    if not isinstance(amount, str) or AMOUNT.fullmatch(amount) is None or Decimal(amount) <= 0:
        raise _invalid("amount_baht")

    category = body["category"]
    if not isinstance(category, str):
        raise _invalid("category")
    category = category.strip()
    # The row's own category stays valid for its own type, so legacy rows save unchanged.
    if category not in categories(kind) and (kind, category) != (current_type, current_category):
        raise _invalid("category")

    description = body["description"]
    if description is not None:
        if not isinstance(description, str) or len(description.strip()) > MAX_DESCRIPTION:
            raise _invalid("description")
        description = description.strip() or None

    day = body["occurred_on"]
    if not isinstance(day, str) or ISO_DATE.fullmatch(day) is None:
        raise _invalid("occurred_on")
    try:
        occurred_on = date.fromisoformat(day)
    except ValueError:
        raise _invalid("occurred_on") from None
    if not EARLIEST <= occurred_on <= today:
        raise _invalid("occurred_on")

    return EditFields(kind, amount, category, description, occurred_on)
