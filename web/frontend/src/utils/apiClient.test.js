import { afterEach, describe, expect, it, vi } from "vitest";

import {
  apiFetch,
  clearCsrfToken,
  createApiError,
  parseApiError,
  postAuthJson,
  postPublicJson,
  readApiError,
  readApiErrorCode,
  readApiResponse,
  setCsrfToken,
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
  document.cookie = "madar_csrf_token=; Max-Age=0; path=/";
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("apiClient response readers", () => {
  it("readApiResponse parses successful JSON responses", async () => {
    const data = await readApiResponse(jsonResponse({ ok: true, value: 12 }));

    expect(data).toEqual({ ok: true, value: 12 });
  });

  it("readApiResponse handles empty non-JSON responses with a controlled detail", async () => {
    const data = await readApiResponse(textResponse("", { statusText: "No Content" }));

    expect(data).toEqual({ detail: "The server returned an unexpected response." });
  });

  it("readApiResponse never surfaces or parses unexpected HTML", async () => {
    const data = await readApiResponse(textResponse(
      "<!doctype html><title>Internal proxy response</title>",
      { status: 502, headers: { "Content-Type": "text/html" } }
    ));

    expect(data).toEqual({ detail: "The server returned an unexpected response." });
    expect(JSON.stringify(data)).not.toContain("doctype");
  });

  it("readApiError extracts useful messages from JSON-like error payloads", () => {
    expect(readApiError({ detail: "Invalid email" })).toBe("Invalid email");
    expect(readApiError({ detail: { code: "CONTACT_NAME_REQUIRED", message: "Name is required" } })).toBe("Name is required");
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

  it("normalizes structured errors without breaking legacy string details", () => {
    expect(
      parseApiError({
        detail: {
          code: "project_revision_conflict",
          message: "This project was updated elsewhere.",
          context: { current_revision: 7 },
        },
      })
    ).toEqual({
      code: "project_revision_conflict",
      message: "This project was updated elsewhere.",
      context: { current_revision: 7 },
    });

    expect(parseApiError({ detail: "Legacy error" })).toEqual({
      code: "",
      message: "Legacy error",
      context: {},
    });
  });

  it("creates typed API errors for centralized frontend recovery", () => {
    const error = createApiError(
      { status: 409 },
      {
        detail: {
          code: "idempotency_conflict",
          message: "This retry does not match the original request.",
          context: { existing_id: "reservation-1" },
        },
      }
    );

    expect(error.name).toBe("ApiError");
    expect(error.status).toBe(409);
    expect(error.code).toBe("idempotency_conflict");
    expect(error.context).toEqual({ existing_id: "reservation-1" });
    expect(error.message).toBe("This retry does not match the original request.");
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
  it("fetches and sends a CSRF token before unsafe authenticated requests", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ csrf_token: "fresh-csrf" }))
        .mockResolvedValueOnce(jsonResponse({ ok: true }))
    );

    const response = await apiFetch("/api/builder/projects/project-1", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ draft_schema: {} }),
    });
    const data = await response.json();

    expect(data).toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetchCall(0)[0]).toBe("/api/auth/user_status");
    expect(fetchCall(0)[1].credentials).toBe("include");
    expect(fetchCall(1)[0]).toBe("/api/builder/projects/project-1");
    expect(fetchCall(1)[1].method).toBe("PUT");
    expect(fetchCall(1)[1].credentials).toBe("include");
    expect(fetchCall(1)[1].headers.get("X-CSRF-Token")).toBe("fresh-csrf");
  });

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

  it("returns a transient refresh failure instead of the original 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(textResponse("expired", { status: 401 }))
        .mockResolvedValueOnce(jsonResponse(
          { detail: { code: "auth_temporarily_unavailable" } },
          { status: 503, headers: { "Retry-After": "5" } }
        ))
    );

    const response = await apiFetch("/api/users/1/profile");

    expect(response.status).toBe(503);
    expect((await response.json()).detail.code).toBe("auth_temporarily_unavailable");
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("gives concurrent callers independent transient refresh responses", async () => {
    const fetchMock = vi.fn((url) => {
      if (url === "/api/auth/refresh") {
        return Promise.resolve(jsonResponse(
          { detail: { code: "auth_temporarily_unavailable" } },
          { status: 503 }
        ));
      }
      return Promise.resolve(textResponse("expired", { status: 401 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const responses = await Promise.all([
      apiFetch("/api/protected"),
      apiFetch("/api/protected"),
    ]);
    const bodies = await Promise.all(responses.map((response) => response.json()));

    expect(bodies.map((body) => body.detail.code)).toEqual([
      "auth_temporarily_unavailable",
      "auth_temporarily_unavailable",
    ]);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh")).toHaveLength(1);
  });

  it("readApiErrorCode extracts stable backend error codes", () => {
    expect(readApiErrorCode({ code: "CONTACT_RECEIVED" })).toBe("CONTACT_RECEIVED");
    expect(readApiErrorCode({ detail: { code: "CONTACT_NAME_REQUIRED" } })).toBe("CONTACT_NAME_REQUIRED");
    expect(readApiErrorCode({ error: { code: "CONTACT_SUBMIT_FAILED" } })).toBe("CONTACT_SUBMIT_FAILED");
    expect(readApiErrorCode({ detail: "Name is required" })).toBe("");
  });

  it("retries an unsafe request once after refreshing an invalid CSRF token", async () => {
    setCsrfToken("old-token");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ detail: "Invalid CSRF token" }, { status: 403 }))
        .mockResolvedValueOnce(jsonResponse(
          { refreshed: true },
          { headers: { "X-CSRF-Token": "new-token" } }
        ))
        .mockResolvedValueOnce(jsonResponse({ ok: true }))
    );

    const response = await apiFetch("/api/builder/projects/123", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Theme" }),
    });
    const data = await response.json();

    expect(data).toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetchCall(0)[0]).toBe("/api/builder/projects/123");
    expect(fetchCall(0)[1].headers.get("X-CSRF-Token")).toBe("old-token");
    expect(fetchCall(1)[0]).toBe("/api/auth/user_status");
    expect(fetchCall(2)[0]).toBe("/api/builder/projects/123");
    expect(fetchCall(2)[1].headers.get("X-CSRF-Token")).toBe("new-token");
    expect(fetchCall(2)[1].headers.get("Content-Type")).toBe("application/json");
  });
});


