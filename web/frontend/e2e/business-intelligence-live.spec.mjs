import fs from "node:fs";
import path from "node:path";
import { test, expect, request as playwrightRequest } from "@playwright/test";

const projectId = process.env.MADAR_E2E_PROJECT_ID;
const crossTenantProjectId = process.env.MADAR_E2E_CROSS_TENANT_PROJECT_ID;
const accessToken = process.env.MADAR_E2E_ACCESS_TOKEN;
const screenshotDir = process.env.MADAR_E2E_SCREENSHOT_DIR;
const userId = 7001;

test("historical analytics and persistent dashboard survive a real browser reload", async ({ page, context, baseURL }) => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  await context.addCookies([{ name: "madar_access_token", value: accessToken,
    url: baseURL, httpOnly: true, sameSite: "Lax" }]);

  const datasetsResponse = await page.request.get(`/api/users/${userId}/data/projects/${projectId}/datasets?limit=100`);
  expect(datasetsResponse.ok()).toBe(true);
  const datasets = (await datasetsResponse.json()).items;
  expect(datasets.length).toBeGreaterThan(0);
  let selected = null;
  let versions = [];
  for (const item of datasets) {
    const response = await page.request.get(`/api/users/${userId}/data/projects/${projectId}/datasets/${item.id}/versions?limit=100`);
    const body = await response.json();
    if (response.ok() && body.items.length > versions.length) { selected = item; versions = body.items; }
  }
  expect(selected).toBeTruthy();
  expect(versions.length).toBeGreaterThanOrEqual(2);

  // Enter with the same tenant/user-scoped selection contract that the project
  // chooser writes. This keeps the C5 rehearsal focused on the BI workflow and
  // avoids relying on transient React navigation state across an app remount.
  await page.goto("/");
  await page.evaluate(({ selectedProjectId }) => {
    window.sessionStorage.setItem(
      "madar:selected-data-project:7001:7001",
      selectedProjectId,
    );
  }, { selectedProjectId: projectId });
  await page.goto(`/business-intelligence/projects/${projectId}/data`);
  await expect(page.getByRole("heading", { name: "Business Intelligence", exact: true })).toBeVisible();
  await page.getByLabel("Dataset").selectOption(selected.id);
  await expect(page.getByLabel("Immutable version")).toHaveValue(versions[0].id);
  await page.getByLabel("Immutable version").selectOption(versions.at(-1).id);
  await expect(page.getByLabel("Immutable version")).toHaveValue(versions.at(-1).id);

  await page.getByRole("tab", { name: "Explore" }).click();
  const firstExplore = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/explore"));
  await page.getByRole("button", { name: "Apply query" }).click();
  expect((await firstExplore).status()).toBe(200);
  await expect(page.getByText(/\/ \d+/)).toBeVisible();

  await page.getByRole("tab", { name: "Metrics" }).click();
  await page.getByLabel("Operation").selectOption("distinct_count");
  await page.getByLabel("Value column").selectOption("name");
  await page.getByRole("button", { name: "Run calculation" }).click();
  await expect(page.getByRole("heading", { name: "Distinct non-missing values" })).toBeVisible();

  await page.getByRole("tab", { name: "Dashboard" }).click();
  await page.getByLabel("Dashboard name").fill("Disposable operations dashboard");
  await page.getByRole("button", { name: "Create dashboard" }).click();
  await expect(page.getByRole("button", { name: "Add current result" })).toBeVisible();
  await page.getByRole("button", { name: "Add current result" }).click();
  await expect(page.locator(".bi-widget").getByRole("heading", { name: "Distinct non-missing values" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "c5-dashboard-created.png"), fullPage: true });

  await page.reload();
  await page.getByRole("tab", { name: "Dashboard" }).click();
  await expect(page.getByLabel("Persistent dashboards")).toHaveValue(/.+/);
  await expect(page.locator(".bi-widget").getByRole("heading", { name: "Distinct non-missing values" })).toBeVisible();
  await expect(page.locator(".bi-widget details code")).toContainText(versions.at(-1).id);
  await page.locator(".bi-widget").getByRole("button", { name: "Refresh to latest" }).click();
  await expect(page.locator(".bi-widget details code")).toContainText(versions.at(-1).id);
  await page.screenshot({ path: path.join(screenshotDir, "c5-dashboard-reopened.png"), fullPage: true });

  const authenticatedApi = await playwrightRequest.newContext({ baseURL,
    extraHTTPHeaders: { Cookie: `madar_access_token=${accessToken}` } });
  expect((await authenticatedApi.get(`/api/users/7002/data/projects/${projectId}/dashboards`)).status()).toBe(403);
  expect((await authenticatedApi.get(`/api/users/${userId}/data/projects/${crossTenantProjectId}/dashboards`)).status()).toBe(404);
  await authenticatedApi.dispose();
  const anonymousApi = await playwrightRequest.newContext({ baseURL });
  expect((await anonymousApi.get(`/api/users/${userId}/data/projects/${projectId}/dashboards`)).status()).toBe(401);
  await anonymousApi.dispose();

  page.once("dialog", dialog => dialog.accept());
  await page.locator(".bi-widget").getByRole("button", { name: "Remove widget" }).click();
  await expect(page.getByText("This dashboard has no widgets.", { exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Delete dashboard" }).click();
  await expect(page.getByRole("button", { name: "Create dashboard" })).toBeVisible();
});
