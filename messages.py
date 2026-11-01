"""Thai text-message formatting for MooToon.

The formatters accept ``TypedDict``-shaped mappings, but at runtime ordinary
dictionaries are enough.  This keeps database and webhook integration simple.

Copy style: lead with the result, one idea per line, plain spoken Thai, a blank
line between blocks, and commands the user can type in straight double quotes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Iterable, Mapping, NotRequired, TypedDict


SAFE_LINE_TEXT_LIMIT: Final = 4_900

THAI_MONTHS: Final = (
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
)
THAI_MONTHS_SHORT: Final = (
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
)

UNKNOWN_HEADING: Final = "หมูตุ๋นยังไม่เข้าใจข้อความนี้ 🐷"
HELP_HINT: Final = 'พิมพ์ "ช่วยเหลือ" ดูคำสั่งทั้งหมด'

# Parser reasons stay stable (code compares them); users see these instead.
FRIENDLY_REASONS: Final[dict[str, str]] = {
    "ไม่รู้จักคำสั่ง": UNKNOWN_HEADING,
    "ไม่มีข้อความให้ประมวลผล": "ยังไม่ได้พิมพ์อะไรเลยครับ",
    "กรุณาระบุว่าเป็นรายรับหรือรายจ่าย": 'บอกหน่อยว่าเป็นรายรับหรือรายจ่ายครับ เช่น "จ่าย ของขวัญ 300" หรือ "รับ ค่าขนม 500"',
    "กรุณาระบุจำนวนเงินของเป้าหมาย": 'เป้านี้กี่บาทครับ? เช่น "ตั้งเป้า 1500 ซื้อหนังสือ"',
    "กรุณาระบุจำนวนเงินที่ออม": 'ออมกี่บาทครับ? เช่น "ออม 100"',
    "คำสั่งเพิ่มเงินออมมีข้อมูลที่ไม่รู้จัก": 'คำสั่งออมใส่แค่จำนวนเงินพอครับ เช่น "ออม 100"',
    "จำนวนเงินต้องมากกว่า 0": "จำนวนเงินต้องมากกว่า 0 บาทครับ",
    "จำนวนเงินมีทศนิยมได้ไม่เกิน 2 ตำแหน่ง": "จำนวนเงินใส่ทศนิยมได้ไม่เกิน 2 หลักครับ เช่น 45.50",
    "รูปแบบจำนวนเงินไม่ถูกต้อง": "อ่านจำนวนเงินไม่ออกครับ ลองพิมพ์เป็นตัวเลข เช่น 50 หรือ 1,250",
    "พบจำนวนเงินมากกว่าหนึ่งค่า": "เจอตัวเลขเงินมากกว่าหนึ่งจำนวน ส่งทีละรายการนะครับ",
    "พบทั้งรายรับและรายจ่ายในข้อความเดียวกัน": "ข้อความนี้มีทั้งรายรับและรายจ่าย แยกส่งทีละรายการนะครับ",
    "พบวันที่มากกว่าหนึ่งค่า": "เจอวันที่มากกว่าหนึ่งวัน ใส่วันเดียวพอครับ",
    "วันที่ไม่ถูกต้อง": 'วันที่ดูไม่ถูกต้องครับ ลองใหม่ เช่น "ข้าว 50 เมื่อวาน"',
    "ข้อความนี้เป็นการปฏิเสธ จึงยังไม่บันทึก": "ข้อความนี้เป็นประโยคปฏิเสธ เลยยังไม่จดให้ครับ",
    "ข้อความนี้ดูเป็นรายการที่ยังไม่เกิดขึ้น จึงยังไม่บันทึก": "ดูเหมือนเป็นเรื่องที่ยังไม่เกิดขึ้น เลยยังไม่จดให้ครับ",
    "ชื่อรายการยาวเกิน 500 ตัวอักษร": "ชื่อรายการยาวไปหน่อย ได้ไม่เกิน 500 ตัวอักษรครับ",
    "ชื่อหมวดยาวเกิน 100 ตัวอักษร": "ชื่อหมวดยาวไปหน่อย ได้ไม่เกิน 100 ตัวอักษรครับ",
    "ชื่อเป้าหมายยาวเกิน 200 ตัวอักษร": "ชื่อเป้าหมายยาวไปหน่อย ได้ไม่เกิน 200 ตัวอักษรครับ",
    "ยังไม่มีข้อมูลธุรกรรมที่ใช้เติมรายการ": "ยังจดไม่ได้ ขาดข้อมูลอีกนิดครับ ตอบเฉพาะที่ถามได้เลย",
    "ยังไม่มีข้อมูลใหม่ที่ใช้เติมรายการ": "ข้อความนี้ยังไม่มีข้อมูลที่ขาดอยู่ครับ ตอบเฉพาะที่ถามได้เลย",
    'ข้อมูลนี้ขัดกับรายการที่ค้างไว้ครับ กรุณาส่งข้อมูลที่ขาด หรือพิมพ์ "ยกเลิก"':
        'ข้อความนี้ไม่ตรงกับรายการที่ถามค้างไว้ครับ ตอบเฉพาะที่ขาด หรือพิมพ์ "ยกเลิก"',
    'กรุณาระบุข้อมูลใหม่หลังคำว่า "แก้ไข" ครับ': 'พิมพ์ข้อมูลใหม่ต่อจากคำว่า "แก้ไข" ครับ เช่น "แก้ไข ข้าว 60"',
    "คำสั่งแก้ไขต้องระบุรายการและจำนวนเงินให้ครบในข้อความเดียวครับ":
        'แก้ไขต้องใส่ทั้งชื่อรายการและจำนวนเงินครับ เช่น "แก้ไข ข้าว 60"',
}


class Transaction(TypedDict):
    amount: int | float | Decimal | str
    type: str
    category: NotRequired[str]
    date: NotRequired[date | datetime | str]
    note: NotRequired[str]


class CategoryTotal(TypedDict):
    category: str
    amount: int | float | Decimal | str


class MonthlySummary(TypedDict):
    income: int | float | Decimal | str
    expense: int | float | Decimal | str
    month: NotRequired[str]
    balance: NotRequired[int | float | Decimal | str]
    transaction_count: NotRequired[int]
    top_categories: NotRequired[list[CategoryTotal]]


class SavingsGoal(TypedDict):
    name: str
    target: int | float | Decimal | str
    saved: int | float | Decimal | str
    due_date: NotRequired[date | datetime | str]


def format_amount(value: object) -> str:
    """Format a baht amount with separators and only meaningful decimals."""

    amount = _decimal(value)
    if amount == amount.to_integral_value():
        return f"{amount:,.0f}"
    rendered = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return rendered


def buddhist_year(year: int) -> int:
    return year + 543


def format_buddhist_date(value: date | datetime) -> str:
    """Short Thai date for chat, e.g. ``1 พ.ย. 69``."""

    return f"{value.day} {THAI_MONTHS_SHORT[value.month - 1]} {buddhist_year(value.year) % 100:02d}"


def format_buddhist_month(value: date | datetime) -> str:
    return f"เดือน{THAI_MONTHS[value.month - 1]} {buddhist_year(value.year)}"


def format_transaction_confirmation(transaction: Mapping[str, object]) -> str:
    """Confirm one saved income or expense transaction in Thai."""

    kind = _kind(transaction.get("type"))
    amount = abs(_decimal(transaction.get("amount", 0)))
    return limit_line_text(
        f"✅ จดแล้ว! {kind} {format_amount(amount)} บาท\n"
        f"{_details(transaction)}\n\n"
        'จดผิด? พิมพ์ "ลบล่าสุด" ได้เลย'
    )


def format_edit_confirmation(transaction: Mapping[str, object]) -> str:
    """Confirm that the latest transaction was replaced in Thai."""

    kind = _kind(transaction.get("type"))
    amount = abs(_decimal(transaction.get("amount", 0)))
    return limit_line_text(
        f"✏️ แก้แล้ว! ตอนนี้เป็น{kind} {format_amount(amount)} บาท\n"
        f"{_details(transaction)}"
    )


def format_delete_confirmation_prompt(transaction: Mapping[str, object]) -> str:
    """Identify the exact transaction awaiting deletion confirmation."""

    kind = _kind(transaction.get("type"))
    amount = abs(_decimal(transaction.get("amount", 0)))
    return limit_line_text(
        "ลบรายการนี้ไหมครับ?\n"
        f"{kind} {format_amount(amount)} บาท\n"
        f"{_details(transaction, missing_date='ไม่ระบุวันที่')}\n\n"
        'พิมพ์ "ยืนยัน" เพื่อลบ หรือ "ยกเลิก" ถ้าไม่ลบ'
    )


def format_delete_success(transaction: Mapping[str, object]) -> str:
    """Confirm a completed deletion and advertise the 10-minute undo window."""

    return limit_line_text(
        "🗑️ ลบแล้ว\n"
        f"{_short_line(transaction)}\n\n"
        'เผลอลบ? พิมพ์ "เลิกทำ" ภายใน 10 นาทีเพื่อเอาคืน'
    )


def format_delete_all_confirmation_prompt(transaction_count: int) -> str:
    """Warn before irreversibly erasing every piece of the user's data."""

    return limit_line_text(
        "⚠️ จะลบข้อมูลทั้งหมดจริงไหมครับ?\n"
        f"รายการ {transaction_count:,} รายการ เป้าหมายการออม และสิ่งที่ค้างไว้จะหายหมด "
        "และเอาคืนไม่ได้\n"
        "(ระบบยังเก็บบันทึกการทำงานบางส่วนไว้ เพื่อป้องกันข้อผิดพลาด)\n\n"
        'พิมพ์ "ยืนยัน" เพื่อลบทั้งหมด หรือ "ยกเลิก" ถ้าไม่ลบ'
    )


