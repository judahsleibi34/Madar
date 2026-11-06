import { describe, expect, it } from "vitest";
import { getWebsiteSettingsPayload, websiteSettingsPayloadChanged } from "./PageBuilder.websiteSettings";

describe("private Website settings projection", () => {
  it("preserves the default payload and its exact keys", () => {
    expect(getWebsiteSettingsPayload()).toEqual({
      subdomain: "", brand: "Madar", footer_store_name: "Madar", logo_url: "",
      contact_email: "info@madar.com", phone: "+972 0599203857",
      description: "An adaptive business management platform for creating and managing digital systems.",
    });
    expect(getWebsiteSettingsPayload({ publish: null, siteChrome: null })).toEqual(getWebsiteSettingsPayload());
  });

  it("normalizes subdomains and trims projected fields without mutating raw values", () => {
    const project = { publish: { subdomain: " HTTPS://My Site " }, siteChrome: {
      brand: "  Brand  ", footerStoreName: " Store ", logoUrl: " /logo.png ",
      contactEmail: " a@example.test ", phone: " 123 ", description: " وصف ",
    } };
    const before = structuredClone(project);
    expect(getWebsiteSettingsPayload(project)).toEqual({ subdomain: "my-site", brand: "Brand",
      footer_store_name: "Store", logo_url: "/logo.png", contact_email: "a@example.test",
      phone: "123", description: "وصف" });
    expect(project).toEqual(before);
    expect(project.siteChrome.brand).toBe("  Brand  ");
    expect(getWebsiteSettingsPayload(project)).toEqual(getWebsiteSettingsPayload(project));
  });

  it.each([null, undefined, "", false, 0])("preserves explicit falsy field overrides: %s", brand => {
    expect(getWebsiteSettingsPayload({ siteChrome: { brand } }).brand).toBe("");
  });

  it("preserves coercion and malformed input behavior", () => {
    expect(getWebsiteSettingsPayload({ siteChrome: { brand: 42, phone: [1, 2] } })).toMatchObject({ brand: "42", phone: "1,2" });
    expect(getWebsiteSettingsPayload({ siteChrome: "bad", publish: "bad" })).toEqual(getWebsiteSettingsPayload());
    expect(() => getWebsiteSettingsPayload(null)).toThrow(TypeError);
    expect(() => websiteSettingsPayloadChanged(null, {})).toThrow(TypeError);
  });

  it("compares only projected, normalized settings", () => {
    const first = { publish: { subdomain: "My Site" }, siteChrome: { brand: " Brand " } };
    const equivalent = { pages: [{ id: "unrelated" }], publish: { subdomain: "my-site" }, siteChrome: { brand: "Brand", logoWidth: 100 } };
    expect(websiteSettingsPayloadChanged(first, equivalent)).toBe(false);
    expect(websiteSettingsPayloadChanged()).toBe(false);
  });

  it.each(["brand", "footerStoreName", "logoUrl", "contactEmail", "phone", "description"])("detects a changed %s", field => {
    expect(websiteSettingsPayloadChanged({}, { siteChrome: { [field]: "changed" } })).toBe(true);
  });

  it("detects changed subdomains and retains the existing length bound", () => {
    expect(websiteSettingsPayloadChanged({}, { publish: { subdomain: "new-site" } })).toBe(true);
    expect(getWebsiteSettingsPayload({ publish: { subdomain: "a".repeat(70) } }).subdomain).toBe("a".repeat(63));
  });
});
