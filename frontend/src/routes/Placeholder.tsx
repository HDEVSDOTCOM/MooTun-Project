import { Card, Empty } from "../components/ui";

// Tabs scheduled for later steps of Phase 2C (see plan/active/webapp_react_rebuild_plan.md).
export function Placeholder({ title }: { title: string }) {
  return (
    <Card>
      <h2 className="font-display text-lg font-semibold">{title}</h2>
      <Empty title="กำลังพัฒนา" hint="ระหว่างนี้ใช้งานผ่านแชตกับน้องหมูตุ๋นได้ตามปกติ" />
    </Card>
  );
}