def format_delete_all_success() -> str:
    """Confirm a completed total wipe without advertising an undo window."""

    return limit_line_text(
        "🗑️ ลบข้อมูลทั้งหมดแล้ว\n"
        "ลบรายการ เป้าหมายการออม และสิ่งที่ค้างไว้ให้หมดแล้วครับ"
    )


def format_delete_all_cancelled() -> str:
    return "โอเค ไม่ลบแล้ว ข้อมูลยังอยู่ครบครับ"


def format_delete_all_no_data() -> str:
    return "ยังไม่มีข้อมูลให้ลบครับ"


def format_delete_all_expired() -> str:
    return 'คำสั่งลบทั้งหมดหมดเวลาแล้ว ถ้ายังอยากลบ พิมพ์ "ลบข้อมูลทั้งหมด" อีกครั้งครับ'


def format_undo_restored(transaction: Mapping[str, object]) -> str:
    """Confirm that a deleted transaction was restored from its snapshot."""

    return limit_line_text(f"↩️ เอาคืนมาแล้ว\n{_short_line(transaction)}")


def format_undo_expired() -> str:
    return "เลย 10 นาทีแล้ว เลยเอารายการที่ลบคืนมาไม่ได้ครับ"


def format_undo_unavailable() -> str:
    return "ไม่มีรายการที่เพิ่งลบให้เอาคืนครับ"


