import { defineConfig } from "@playwright/test";
import { assertIsolatedE2EEnvironment } from "./e2e/safety.mjs";

const isolated = assertIsolatedE2EEnvironment(process.env);
for (const name of [
  "MADAR_E2E_ACCESS_TOKEN", "MADAR_E2E_CONTROL_URL", "MADAR_E2E_CONTROL_TOKEN",
  "MADAR_E2E_PROJECT_ID", "MADAR_E2E_CROSS_TENANT_PROJECT_ID",
  "MADAR_E2E_PROVIDER_TOKEN", "MADAR_E2E_SCREENSHOT_DIR",
]) {
  if (!process.env[name]?.trim()) throw new Error(`${name} is required`);
}
for (const name of ["MADAR_E2E_CONTROL_URL"]) {
  const url = new URL(process.env[name]);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname)) {
    throw new Error(`${name} must be an HTTP loopback URL`);
  }
}

export default defineConfig({
  testDir: "./e2e",
  testMatch: process.env.MADAR_E2E_SPEC || "data-sources-live.spec.mjs",
  timeout: 8 * 60 * 1000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: isolated.baseUrl,
    channel: "chrome",
    headless: true,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    screenshot: "off",
    trace: "off",
    video: "off",
  },
});
