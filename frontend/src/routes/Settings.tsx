import { Card, CardTitle } from "../components/ui";

// Mirrors the chat commands in PRODUCT_SPEC.md. Every change to data happens in chat.
const COMMANDS: [string, string][] = [
  ["ข้าว 50", "จดรายจ่าย (ไม่ต้องพิมพ์ “จ่าย” ถ้าชัดเจน)"],
  ["เงินเดือน 20000", "จดรายรับ"],
  ["เมื่อวานจ่าย 40 เดินทาง", "จดย้อนหลัง"],
  ["แก้ ข้าว 60", "แก้รายการล่าสุด"],
  ["ลบรายการล่าสุด", "ลบรายการล่าสุด (ต้องยืนยัน)"],
  ["เลิกทำ", "กู้คืนรายการที่เพิ่งลบ"],
  ["ตั้งเป้า 1500 ซื้อหนังสือ", "ตั้งเป้าหมายการออม"],
  ["ออม 100", "เพิ่มเงินออม"],
  ["ส่งออกข้อมูล", "รับลิงก์ไฟล์ CSV (หมดอายุใน 10 นาที)"],
  ["เสนอแนะ 5 ใช้ง่ายดี", "ให้คะแนนและความเห็น"],
  ["ลบข้อมูลทั้งหมด", "ลบข้อมูลการเงินทั้งหมด (ต้องยืนยัน)"],
];

export function Settings() {
  return (
    <div className="space-y-4">
      <Card>
        <CardTitle>คำสั่งในแชต</CardTitle>
        <p className="mb-3 text-sm text-muted">หน้านี้ดูข้อมูลอย่างเดียว การจด แก้ไข และลบ ทำผ่านแชตกับน้องหมูตุ๋น</p>
        <ul className="divide-y divide-line">
          {COMMANDS.map(([command, meaning]) => (
            <li key={command} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 py-2.5">
              <code className="rounded-lg bg-brand-soft px-2 py-0.5 font-sans text-sm font-medium text-brand">{command}</code>
              <span className="text-sm text-muted">{meaning}</span>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <CardTitle>ความเป็นส่วนตัว</CardTitle>
        <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed">
          <li>ใช้การยืนยันตัวตน LINE เพื่อเรียกดูเฉพาะข้อมูลของคุณ ไม่ขอชื่อ รูปโปรไฟล์ หรืออีเมล</li>
          <li>หน้านี้ไม่บันทึกโทเคนหรือข้อมูลการเงินลงพื้นที่จัดเก็บถาวรของเบราว์เซอร์ การจัดเก็บภายใน LINE / LIFF เป็นไปตามการทำงานของแพลตฟอร์ม</li>
          <li>ออกจากหน้านี้แล้ว ข้อมูลที่แสดงจะถูกล้าง กลับมาเมื่อไรจะโหลดใหม่ การปิดหน้านี้ไม่ได้รับประกันว่าออกจากระบบ LINE</li>
          <li>ยอดสุทธิของเดือนไม่ใช่ยอดเงินในธนาคาร และการออมแยกจากรายรับรายจ่าย</li>
        </ul>
      </Card>
      <p className="pb-2 text-center text-xs text-muted">MooTun · Developing</p>
    </div>
  );
}