def format_delete_not_confirmed_yet() -> str:
    return 'ยังไม่ได้ลบอะไรเลยครับ พิมพ์ "ยืนยัน" เพื่อลบ หรือ "ยกเลิก" ถ้าไม่ลบ'


def format_undo_id_collision() -> str:
    return "เอารายการคืนไม่ได้ เพราะมีข้อมูลอื่นซ้ำกันอยู่ครับ"


def format_recent_transactions(
    transactions: Iterable[Mapping[str, object]],
    *,
    limit: int = 10,
) -> str:
    """Render recent transactions as a compact list, newest first."""

    if limit <= 0:
        return "ยังไม่มีรายการให้ดูครับ"

    items = list(transactions)[:limit]
    if not items:
        return 'ยังไม่มีรายการเลย ลองพิมพ์ "ข้าว 50" ดูครับ'

    lines = ["🧾 รายการล่าสุด", ""]
    for item in items:
        kind = _kind(item.get("type"))
        sign = "+" if kind == "รายรับ" else "−"
        icon = "🟢" if kind == "รายรับ" else "🔴"
        amount = format_amount(abs(_decimal(item.get("amount", 0))))
        category = _clean(item.get("category"), "ไม่ระบุหมวด")
        happened_on = _format_date(item.get("date")) or "ไม่ระบุวันที่"
        lines.append(f"{icon} {happened_on} · {category} · {sign}{amount} บาท")

    return limit_line_text("\n".join(lines))


