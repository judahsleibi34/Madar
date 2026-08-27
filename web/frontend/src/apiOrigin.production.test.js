import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cwd } from "node:process";
import { describe, expect, it } from "vitest";

const dockerfile = readFileSync(resolve(cwd(), "Dockerfile"), "utf8");
const packageJson = JSON.parse(readFileSync(resolve(cwd(), "package.json"), "utf8"));
const originCheck = readFileSync(resolve(cwd(), "scripts/check-api-origin.mjs"), "utf8");
const bundleCheck = readFileSync(resolve(cwd(), "scripts/check-production-bundle.mjs"), "utf8");

describe("production API origin build contract", () => {
  it("requires and verifies the canonical API origin in immutable builds", () => {
    expect(dockerfile).toContain("ARG MADAR_REQUIRE_PRODUCTION_API_URL=false");
    expect(dockerfile).toContain("MADAR_REQUIRE_PRODUCTION_API_URL=$MADAR_REQUIRE_PRODUCTION_API_URL");
    expect(packageJson.scripts.build).toContain("api-origin:audit");
    expect(packageJson.scripts.build).toContain("bundle-origin:audit");
    expect(originCheck).toContain("https://api.madarportal.com");
    expect(bundleCheck).toContain("https://api.madarportal.com");
  });

  it("keeps third-party analytics origins out of the application bundle contract", () => {
    expect(bundleCheck).toMatch(/jsdelivr/);
    expect(bundleCheck).toMatch(/cloudflareinsights/);
  });
});
