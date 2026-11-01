"""Rich menu definitions (pure data). See plan/active/phase2b_rich_menu_spec.md."""

from __future__ import annotations

from pathlib import Path

CANVAS = (2500, 1686)
LIFF_ID = "2011960945-14GtwIlx"
NAME_PREFIX = "mootoon-"
ALIASES = {"page1": "mootoon-page1", "page2": "mootoon-page2"}
CHAT_BAR_TEXT = "เมนู"

_ASSETS = Path(__file__).resolve().parent / "richmenu"
IMAGE_PATHS = {"page1": _ASSETS / "page1.jpg", "page2": _ASSETS / "page2.jpg"}

# (x, y, width, height). Tile bounds from the owner art scaled by 2500/1527,
# gaps split at midpoints so the areas tile the whole canvas.
AREAS = {
    "BIG": (0, 0, 1375, 1067),
    "WIDE": (0, 1067, 1375, 619),
    "R1A": (1375, 0, 563, 539),
    "R1B": (1938, 0, 562, 539),
    "R2A": (1375, 539, 563, 520),
    "R2B": (1938, 539, 562, 520),
    "R3A": (1375, 1059, 563, 627),
    "R3B": (1938, 1059, 562, 627),
}


def _message(label: str, text: str) -> dict:
    return {"type": "message", "label": label, "text": text}


def _liff(label: str, tab: str) -> dict:
    return {"type": "uri", "label": label, "uri": f"https://liff.line.me/{LIFF_ID}/{tab}"}


def _keyboard(label: str, data: str, fill_in: str | None = None) -> dict:
    action = {"type": "postback", "label": label, "data": f"richmenu={data}", "inputOption": "openKeyboard"}
    if fill_in is not None:
        action["fillInText"] = fill_in
    return action


def _switch(label: str, page: str) -> dict:
    return {"type": "richmenuswitch", "label": label, "richMenuAliasId": ALIASES[page], "data": f"richmenu={page}"}


# Keys follow AREAS order. Message texts must stay valid parser commands (test_richmenu.py).
PAGES = {
    "page1": {
        "BIG": _keyboard("จดรายรับรายจ่าย", "compose"),
        "WIDE": _switch("เพิ่มเติม", "page2"),
        "R1A": _message("สรุป", "สรุปเดือนนี้"),
        "R1B": _liff("วิเคราะห์", "analysis"),
        "R2A": _liff("หมวด/งบ", "analysis"),
        "R2B": _message("รายการ", "รายการล่าสุด"),
        "R3A": _liff("ตั้งค่า", "settings"),
        "R3B": _message("Help", "ช่วยเหลือ"),
    },
    "page2": {
        "BIG": _message("เป้าหมายการออม", "เป้าหมาย"),
        "WIDE": _switch("กลับหน้าแรก", "page1"),
        "R1A": _keyboard("สร้างเป้า", "goal", "ตั้งเป้า "),
        "R1B": _keyboard("ออม", "save", "ออม "),
        "R2A": _message("ลบล่าสุด", "ลบล่าสุด"),
        "R2B": _message("ส่งออกข้อมูล", "ส่งออกข้อมูล"),
        "R3A": _keyboard("เสนอแนะ", "feedback", "เสนอแนะ "),
        "R3B": _message("วิธีใช้", "ช่วยเหลือ"),
    },
}


def build_richmenu(page: str) -> dict:
    """Return the LINE rich menu object for ``page`` (raises KeyError if unknown)."""
    areas = PAGES[page]
    width, height = CANVAS
    return {
        "size": {"width": width, "height": height},
        "selected": True,
        "name": ALIASES[page],
        "chatBarText": CHAT_BAR_TEXT,
        "areas": [
            {"bounds": {"x": x, "y": y, "width": w, "height": h}, "action": areas[name]}
            for name, (x, y, w, h) in AREAS.items()
        ],
    }