def format_monthly_summary(summary: Mapping[str, object]) -> str:
    """Render totals and optional leading expense categories for a month."""

    income = _decimal(summary.get("income", 0))
    expense = abs(_decimal(summary.get("expense", 0)))
    balance_value = summary.get("balance")
    balance = (
        _decimal(balance_value) if balance_value is not None else income - expense
    )
    month = _clean(summary.get("month"), "เดือนนี้")

    lines = [
        f"📊 สรุป{month}",
        "",
        f"รายรับ {format_amount(income)} บาท",
        f"รายจ่าย {format_amount(expense)} บาท",
        f"เหลือ {format_amount(balance)} บาท"
        if balance >= 0
        else f"ใช้เกินไป {format_amount(-balance)} บาท",
    ]
    count = summary.get("transaction_count")
    if isinstance(count, int) and count >= 0:
        lines.append(f"จดไปแล้ว {count:,} รายการ")

    categories = summary.get("top_categories")
    if isinstance(categories, list) and categories:
        lines.extend(["", "ใช้เงินกับอะไรมากสุด"])
        for item in categories[:3]:
            if not isinstance(item, Mapping):
                continue
            category = _clean(item.get("category"), "ไม่ระบุหมวด")
            amount = format_amount(abs(_decimal(item.get("amount", 0))))
            lines.append(f"• {category} {amount} บาท")

    return limit_line_text("\n".join(lines))


def format_savings_goal(goal: Mapping[str, object]) -> str:
    """Render one savings goal with bounded progress and remaining amount."""

    name = _clean(goal.get("name"), "เป้าหมายการออม")
    target = max(_decimal(goal.get("target", 0)), Decimal("0"))
    saved = max(_decimal(goal.get("saved", 0)), Decimal("0"))
    remaining = max(target - saved, Decimal("0"))
    percent = Decimal("0") if target == 0 else saved * 100 / target
    display_percent = min(percent, Decimal("100"))

    lines = [
        f"🎯 {name}",
        f"ออมแล้ว {format_amount(saved)} จาก {format_amount(target)} บาท "
        f"({format_amount(display_percent)}%)",
    ]
    if remaining:
        lines.append(f"อีก {format_amount(remaining)} บาทก็ถึงเป้า")
    elif target > 0:
        lines.append("ถึงเป้าแล้ว เก่งมาก 🎉")

    due_date = _format_date(goal.get("due_date"))
    if due_date:
        lines.append(f"ภายใน {due_date}")
    return limit_line_text("\n".join(lines))


# Both names are convenient at integration sites.
format_savings_progress = format_savings_goal


def format_savings_goal_created(goal: Mapping[str, object]) -> str:
    return limit_line_text(f"ตั้งเป้าเรียบร้อย!\n\n{format_savings_goal(goal)}")


