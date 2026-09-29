import { describe, expect, it } from "vitest";

import { getResponsiveMediaProps, resolveDocumentUrl, resolveMediaUrl } from "./media";


describe("resolveMediaUrl", () => {
  it("versions managed uploads so recovered assets bypass cached 404 responses", () => {
    expect(resolveMediaUrl(
      "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.png"
    )).toBe("/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.png?v=4");
    expect(resolveMediaUrl(
      "https://api.madarportal.com/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.png"
    )).toBe("/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.png?v=4");
  });

  it("resolves managed MP4 and WebM videos", () => {
    expect(resolveMediaUrl(
      "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.mp4"
    )).toMatch(/56fee3e0f73c4110abdf423d501fb835\.mp4\?v=4$/);
    expect(resolveMediaUrl(
      "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.webm"
    )).toMatch(/56fee3e0f73c4110abdf423d501fb835\.webm\?v=4$/);
  });

  it("does not add a version to external media URLs", () => {
    expect(resolveMediaUrl("https://images.example.com/photo.png")).toBe(
      "https://images.example.com/photo.png"
    );
  });

  it("keeps public storefront assets on the storefront origin", () => {
    expect(resolveMediaUrl("/form-flow-products/lavender-eye-pillow.jpg")).toBe(
      "/form-flow-products/lavender-eye-pillow.jpg"
    );
  });

  it("builds stable responsive variants only for managed images", () => {
    const props = getResponsiveMediaProps(
      "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.png",
      { widths: [480, 1024], fallbackWidth: 1024, sizes: "50vw" }
    );
    expect(props.src).toMatch(/\?v=4&w=1024$/);
    expect(props.srcSet).toContain("&w=480 480w");
    expect(props.srcSet).toContain("&w=1024 1024w");
    expect(props.sizes).toBe("50vw");
    expect(getResponsiveMediaProps("https://images.example.com/photo.png"))
      .toEqual({ src: "https://images.example.com/photo.png" });
  });

  it("maps unsupported requests to bounded widths instead of dropping mobile candidates", () => {
    const props = getResponsiveMediaProps(
      "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.png",
      { widths: [375, 640, 960, 1600], fallbackWidth: 1600, sizes: "100vw" }
    );
    expect(props.src).toMatch(/&w=1920$/);
    expect(props.srcSet).toContain("&w=480 480w");
    expect(props.srcSet).toContain("&w=768 768w");
    expect(props.srcSet).toContain("&w=1024 1024w");
    expect(props.srcSet).toContain("&w=1920 1920w");
    expect(props.srcSet).not.toContain("&w=640");
  });
});

describe("resolveDocumentUrl", () => {
  it.each(["pdf", "doc", "docx"])("resolves managed %s documents", (extension) => {
    expect(resolveDocumentUrl(
      `/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.${extension}`
    )).toMatch(new RegExp(`56fee3e0f73c4110abdf423d501fb835\\.${extension}\\?v=4$`));
  });

  it("keeps document and visual media categories explicit", () => {
    expect(resolveDocumentUrl("/files/guide.pdf")).toContain("/files/guide.pdf");
    expect(resolveMediaUrl("/files/guide.pdf")).toBe("");
    expect(resolveDocumentUrl("/files/archive.zip")).toBe("");
  });

  it("accepts HTTPS documents and rejects unsafe URL forms", () => {
    expect(resolveDocumentUrl("https://media.example.com/guide.docx")).toBe(
      "https://media.example.com/guide.docx"
    );
    for (const unsafeUrl of [
      "http://media.example.com/guide.pdf",
      "//evil.example/guide.pdf",
      "javascript:alert(1)",
      "data:application/pdf;base64,AA==",
      "file:///tmp/guide.pdf",
      "https://media.example.com/archive.zip",
      "https://user:password@media.example.com/guide.pdf",
    ]) {
      expect(resolveDocumentUrl(unsafeUrl)).toBe("");
    }
  });
});
