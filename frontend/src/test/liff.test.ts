import { afterEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({
  login: vi.fn(),
  isLoggedIn: () => false,
  init: vi.fn(async () => {}),
}));
vi.mock("@line/liff", () => ({ default: sdk }));

const { login } = await import("../liff");

function at(path: string) {
  window.history.replaceState(null, "", path);
  login();
  return sdk.login.mock.lastCall?.[0].redirectUri as string;
}

afterEach(() => sdk.login.mockClear());

describe("login return path", () => {
  it("comes back to the tab and the edit that needed it", () => {
    expect(at("/app/transactions?edit=42")).toBe(`${window.location.origin}/app/transactions?edit=42`);
    expect(at("/app/savings")).toBe(`${window.location.origin}/app/savings`);
  });

  it("falls back to the app root for anything else", () => {
    expect(at("/app/transactions?edit=42&next=https://evil.example")).toBe(`${window.location.origin}/app/transactions`);
    expect(at("/app/unknown")).toBe(`${window.location.origin}/app/`);
    expect(at("/elsewhere")).toBe(`${window.location.origin}/app/`);
  });
});