def format_savings_added(goal: Mapping[str, object]) -> str:
    return limit_line_text(f"💰 เก็บเพิ่มแล้ว!\n\n{format_savings_goal(goal)}")


def format_no_savings_goal() -> str:
    return 'ยังไม่มีเป้าหมายการออม ลองพิมพ์ "ตั้งเป้า 1500 ซื้อหนังสือ" ดูครับ'


def friendly_reason(reason: str | None) -> str:
    """Map a parser reason to user-facing copy (unknown reasons pass through)."""

    text = _clean(reason, "")
    if not text:
        return UNKNOWN_HEADING
    return FRIENDLY_REASONS.get(text, text)


def format_unknown_message(reason: str | None = None) -> str:
    """Explain an unresolved command, optionally including the parser reason."""

    heading = friendly_reason(reason)
    if heading != UNKNOWN_HEADING:
        return f"{heading}\n\n{HELP_HINT}"
    return (
        f"{UNKNOWN_HEADING}\n"
        "ลองพิมพ์แบบนี้ดูครับ\n"
        "• ข้าว 50\n"
        "• เงินเดือน 20000\n"
        "• สรุปเดือนนี้\n\n"
        f"หรือ{HELP_HINT}"
    )


def format_pending_transaction_prompt(
    *,
    amount: object | None,
    description: str | None,
) -> str:
    if amount is None:
        item = _clean(description, "รายการนี้")
        return f"{item} กี่บาทครับ? พิมพ์แค่ตัวเลขได้เลย เช่น 50"
    return f'{format_amount(amount)} บาทนี้ เป็นรายรับหรือรายจ่ายครับ? ตอบสั้นๆ ได้เลย เช่น "รายจ่าย"'


def format_pending_conflict() -> str:
    return 'ข้อความนี้ไม่ตรงกับรายการที่ถามค้างไว้ครับ ตอบเฉพาะที่ขาด หรือพิมพ์ "ยกเลิก"'


def format_invalid_followup() -> str:
    return 'ยังจดไม่ได้ ขาดข้อมูลอีกนิดครับ ตอบเฉพาะที่ถาม หรือพิมพ์ "ยกเลิก"'


def format_feedback_success(rating: int) -> str:
    return limit_line_text(f"ได้รับแล้ว {rating} ดาว ขอบคุณที่ช่วยให้หมูตุ๋นดีขึ้นครับ 🐷")


def format_feedback_instruction() -> str:
    return limit_line_text(
        'อยากบอกอะไรหมูตุ๋น พิมพ์ "เสนอแนะ" ตามด้วยคะแนน 1-5 และข้อความ (ถ้ามี) เช่น\n'
        "• เสนอแนะ 5\n"
        "• เสนอแนะ 4 ใช้ง่ายดีครับ"
    )


def format_feedback_invalid_rating() -> str:
    return 'คะแนนต้องเป็นเลข 1 ถึง 5 ครับ เช่น "เสนอแนะ 5"'


def format_feedback_comment_too_long() -> str:
    return "ข้อความยาวไปหน่อย ได้ไม่เกิน 1,000 ตัวอักษร ช่วยย่อแล้วส่งใหม่นะครับ"


def format_export_link(url: str) -> str:
    return f"📄 ไฟล์ CSV พร้อมแล้ว กดลิงก์เพื่อดาวน์โหลด (ใช้ได้ 10 นาที)\n{url}"


def format_export_no_data() -> str:
    return "ยังไม่มีรายการให้ส่งออกครับ"


def format_export_unavailable() -> str:
    return "ตอนนี้ส่งออกข้อมูลไม่ได้ ลองใหม่อีกสักพักนะครับ"


