import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const publicRoot = path.join(frontendRoot, "public");

const readPngSize = (filePath) => {
  const data = fs.readFileSync(filePath);
  expect(data.subarray(1, 4).toString("ascii")).toBe("PNG");
  return `${data.readUInt32BE(16)}x${data.readUInt32BE(20)}`;
};

describe("PWA static contract", () => {
  it("has a complete standalone manifest with real matching icons", () => {
    const manifest = JSON.parse(
      fs.readFileSync(path.join(publicRoot, "manifest.webmanifest"), "utf8")
    );
    expect(manifest).toMatchObject({
      name: "Madar",
      short_name: "Madar",
      start_url: "/dashboard",
      scope: "/",
      display: "standalone",
      background_color: "#f4f0e8",
      theme_color: "#852c21",
    });
    expect(manifest.icons.length).toBeGreaterThanOrEqual(3);

    for (const icon of manifest.icons) {
      const iconPath = path.join(publicRoot, icon.src.replace(/^\//, ""));
      expect(fs.existsSync(iconPath)).toBe(true);
      expect(icon.type).toBe("image/png");
      expect(readPngSize(iconPath)).toBe(icon.sizes);
    }
    expect(manifest.icons.some((icon) => icon.purpose === "maskable")).toBe(true);
  });

  it("keeps one push/lifecycle worker without a private-data fetch cache", () => {
    const worker = fs.readFileSync(path.join(publicRoot, "madar-push-sw.js"), "utf8");
    for (const eventName of ["install", "activate", "push", "notificationclick"]) {
      expect(worker).toContain(`addEventListener("${eventName}"`);
    }
    expect(worker).not.toContain('addEventListener("fetch"');
    expect(worker).not.toContain("caches.open");
  });
});
