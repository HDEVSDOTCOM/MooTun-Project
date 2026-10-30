import liff from "@line/liff";

let initialization: Promise<void> | null = null;
let initialized = false;

// Only openid is required. Scopes are configured in the LINE console, never by the browser.
export function initLiff(): Promise<void> {
  if (!initialization) {
    initialization = (async () => {
      const response = await fetch("/app/config.json", { cache: "no-store", credentials: "omit" });
      if (!response.ok) throw new Error("WEBAPP_UNAVAILABLE");
      const config = (await response.json()) as { liff_id: string };
      // Leave SDK query parameters intact until initialization completes.
      await liff.init({ liffId: config.liff_id, withLoginOnExternalBrowser: false });
      initialized = true;
    })().catch((error: unknown) => {
      initialization = null;
      throw error;
    });
  }
  return initialization;
}

export function isInitialized(): boolean {
  return initialized;
}

export function idToken(): string | null {
  return liff.getIDToken();
}

// Explicit recovery only, never an automatic login loop. Fixed same-origin return path.
export function login(): void {
  if (liff.isLoggedIn()) liff.logout();
  liff.login({ redirectUri: new URL("/app/", window.location.origin).href });
}
