"""LINE Flex Message builders for chat cards and quick replies (pure JSON, no I/O).

Visible amounts always come from ``messages.format_amount``; integer satang is
used only to size the month bar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Mapping

from messages import _clean, _decimal, _format_date, format_amount
from postback import HELP_TOPICS

BRAND: Final = "#D81B72"
INCOME: Final = "#1F9E74"
HEADER_BG: Final = "#FBF1E6"
MUTED: Final = "#8A6F7B"
INK: Final = "#2B1A22"
TRACK: Final = "#F1E3E9"
STRUCK: Final = "#B9A7AF"

_HEADINGS: Final = {
    "record": ("จดแล้ว! ✅", "อย่าลืมเช็กว่าถูกไหมนะครับ"),
    "edit": ("แก้แล้ว ✏️", "ตรวจอีกทีนะครับ"),
    "restore": ("เอาคืนมาแล้ว ↩️", "กลับมาอยู่ในรายการแล้ว"),
    "delete": ("ลบแล้ว 🗑️", "กดเอาคืนได้ภายใน 10 นาที"),
}
_HELP_LABELS: Final = {
    "expense": "จดรายจ่าย",
    "income": "จดรายรับ",
    "savings": "เงินออม",
    "edit": "แก้หรือลบ",
    "privacy": "ความเป็นส่วนตัว",
    "other": "ปัญหาอื่นๆ",
}


@dataclass(frozen=True)
class MonthTotal:
    category_satang: int
    type_total_satang: int

    @property
    def percent(self) -> int:
        if self.type_total_satang <= 0 or self.category_satang <= 0:
            return 0
        share = Decimal(self.category_satang) * 100 / Decimal(self.type_total_satang)
        return int(share.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def transaction_card(
    variant: str,
    tx: Mapping[str, object],
    total: MonthTotal,
    *,
    liff_id: str | None,
    image_url: str | None,
) -> dict:
    """Card for a recorded, edited or restored transaction."""

    if variant not in ("record", "edit", "restore"):
        raise ValueError(f"unknown card variant: {variant}")
    buttons = []
    if liff_id:
        buttons.append(_icon_button("✏️", {"type": "uri", "label": "แก้ไข",
                                          "uri": f"https://liff.line.me/{liff_id}/transactions?edit={int(tx['id'])}"}))
    buttons.append(_icon_button("✕", {"type": "postback", "label": "ลบ", "data": f"a=del&t={int(tx['id'])}"}))
    return _bubble(variant, tx, total, image_url, amount_struck=False, buttons=buttons)


def deleted_card(tx: Mapping[str, object], total: MonthTotal, *, action_id: str, image_url: str | None) -> dict:
    """Card for a one-tap deletion, with an undo button."""

    card = _bubble("delete", tx, total, image_url, amount_struck=True, buttons=[])
    card["footer"] = {
        "type": "box",
        "layout": "vertical",
        "paddingTop": "none",
        "contents": [{
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {"type": "postback", "label": "เอาคืน", "data": f"a=undo&id={action_id}"},
        }],
    }
    return card


def help_quick_reply() -> tuple[dict, ...]:
    return tuple(
        {"type": "action", "action": {"type": "postback", "label": _HELP_LABELS[topic], "data": f"a=help&t={topic}"}}
        for topic in HELP_TOPICS
    )


def direction_quick_reply() -> tuple[dict, ...]:
    return _message_items("รายจ่าย", "รายรับ")


def confirm_quick_reply() -> tuple[dict, ...]:
    return _message_items("ยืนยัน", "ยกเลิก")


def _message_items(*labels: str) -> tuple[dict, ...]:
    return tuple({"type": "action", "action": {"type": "message", "label": label, "text": label}} for label in labels)


def _bubble(variant, tx, total, image_url, *, amount_struck: bool, buttons: list[dict]) -> dict:
    income = str(tx.get("type")) == "income"
    kind = "รายรับ" if income else "รายจ่าย"
    accent = INCOME if income else BRAND
    category = _clean(tx.get("category"), "ไม่ระบุหมวด")
    note = _clean(tx.get("note"), "")
    item = note if note and note != "ไม่ระบุรายการ" else category
    amount = f"{'+' if income else '-'}฿{format_amount(abs(_decimal(tx.get('amount', 0))))}"
    title, subtitle = _HEADINGS[variant]

    header_contents: list[dict] = [{
        "type": "box",
        "layout": "vertical",
        "flex": 1,
        "justifyContent": "center",
        "contents": [
            {"type": "text", "text": title, "weight": "bold", "size": "lg", "color": INK},
            {"type": "text", "text": subtitle, "size": "xs", "color": MUTED, "wrap": True},
        ],
    }]
    if image_url:
        header_contents.append({"type": "image", "url": image_url, "size": "72px", "flex": 0, "aspectMode": "fit"})

    amount_text = {"type": "text", "text": amount, "weight": "bold", "size": "md", "flex": 0, "align": "end",
                   "color": STRUCK if amount_struck else accent}
    if amount_struck:
        amount_text["decoration"] = "line-through"

    body = [
        {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {"type": "box", "layout": "vertical", "flex": 0, "backgroundColor": accent, "cornerRadius": "12px",
                 "paddingStart": "8px", "paddingEnd": "8px", "paddingTop": "2px", "paddingBottom": "2px",
                 "contents": [{"type": "text", "text": kind, "size": "xxs", "color": "#FFFFFF", "weight": "bold"}]},
                {"type": "text", "text": f"· {category}", "size": "sm", "color": INK, "flex": 1, "wrap": True,
                 "maxLines": 1, "gravity": "center"},
            ],
        },
        {"type": "text", "text": _format_date(tx.get("date")) or "ไม่ระบุวันที่", "size": "xxs", "color": MUTED,
         "margin": "md"},
        {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "alignItems": "center",
            "contents": [
                {"type": "text", "text": item, "size": "md", "color": INK, "flex": 1, "wrap": True, "maxLines": 2},
                amount_text,
                *buttons,
            ],
        },
        {"type": "separator", "margin": "lg"},
        *_month_block(category, total, kind, accent),
    ]
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {"type": "box", "layout": "horizontal", "backgroundColor": HEADER_BG, "paddingAll": "16px",
                   "contents": header_contents},
        "body": {"type": "box", "layout": "vertical", "spacing": "xs", "paddingAll": "16px", "contents": body},
    }


def _month_block(category: str, total: MonthTotal, kind: str, accent: str) -> list[dict]:
    amount = format_amount(Decimal(total.category_satang) / 100)
    percent = total.percent
    track: dict = {"type": "box", "layout": "vertical", "height": "8px", "backgroundColor": TRACK,
                   "cornerRadius": "4px", "margin": "sm", "contents": []}
    if percent > 0:
        track["contents"] = [{"type": "box", "layout": "vertical", "height": "8px", "width": f"{max(percent, 2)}%",
                              "backgroundColor": accent, "cornerRadius": "4px", "contents": []}]
    else:
        track["contents"] = [{"type": "filler"}]
    return [
        {"type": "text", "text": f"{category}เดือนนี้ ฿{amount}", "size": "sm", "color": INK, "margin": "lg",
         "wrap": True, "maxLines": 2},
        track,
        {"type": "text", "text": f"{percent}% ของ{kind}", "size": "xxs", "color": MUTED, "align": "end"},
    ]


def _icon_button(label: str, action: dict) -> dict:
    return {"type": "box", "layout": "vertical", "flex": 0, "width": "32px", "height": "32px",
            "cornerRadius": "8px", "backgroundColor": "#F5EEF1", "justifyContent": "center", "action": action,
            "contents": [{"type": "text", "text": label, "size": "sm", "align": "center", "color": INK}]}