describe("CSRF session races", () => {
  it("uses the shared cookie after another tab replaces the session token", async () => {
    setCsrfToken("old-tab-token");
    document.cookie = "madar_csrf_token=current-session-token; path=/";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ ok: true })));
    await apiFetch("/api/screen-time/heartbeat", { method: "POST", body: "{}" });
    expect(fetchCall()[1].headers.get("X-CSRF-Token")).toBe("current-session-token");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("shares a token refresh across concurrent rejected heartbeat and cart requests", async () => {
    setCsrfToken("expired-token");
    const attempts = new Map();
    const fetchMock = vi.fn(async (url) => {
      if (url.includes("/auth/user_status")) return jsonResponse({ csrf_token: "fresh-token" });
      const count = (attempts.get(url) || 0) + 1;
      attempts.set(url, count);
      return count === 1 ? jsonResponse({ detail: "Invalid CSRF token" }, { status: 403 }) : jsonResponse({ ok: true });
    });
    vi.stubGlobal("fetch", fetchMock);
    const responses = await Promise.all([
      apiFetch("/api/screen-time/heartbeat", { method: "POST", body: "{}" }),
      apiFetch("/api/public/sites/demo/cart/reconcile", { method: "POST", body: "{}" }),
    ]);
    expect(responses.every(response => response.ok)).toBe(true);
    expect(fetchMock.mock.calls.filter(([url]) => url.includes("/auth/user_status"))).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url, init]) => !url.includes("/auth/") && init.headers.get("X-CSRF-Token") === "fresh-token")).toHaveLength(2);
  });

  it("replaces an explicitly supplied expired header on the single retry", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Invalid CSRF token" }, { status: 403 }))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "replacement" }))
      .mockResolvedValueOnce(jsonResponse({ ok: true })));
    const response = await apiFetch("/api/public/sites/demo/cart/reconcile", {
      method: "POST", headers: { "X-CSRF-Token": "expired" }, body: "{}",
    });
    expect(response.ok).toBe(true);
    expect(fetchCall(2)[1].headers.get("X-CSRF-Token")).toBe("replacement");
  });
});


describe("expired-session mutation recovery", () => {
  it("refreshes the session when status cannot issue a new CSRF token", async () => {
    setCsrfToken("expired");
    vi.stubGlobal("fetch",vi.fn()
      .mockResolvedValueOnce(jsonResponse({detail:"Invalid CSRF token"},{status:403}))
      .mockResolvedValueOnce(jsonResponse({logged_in:false}))
      .mockResolvedValueOnce(jsonResponse({logged_in:true},{headers:{"X-CSRF-Token":"renewed"}}))
      .mockResolvedValueOnce(jsonResponse({ok:true})));
    const response=await apiFetch("/api/screen-time/heartbeat",{method:"POST",body:"{}"});
    expect(response.ok).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(4);
    expect(fetchCall(2)[0]).toBe("/api/auth/refresh");
    expect(fetchCall(3)[1].headers.get("X-CSRF-Token")).toBe("renewed");
  });

  it("renews an explicit CSRF header after an authentication refresh",async()=>{
    vi.stubGlobal("fetch",vi.fn()
      .mockResolvedValueOnce(jsonResponse({detail:"Session expired"},{status:401}))
      .mockResolvedValueOnce(jsonResponse({logged_in:true},{headers:{"X-CSRF-Token":"renewed"}}))
      .mockResolvedValueOnce(jsonResponse({ok:true})));
    const response=await apiFetch("/api/public/sites/demo/orders",{method:"POST",headers:{"X-CSRF-Token":"expired"},body:"{}"});
    expect(response.ok).toBe(true);
    expect(fetchCall(2)[1].headers.get("X-CSRF-Token")).toBe("renewed");
  });
});
