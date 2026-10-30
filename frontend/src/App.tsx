import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { TabBar } from "./components/TabBar";
import { Card, Skeleton } from "./components/ui";
import { Placeholder } from "./routes/Placeholder";
import { Savings } from "./routes/Savings";
import { Settings } from "./routes/Settings";
import { Summary } from "./routes/Summary";
import { Transactions } from "./routes/Transactions";
import { SessionProvider, useSession } from "./session";

export function App() {
  return (
    <BrowserRouter basename="/app">
      <SessionProvider>
        <div className="mx-auto min-h-dvh max-w-xl px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-24">
          <header className="mb-4 flex items-center gap-2">
            <span aria-hidden="true" className="text-2xl">🐷</span>
            <h1 className="font-display text-xl font-semibold">หมูตุ๋น</h1>
          </header>
          <Main />
        </div>
        <TabBar />
      </SessionProvider>
    </BrowserRouter>
  );
}

function Main() {
  const { phase, message, canLogin, login, reload } = useSession();

  if (phase === "connecting") {
    return (
      <div className="space-y-4" aria-busy="true">
        <p role="status" className="sr-only">{message}</p>
        <Skeleton className="h-48 rounded-3xl" />
        <Skeleton className="h-40 rounded-3xl" />
      </div>
    );
  }

  if (phase !== "ready") {
    return (
      <Card>
        <p role="status" aria-live="polite">{message}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          {canLogin && (
            <button type="button" onClick={login} className="min-h-11 rounded-2xl bg-brand px-4 font-medium text-white">
              เข้าสู่ระบบ LINE
            </button>
          )}
          <button type="button" onClick={reload} className="min-h-11 rounded-2xl bg-brand-soft px-4 font-medium text-brand">
            ลองอีกครั้ง
          </button>
        </div>
      </Card>
    );
  }

  return (
    <main>
      <Routes>
        <Route index element={<Navigate to="/summary" replace />} />
        <Route path="summary" element={<Summary />} />
        <Route path="analysis" element={<Placeholder title="วิเคราะห์" />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="savings" element={<Savings />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/summary" replace />} />
      </Routes>
    </main>
  );
}
