import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getMe, sendMe, type EditBody } from "../api";

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

const BODY: EditBody = {
  transaction_type: "expense", amount_baht: "50.00", category: "อาหาร", description: null, occurred_on: "2026-11-01",
};

describe("sendMe", () => {
  it("sends the method, JSON body and bearer token without cookies", async () => {
    const fetchMock = respond(200, '{"id": 3}');
    await expect(sendMe("PATCH", "/api/me/transactions/3", "tok", BODY)).resolves.toEqual({ id: 3 });
    expect(fetchMock).toHaveBeenCalledWith("/api/me/transactions/3", {
      method: "PATCH",
      headers: { Authorization: "Bearer tok", "Content-Type": "application/json" },
      body: JSON.stringify(BODY),
      cache: "no-store",
      credentials: "omit",
    });
  });

  it("returns null for 204", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    await expect(sendMe("DELETE", "/api/me/transactions/3", "tok")).resolves.toBeNull();
  });

  it("carries the field of a 422", async () => {
    respond(422, '{"code": "INVALID_FIELD", "field": "amount_baht"}');
    const error = await sendMe("PATCH", "/api/me/transactions/3", "tok", BODY).catch((e) => e);
    expect(error).toMatchObject({ status: 422, code: "INVALID_FIELD", field: "amount_baht" });
  });

  it("maps 404 to NOT_FOUND", async () => {
    respond(404, '{"code": "NOT_FOUND"}');
    await expect(sendMe("DELETE", "/api/me/transactions/3", "tok")).rejects.toMatchObject({ status: 404, code: "NOT_FOUND" });
  });
});
