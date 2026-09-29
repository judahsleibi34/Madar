import { afterEach, describe, expect, it, vi } from "vitest";

import { recordPublicSiteVisit } from "./siteVisitApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("public visit analytics", () => {
  it("submits one anonymous request without auth discovery or credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ success: true }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);

    await expect(recordPublicSiteVisit("disco", "website")).resolves.toEqual({ success: true });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/public/sites/disco/visits",
      expect.objectContaining({
        method: "POST",
        credentials: "omit",
        cache: "no-store",
        body: JSON.stringify({ surface: "website" }),
      }),
    );
  });

  it("keeps analytics independent of authenticated cookies and fails locally", async () => {
    document.cookie = "madar_csrf_token=existing-token; path=/";
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(recordPublicSiteVisit("disco", "store")).rejects.toThrow("Visit tracking failed");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1].credentials).toBe("omit");
    document.cookie = "madar_csrf_token=; Max-Age=0; path=/";
  });
});
