"""Strict parser for postback data sent by MooTun's own cards and quick replies.

Anything outside the exact formats below (including the rich menu's
``richmenu=...`` postbacks) parses to ``None`` and is ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import parse_qs

HELP_TOPICS: Final = ("expense", "income", "savings", "edit", "privacy", "other")
MAX_DATA_LENGTH: Final = 300

_TRANSACTION_ID = re.compile(r"[1-9][0-9]{0,8}")
_ACTION_ID = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True)
class DeleteTx:
    transaction_id: int


@dataclass(frozen=True)
class Undo:
    action_id: str


@dataclass(frozen=True)
class HelpTopic:
    topic: str


PostbackCommand = DeleteTx | Undo | HelpTopic


def parse_postback(data: object) -> PostbackCommand | None:
    if not isinstance(data, str) or not data or len(data) > MAX_DATA_LENGTH:
        return None
    try:
        fields = parse_qs(data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    if any(len(values) != 1 for values in fields.values()):
        return None
    values = {key: items[0] for key, items in fields.items()}
    action = values.get("a")
    if action == "del" and set(values) == {"a", "t"} and _TRANSACTION_ID.fullmatch(values["t"]):
        return DeleteTx(int(values["t"]))
    if action == "undo" and set(values) == {"a", "id"} and _ACTION_ID.fullmatch(values["id"]):
        return Undo(values["id"])
    if action == "help" and set(values) == {"a", "t"} and values["t"] in HELP_TOPICS:
        return HelpTopic(values["t"])
    return None
