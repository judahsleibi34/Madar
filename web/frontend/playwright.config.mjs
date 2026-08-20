import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import { defineConfig } from "@playwright/test";
import { assertIsolatedE2EEnvironment } from "./e2e/safety.mjs";

const configDirectory = path.dirname(fileURLToPath(import.meta.url));
const testEnvironmentPath = path.resolve(configDirectory, "../.env.test.local");

const environmentResult = dotenv.config({
  path: testEnvironmentPath,
  // The repository-root test file is authoritative for each fresh run. This
  // prevents values inherited by the shell from reusing stale credentials.
  override: true,
  quiet: true,
});

if (environmentResult.error) {
  throw new Error("Authenticated Playwright testing requires the repository-root .env.test.local file.");
}

for (const variableName of ["TEST_USER_EMAIL", "TEST_USER_PASSWORD", "PUBLISHED_FORM_PATH"]) {
  if (!process.env[variableName]?.trim()) {
    throw new Error(`Authenticated Playwright testing requires ${variableName}.`);
  }
}

const isolatedEnvironment = assertIsolatedE2EEnvironment(process.env);

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.mjs",
  timeout: 8 * 60 * 1000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  workers: 1,
  preserveOutput: "always",
  reporter: "line",
  use: {
    baseURL: isolatedEnvironment.baseUrl,
    channel: "chrome",
    headless: true,
    screenshot: "off",
    trace: "off",
    video: "off",
  },
});