def format_onboarding_welcome() -> str:
    return limit_line_text(
        "🐷 สวัสดีครับ หมูตุ๋นช่วยจดรายรับรายจ่ายและเงินออมให้ แค่พิมพ์ในแชต\n\n"
        "ลองเลย เช่น\n"
        "• ข้าว 50\n"
        "• เงินเดือน 20000\n"
        "• สรุปเดือนนี้\n\n"
        'ดูคำสั่งทั้งหมด: "ช่วยเหลือ"\n'
        'ดูข้อความนี้อีกครั้ง: "เริ่มใช้งาน"\n'
        'บอกความเห็น: "เสนอแนะ 5 ใช้ง่ายดี"\n\n'
        'ข้อมูลของคุณแยกตามบัญชี LINE และลบทั้งหมดได้ทุกเมื่อด้วย "ลบข้อมูลทั้งหมด"'
    )


def format_onboarding_usage() -> str:
    return limit_line_text('พิมพ์แค่ "เริ่มใช้งาน" คำเดียวพอครับ ไม่ต้องใส่อะไรต่อท้าย')


def format_help_message() -> str:
    return (
        "🐷 วิธีใช้หมูตุ๋น\n\n"
        "จดรายการ: พิมพ์ชื่อกับจำนวนเงิน\n"
        "• ข้าว 50 (รายจ่าย)\n"
        "• เงินเดือน 20000 (รายรับ)\n"
        "• ระบุเองก็ได้: จ่าย 50 หรือ รับ 500\n\n"
        "ดูข้อมูล\n"
        "• รายการล่าสุด\n"
        "• สรุปเดือนนี้\n"
        "• ส่งออกข้อมูล (ไฟล์ CSV)\n\n"
        "แก้หรือลบ\n"
        "• แก้ไข ข้าว 60 (แก้รายการล่าสุด)\n"
        "• ลบล่าสุด (ถามยืนยันก่อน)\n"
        "• เลิกทำ (เอาคืนภายใน 10 นาที)\n"
        "• ลบข้อมูลทั้งหมด (ถามยืนยันก่อน)\n\n"
        "เงินออม\n"
        "• ตั้งเป้า 1500 ซื้อหนังสือ\n"
        "• ออม 100\n"
        "• เป้าหมายการออม\n\n"
        "อื่นๆ\n"
        "• เริ่มใช้งาน\n"
        "• เสนอแนะ 5 ใช้ง่ายดี"
    )


def limit_line_text(text: str, limit: int = SAFE_LINE_TEXT_LIMIT) -> str:
    """Keep generated text under LINE's limit without cutting silently."""

    if limit < 2:
        raise ValueError("limit must be at least 2")
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _details(transaction: Mapping[str, object], *, missing_date: str = "") -> str:
    """One line: note · category · date (note and date only when known)."""

    parts = []
    note = _clean(transaction.get("note"), "")
    if note and note != "ไม่ระบุรายการ":
        parts.append(note)
    parts.append(_clean(transaction.get("category"), "ไม่ระบุหมวด"))
    happened_on = _format_date(transaction.get("date")) or missing_date
    if happened_on:
        parts.append(happened_on)
    return " · ".join(parts)


def _short_line(transaction: Mapping[str, object]) -> str:
    amount = abs(_decimal(transaction.get("amount", 0)))
    category = _clean(transaction.get("category"), "ไม่ระบุหมวด")
    happened_on = _format_date(transaction.get("date")) or "ไม่ระบุวันที่"
    return f"{category} · {format_amount(amount)} บาท · {happened_on}"


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        return Decimal("0")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return number if number.is_finite() else Decimal("0")


def _kind(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"income", "รายรับ", "รับ", "+", "credit"}:
        return "รายรับ"
    return "รายจ่าย"


def _clean(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip().replace("\n", " ")
    return text or fallback


def _format_date(value: object) -> str:
    if isinstance(value, datetime):
        return format_buddhist_date(value)
    if isinstance(value, date):
        return format_buddhist_date(value)
    return _clean(value, "")
