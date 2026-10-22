import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

const projectId = process.env.MADAR_E2E_PROJECT_ID;
const accessToken = process.env.MADAR_E2E_ACCESS_TOKEN;
const screenshotDir = process.env.MADAR_E2E_SCREENSHOT_DIR;
const userId = 7001;

test("schema 141 shows the safe Data Sources capability fallback", async ({ page, context, baseURL }) => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  await context.addCookies([{
    name: "madar_access_token", value: accessToken,
    url: baseURL, httpOnly: true, sameSite: "Lax",
  }]);
  const authResponse = await page.request.get("/api/auth/user_status");
  expect(authResponse.ok(), await authResponse.text()).toBe(true);
  const capabilityResponse = await page.request.get(
    `/api/users/${userId}/data/projects/${projectId}/source-capabilities`
  );
  const capabilities = await capabilityResponse.json();
  expect(capabilityResponse.ok(), JSON.stringify(capabilities)).toBe(true);
  expect(capabilities).toMatchObject({
    source_registry_available: false,
    api_sources_available: false,
    incremental_resources_available: false,
    credential_vault_available: false,
    automatic_sync_available: false,
    providers: [],
  });

  await page.goto("/data-sources");
  const chooser = page.getByRole("dialog", { name: "Choose a data project" });
  await chooser.getByRole("button", { name: "My Projects" }).click();
  await page.getByRole("button", { name: "Browser API project" }).click();
  await expect(page).toHaveURL(new RegExp(`/data-sources/projects/${projectId}/data$`));
  await expect(page.getByText("Persistent sources require an upgrade")).toBeVisible();
  await expect(page.getByText("Not Found", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add API source" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Spreadsheet upload" })).toBeEnabled();
  await page.screenshot({ path: path.join(screenshotDir, "00-physical-schema-141-fallback.png"), fullPage: true });
});
