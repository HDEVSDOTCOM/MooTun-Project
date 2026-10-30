import { NavLink } from "react-router-dom";

const ICONS: Record<string, string> = {
  summary: "M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
  analysis: "M5 20V11M12 20V5M19 20v-7",
  transactions: "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
  savings: "M12 3v18M17 7.5C17 5.6 14.8 5 12 5S7 5.9 7 8s2.2 2.6 5 3.2 5 1.4 5 3.6-2.2 3.2-5 3.2-5-.8-5-2.7",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 13a7.5 7.5 0 0 0 0-2l2-1.6-2-3.4-2.4 1a7.4 7.4 0 0 0-1.7-1L15 3.5h-4L10.7 6a7.4 7.4 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7.5 7.5 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a7.4 7.4 0 0 0 1.7 1l.3 2.5h4l.3-2.5a7.4 7.4 0 0 0 1.7-1l2.4 1 2-3.4z",
};

// Must match SPA_TABS in webapp_routes.py.
export const TABS = [
  { path: "summary", label: "สรุป" },
  { path: "analysis", label: "วิเคราะห์" },
  { path: "transactions", label: "รายการ" },
  { path: "savings", label: "การออม" },
  { path: "settings", label: "ตั้งค่า" },
] as const;

export function TabBar() {
  return (
    <nav
      aria-label="เมนูหลัก"
      className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
    >
      <ul className="mx-auto grid max-w-xl grid-cols-5">
        {TABS.map((tab) => (
          <li key={tab.path}>
            <NavLink
              to={`/${tab.path}`}
              className={({ isActive }) =>
                `flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] ${isActive ? "font-semibold text-brand" : "text-muted"}`
              }
            >
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d={ICONS[tab.path]} />
              </svg>
              {tab.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
