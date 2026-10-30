import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, getMe, type Summary } from "./api";
import { idToken, initLiff, isInitialized, login as liffLogin } from "./liff";

export type Phase = "connecting" | "ready" | "auth" | "error" | "hidden";

export interface SessionState {
  phase: Phase;
  message: string;
  canLogin: boolean;
  token: string | null;
  summary: Summary | null;
  summaryError: ApiError | null;
  // Aborted whenever the page hides, reloads, or authentication is lost.
  signal: AbortSignal | null;
}

interface Session extends SessionState {
  reload: () => void;
  login: () => void;
  requireAuth: () => void;
}

const MESSAGES = {
  connecting: "กำลังเชื่อมต่อ LINE…",
  auth: "ต้องยืนยันตัวตน LINE อีกครั้ง หากยกเลิกการอนุญาต สามารถลองเข้าสู่ระบบใหม่ได้",
  authUnavailable: "การยืนยัน LINE ไม่พร้อมใช้งานชั่วคราว กรุณาลองอีกครั้ง",
  webUnavailable: "หน้าเว็บไม่พร้อมใช้งานชั่วคราว ยังใช้งานผ่านแชตได้",
  connectFailed: "เชื่อมต่อ LINE ไม่สำเร็จ หากยกเลิกการอนุญาต สามารถลองอีกครั้งได้",
  hidden: "กลับมาที่หน้านี้เพื่อโหลดข้อมูลใหม่",
  loginFailed: "เข้าสู่ระบบ LINE ไม่สำเร็จ กรุณาลองอีกครั้ง",
};

const EMPTY = { token: null, summary: null, summaryError: null, signal: null } as const;

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({
    ...EMPTY, phase: "connecting", message: MESSAGES.connecting, canLogin: false,
  });
  const controller = useRef<AbortController | null>(null);

  // Drop every rendered financial value and cancel in-flight reads.
  const invalidate = useCallback((phase: Phase, message: string, canLogin = false) => {
    controller.current?.abort();
    controller.current = null;
    setState({ ...EMPTY, phase, message, canLogin });
  }, []);

  const requireAuth = useCallback(() => invalidate("auth", MESSAGES.auth, true), [invalidate]);

  const load = useCallback(async () => {
    invalidate("connecting", MESSAGES.connecting);
    const active = new AbortController();
    controller.current = active;
    const isCurrent = () => controller.current === active && !active.signal.aborted;
    try {
      await initLiff();
      if (!isCurrent()) return;
      const token = idToken();
      if (!token) {
        requireAuth();
        return;
      }
      // Summary is the identity bootstrap. No other financial read precedes it.
      let summary: Summary | null = null;
      let summaryError: ApiError | null = null;
      try {
        summary = await getMe<Summary>("/api/me/summary", token, active.signal);
      } catch (error) {
        if (!isCurrent()) return;
        if (!(error instanceof ApiError)) throw error;
        if (error.status === 401) {
          requireAuth();
          return;
        }
        if (error.code !== "DATA_UNAVAILABLE") {
          invalidate("error", MESSAGES.authUnavailable);
          return;
        }
        summaryError = error;
      }
      if (!isCurrent()) return;
      setState({ phase: "ready", message: "", canLogin: false, token, summary, summaryError, signal: active.signal });
    } catch (error) {
      if (!isCurrent()) return;
      const message = error instanceof Error && error.message === "WEBAPP_UNAVAILABLE"
        ? MESSAGES.webUnavailable
        : MESSAGES.connectFailed;
      invalidate("error", message, isInitialized());
    }
  }, [invalidate, requireAuth]);

  const login = useCallback(() => {
    invalidate("auth", MESSAGES.auth, true);
    try {
      liffLogin();
    } catch {
      setState((current) => ({ ...current, message: MESSAGES.loginFailed }));
    }
  }, [invalidate]);

  useEffect(() => {
    void load();
    const hide = () => invalidate("hidden", MESSAGES.hidden);
    const show = () => {
      if (!document.hidden) void load();
    };
    const visibility = () => (document.hidden ? hide() : void load());
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
      document.removeEventListener("visibilitychange", visibility);
      controller.current?.abort();
    };
  }, [load, invalidate]);

  return (
    <SessionContext.Provider value={{ ...state, reload: () => void load(), login, requireAuth }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession outside SessionProvider");
  return session;
}

export interface Resource<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  retry: () => void;
}

// One financial read, cancelled on unmount and whenever the session invalidates.
export function useMe<T>(path: string | null): Resource<T> {
  const { phase, token, signal, requireAuth } = useSession();
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<Omit<Resource<T>, "retry">>({ data: null, error: null, loading: true });

  useEffect(() => {
    if (phase !== "ready" || !token || !signal || !path) return;
    const local = new AbortController();
    const abort = () => local.abort();
    signal.addEventListener("abort", abort);
    setResource({ data: null, error: null, loading: true });
    getMe<T>(path, token, local.signal).then(
      (data) => {
        if (!local.signal.aborted) setResource({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (local.signal.aborted) return;
        if (error instanceof ApiError && error.status === 401) {
          requireAuth();
          return;
        }
        const apiError = error instanceof ApiError ? error : new ApiError(0, "DATA_UNAVAILABLE");
        setResource({ data: null, error: apiError, loading: false });
      },
    );
    return () => {
      signal.removeEventListener("abort", abort);
      local.abort();
    };
  }, [phase, token, signal, path, requireAuth, attempt]);

  return { ...resource, retry: () => setAttempt((value) => value + 1) };
}
