import { defineConfig } from "@playwright/test";
// Local actual-app tests: every API mocked, every non-local request blocked.
export default defineConfig({ testDir: "./e2e", testMatch: "commercial-ui.mock.spec.mjs", workers: 1, use: { baseURL: "http://127.0.0.1:5179", browserName: "chromium", headless: true }, webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5179 --strictPort", url: "http://127.0.0.1:5179", reuseExistingServer: false } });
