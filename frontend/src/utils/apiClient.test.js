import { afterEach, describe, expect, it, vi } from "vitest";

import {
  apiFetch,
  clearCsrfToken,
  postAuthJson,
  postPublicJson,
  readApiError,
  readApiResponse,
} from "./apiClient";

const jsonResponse = (body, init = {}) =>
  new Response(JSON.stringify(body), {
    status: init.status || 200,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });

const textResponse = (body, init = {}) =>
  new Response(body, {
    status: init.status || 200,
    statusText: init.statusText || "",
    headers: init.headers || {},
  });

const fetchCall = (index = 0) => fetch.mock.calls[index];

afterEach(() => {
  clearCsrfToken();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("apiClient response readers", () => {
  it("readApiResponse parses successful JSON responses", async () => {
    const data = await readApiResponse(jsonResponse({ ok: true, value: 12 }));

    expect(data).toEqual({ ok: true, value: 12 });
  });

  it("readApiResponse handles empty non-JSON responses with a fallback detail", async () => {
    const data = await readApiResponse(textResponse("", { statusText: "No Content" }));

    expect(data).toEqual({ detail: "No Content" });
  });

  it("readApiError extracts useful messages from JSON-like error payloads", () => {
    expect(readApiError({ detail: "Invalid email" })).toBe("Invalid email");
    expect(readApiError({ message: "Server unavailable" })).toBe("Server unavailable");
    expect(
      readApiError({
        detail: [{ msg: "Email is required" }, { msg: "Password is required" }],
      })
    ).toBe("Email is required Password is required");
  });

  it("readApiError falls back for non-JSON or unrecognized error payloads", () => {
    expect(readApiError({ detail: "" }, "Fallback message")).toBe("Fallback message");
    expect(readApiError(null, "Fallback message")).toBe("Fallback message");
  });
});

describe("apiClient JSON POST helpers", () => {
  it.each([
    ["postPublicJson", postPublicJson],
    ["postAuthJson", postAuthJson],
  ])("%s sends JSON with include credentials", async (_name, postJson) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ saved: true })));

    const { response, data } = await postJson("/contact", { name: "Madar" });
    const [url, init] = fetchCall();

    expect(url).toBe("/api/contact");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(init.body).toBe(JSON.stringify({ name: "Madar" }));
    expect(init.headers.get("Content-Type")).toBe("application/json");
    expect(response.ok).toBe(true);
    expect(data).toEqual({ saved: true });
  });
});

describe("apiFetch session refresh", () => {
  it("retries an authenticated request once after a successful refresh", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(textResponse("expired", { status: 401 }))
        .mockResolvedValueOnce(jsonResponse({ refreshed: true }))
        .mockResolvedValueOnce(jsonResponse({ ok: true }))
    );

    const response = await apiFetch("/api/users/1/profile");
    const data = await response.json();

    expect(data).toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetchCall(0)[0]).toBe("/api/users/1/profile");
    expect(fetchCall(1)[0]).toBe("/api/auth/refresh");
    expect(fetchCall(1)[1].method).toBe("POST");
    expect(fetchCall(1)[1].credentials).toBe("include");
    expect(fetchCall(2)[0]).toBe("/api/users/1/profile");
    expect(fetchCall(2)[1].credentials).toBe("include");
  });

  it("shares one refresh request across concurrent 401 responses", async () => {
    const fetchMock = vi.fn((url) => {
      if (url === "/api/auth/refresh") {
        return Promise.resolve(jsonResponse({ refreshed: true }));
      }

      const protectedCalls = fetchMock.mock.calls.filter(
        ([calledUrl]) => calledUrl === "/api/protected"
      ).length;

      return Promise.resolve(
        protectedCalls <= 2
          ? textResponse("expired", { status: 401 })
          : jsonResponse({ ok: true })
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const responses = await Promise.all([
      apiFetch("/api/protected"),
      apiFetch("/api/protected"),
    ]);
    const bodies = await Promise.all(responses.map((response) => response.json()));

    expect(bodies).toEqual([{ ok: true }, { ok: true }]);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh")).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/protected")).toHaveLength(4);
  });

  it("returns the original 401 response when refresh fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(textResponse("expired", { status: 401 }))
        .mockResolvedValueOnce(textResponse("refresh failed", { status: 401 }))
    );

    const response = await apiFetch("/api/users/1/profile");

    expect(response.status).toBe(401);
    expect(await response.text()).toBe("expired");
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetchCall(1)[0]).toBe("/api/auth/refresh");
  });
});
