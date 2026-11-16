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

// Back to the chat after an edit opened from a card. Outside LINE this is a no-op.
export function closeWindow(): void {
  if (initialized) liff.closeWindow();
}

// Posts a text into the chat as the user, so the bot can answer with a fresh card.
// Needs the chat_message.write scope and a LIFF opened from a chat; otherwise it does nothing.
export async function sendToChat(text: string): Promise<void> {
  if (!initialized || !liff.isInClient()) return;
  try {
    await liff.sendMessages([{ type: "text", text }]);
  } catch {
    // Missing scope or not opened from a chat: the edit is already saved, so stay quiet.
  }
}

export function idToken(): string | null {
  return liff.getIDToken();
}

// Login comes back to the same tab, and to an edit opened from a chat card. Anything
// else falls back to the app root; the path is rebuilt from an allowlist, never echoed.
const RETURN_TAB = /^\/app\/(?:summary|analysis|transactions|savings|settings)?$/;
const RETURN_EDIT = /^\?edit=[0-9]{1,9}$/;

function returnPath(): string {
  const { pathname, search } = window.location;
  if (!RETURN_TAB.test(pathname)) return "/app/";
  return pathname === "/app/transactions" && RETURN_EDIT.test(search) ? pathname + search : pathname;
}

// Explicit recovery only, never an automatic login loop. Same-origin return path.
export function login(): void {
  if (liff.isLoggedIn()) liff.logout();
  liff.login({ redirectUri: new URL(returnPath(), window.location.origin).href });
}
