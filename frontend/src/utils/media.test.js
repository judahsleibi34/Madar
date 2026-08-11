import { describe, expect, it } from "vitest";

import { resolveMediaUrl } from "./media";


describe("resolveMediaUrl", () => {
  it("versions managed uploads so recovered assets bypass cached 404 responses", () => {
    expect(
      resolveMediaUrl(
        "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.png"
      )
    ).toMatch(
      /\/uploads\/tenant_7\/builder_assets\/56fee3e0f73c4110abdf423d501fb835\.png\?v=3$/
    );
  });

  it("resolves managed MP4 and WebM videos", () => {
    expect(resolveMediaUrl(
      "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.mp4"
    )).toMatch(/56fee3e0f73c4110abdf423d501fb835\.mp4\?v=3$/);
    expect(resolveMediaUrl(
      "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.webm"
    )).toMatch(/56fee3e0f73c4110abdf423d501fb835\.webm\?v=3$/);
  });

  it("does not add a version to external media URLs", () => {
    expect(resolveMediaUrl("https://images.example.com/photo.png")).toBe(
      "https://images.example.com/photo.png"
    );
  });
});
