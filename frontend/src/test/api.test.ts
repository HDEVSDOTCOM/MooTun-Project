import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getMe } from "../api";

function respond(status: number, body: string) {
  const fetchMock = vi.fn(async () => new Response(body, { status, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("getMe", () => {
  it("sends only a bearer token, without cookies or HTTP cache", async () => {
    const fetchMock = respond(200, '{"ok": true}');
    const signal = new AbortController().signal;
    await expect(getMe("/api/me/summary", "tok", signal)).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith("/api/me/summary", {
      headers: { Authorization: "Bearer tok" }, cache: "no-store", credentials: "omit", signal,
    });
  });

  it.each([
    [401, '{"code": "UNAUTHORIZED"}', 401, "UNAUTHORIZED"],
    [401, "not json", 401, "UNAUTHORIZED"],
    [503, '{"code": "AUTH_UNAVAILABLE"}', 503, "AUTH_UNAVAILABLE"],
    [503, '{"code": "SOMETHING_NEW"}', 503, "DATA_UNAVAILABLE"],
    [500, "<html>", 500, "DATA_UNAVAILABLE"],
    [200, "not json", 200, "DATA_UNAVAILABLE"],
  ])("maps HTTP %i %s to a known error code", async (status, body, expectedStatus, code) => {
    respond(status, body);
    const error = await getMe("/api/me/summary", "tok", new AbortController().signal).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: expectedStatus, code });
  });
});
