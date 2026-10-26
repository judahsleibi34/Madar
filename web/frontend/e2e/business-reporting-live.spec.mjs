import fs from "node:fs";
import path from "node:path";
import { test, expect, request as playwrightRequest } from "@playwright/test";

const projectId = process.env.MADAR_E2E_PROJECT_ID;
const crossTenantProjectId = process.env.MADAR_E2E_CROSS_TENANT_PROJECT_ID;
const accessToken = process.env.MADAR_E2E_ACCESS_TOKEN;
const providerToken = process.env.MADAR_E2E_PROVIDER_TOKEN;
const controlUrl = process.env.MADAR_E2E_CONTROL_URL;
const controlToken = process.env.MADAR_E2E_CONTROL_TOKEN;
const screenshotDir = process.env.MADAR_E2E_SCREENSHOT_DIR;
const userId = 7001;

test("scheduled and manual reports retain exact version provenance through the real worker", async ({ page, context, baseURL }) => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  await context.addCookies([{ name: "madar_access_token", value: accessToken,
    url: baseURL, httpOnly: true, sameSite: "Lax" }]);
  const control = await playwrightRequest.newContext({ baseURL: controlUrl,
    extraHTTPHeaders: { "x-madar-e2e-control": controlToken } });
  const root = `/api/users/${userId}/data/projects/${projectId}`;
  let datasets = (await (await page.request.get(`${root}/datasets?limit=100`)).json()).items;
  if (!datasets.length) {
    await page.goto("/data-sources");
    const chooser = page.getByRole("dialog", { name: "Choose a data project" });
    await expect(chooser).toBeVisible();
    await chooser.getByRole("button", { name: "My Projects" }).click();
    await page.getByRole("button", { name: "Browser API project" }).click();
    await page.getByRole("button", { name: /Approved API connection/ }).click();
    await page.getByPlaceholder("Example: Monthly sales uploads").fill("Reporting source");
    await page.getByRole("button", { name: "Add API source" }).click();
    await page.getByLabel(/Provider access token/).fill(providerToken);
    await page.getByRole("button", { name: "Save credentials" }).click();
    await expect(page.getByText("Credentials were encrypted and saved.")).toBeVisible();
    await page.getByRole("button", { name: "Validate and prepare resource" }).click();
    await expect(page.getByText("The connection was validated and the resource is ready for scheduling.")).toBeVisible();
    const syncToggle = page.getByRole("checkbox", { name: "Automatic synchronization" });
    await syncToggle.check();
    await page.getByRole("button", { name: "Save schedule" }).click();
    await expect(page.getByText("Synchronization settings were saved.")).toBeVisible();
    const sources = (await (await page.request.get(`${root}/sources?limit=100`)).json()).items;
    const initialSync = await control.post("/control/sync", { data: { source_id: sources[0].id } });
    expect(initialSync.ok()).toBe(true);
    const initialSyncBody = await initialSync.json();
    expect(initialSyncBody.claimed).toBe(1);
    expect(initialSyncBody.outcomes[0].outcome).toBe("succeeded");
    const checkpoint = await control.post("/control/checkpoints", { data: {} });
    expect(checkpoint.ok()).toBe(true);
    expect((await checkpoint.json()).claimed).toBeGreaterThanOrEqual(1);
    datasets = (await (await page.request.get(`${root}/datasets?limit=100`)).json()).items;
  }
  expect(datasets.length).toBeGreaterThan(0);
  const dataset = datasets[0];
  const versions = (await (await page.request.get(`${root}/datasets/${dataset.id}/versions?limit=100`)).json()).items;
  expect(versions.length).toBeGreaterThan(0);

  await page.goto("/");
  await page.evaluate(({ selectedProjectId }) => window.sessionStorage.setItem(
    "madar:selected-data-project:7001:7001", selectedProjectId,
  ), { selectedProjectId: projectId });
  await page.goto(`/business-intelligence/projects/${projectId}/data`);
  await expect(page.getByRole("heading", { name: "Business Intelligence", exact: true })).toBeVisible();
  await page.getByLabel("Dataset").selectOption(dataset.id);
  await page.getByLabel("Immutable version").selectOption(versions[0].id);
  await page.getByRole("tab", { name: "Metrics" }).click();
  await page.getByRole("button", { name: "Run calculation" }).click();
  await expect(page.getByRole("heading", { name: "Record count" })).toBeVisible();
  await page.getByRole("tab", { name: "Dashboard" }).click();
  await page.getByLabel("Dashboard name").fill("Disposable recurring report");
  await page.getByRole("button", { name: "Create dashboard" }).click();
  await page.getByRole("button", { name: "Add current result" }).click();
  await expect(page.locator(".bi-widget").getByRole("heading", { name: "Record count" })).toBeVisible();
  await page.getByLabel("Version policy").selectOption("latest_committed");
  await page.getByRole("button", { name: "Add current result" }).click();
  await expect(page.locator(".bi-widget")).toHaveCount(2);
  const dashboardId = await page.getByLabel("Persistent dashboards").inputValue();
  expect(dashboardId).toMatch(/^[0-9a-f-]{36}$/);
  const refreshResponse = page.waitForResponse(response => response.request().method() === "PATCH"
    && response.url().endsWith("/automatic-refresh"));
  await page.getByRole("checkbox", { name: /Automatically generate a report/ }).click();
  expect((await refreshResponse).status()).toBe(200);
  await expect(page.getByRole("checkbox", { name: /Automatically generate a report/ })).toBeChecked();

  if (process.env.MADAR_E2E_REPORTING_ONLY === "YES") {
    const beforeRefresh = await (await page.request.get(`${root}/dashboards/${dashboardId}`)).json();
    expect(beforeRefresh.widgets.map(widget => widget.version_policy).sort()).toEqual(["latest_committed", "pinned"]);
    expect(new Set(beforeRefresh.widgets.map(widget => widget.dataset_version_id))).toEqual(new Set([versions[0].id]));
    const sources = (await (await page.request.get(`${root}/sources?limit=100`)).json()).items;
    expect(sources.length).toBeGreaterThan(0);
    const newSync = await control.post("/control/sync", { data: { source_id: sources[0].id, force_due: true } });
    expect(newSync.ok()).toBe(true);
    expect((await newSync.json()).outcomes[0].outcome).toBe("succeeded");
    const newCheckpoint = await control.post("/control/checkpoints", { data: {} });
    expect(newCheckpoint.ok()).toBe(true);
    expect((await newCheckpoint.json()).claimed).toBeGreaterThanOrEqual(1);
    const newVersions = (await (await page.request.get(`${root}/datasets/${dataset.id}/versions?limit=100`)).json()).items;
    expect(newVersions[0].id).not.toBe(versions[0].id);
    const refreshScheduler = await control.post("/control/report-scheduler", { data: { limit: 5 } });
    expect(refreshScheduler.ok()).toBe(true);
    expect((await refreshScheduler.json()).refreshes.dispatched).toBe(1);
    const refreshWorker = await control.post("/control/report-worker", { data: { limit: 5 } });
    expect(refreshWorker.ok()).toBe(true);
    expect((await refreshWorker.json()).claimed).toBe(1);
    const reportItems = (await (await page.request.get(`${root}/reports?limit=50`)).json()).items;
    const refreshItem = reportItems.find(item => item.trigger_type === "data_refresh");
    expect(refreshItem).toBeTruthy();
    const refreshReport = await (await page.request.get(`${root}/reports/${refreshItem.id}`)).json();
    const byPolicy = Object.fromEntries(refreshReport.version_vector.map(item => [item.version_policy, item]));
    expect(byPolicy.pinned.dataset_version_id).toBe(versions[0].id);
    expect(byPolicy.latest_committed.dataset_version_id).toBe(newVersions[0].id);
    const afterRefresh = await (await page.request.get(`${root}/dashboards/${dashboardId}`)).json();
    expect(afterRefresh.widgets.map(widget => widget.dataset_version_id)).toEqual(
      beforeRefresh.widgets.map(widget => widget.dataset_version_id),
    );
  }

  await page.getByRole("tab", { name: "Reports" }).click();
  await page.getByLabel("Schedule name").fill("Daily UTC report");
  await page.getByLabel("Cadence").selectOption("daily");
  await page.getByLabel("Timezone").fill("UTC");
  await page.getByLabel("Local time").fill("09:00");
  await page.getByRole("button", { name: "Create schedule" }).click();
  await expect(page.getByText("Daily UTC report", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Generate report now" }).click();

  const manualWorker = await control.post("/control/report-worker", { data: { limit: 5 } });
  expect(manualWorker.ok()).toBe(true);
  expect((await manualWorker.json()).claimed).toBeGreaterThanOrEqual(1);
  const scheduler = await control.post("/control/report-scheduler", { data: { limit: 5, force_due: true } });
  expect(scheduler.ok()).toBe(true);
  expect((await scheduler.json()).schedules.dispatched).toBeGreaterThanOrEqual(1);
  const scheduledWorker = await control.post("/control/report-worker", { data: { limit: 5 } });
  expect(scheduledWorker.ok()).toBe(true);
  await control.dispose();

  await page.reload();
  await page.getByRole("tab", { name: "Reports" }).click();
  await expect(page.getByText(/manual · completed/)).toBeVisible();
  await expect(page.getByText(/scheduled · completed/)).toBeVisible();
  await page.getByRole("button", { name: "Open report" }).first().click();
  await expect(page.locator(".bi-report-print")).toContainText(versions[0].id);
  await expect(page.locator(".bi-report-print")).toContainText("business meaning, units, currencies");
  const download = await page.request.get(`${root}/reports/${(await (await page.request.get(`${root}/reports?limit=50`)).json()).items[0].id}/export.csv`);
  expect(download.status()).toBe(200);
  expect(download.headers()["content-type"]).toContain("text/csv");
  expect(await download.text()).toContain("dataset_version_id");
  await page.screenshot({ path: path.join(screenshotDir, "c5-recurring-report.png"), fullPage: true });

  const authenticatedApi = await playwrightRequest.newContext({ baseURL,
    extraHTTPHeaders: { Cookie: `madar_access_token=${accessToken}` } });
  expect((await authenticatedApi.get(`/api/users/7002/data/projects/${projectId}/reports`)).status()).toBe(403);
  expect((await authenticatedApi.get(`/api/users/${userId}/data/projects/${crossTenantProjectId}/reports`)).status()).toBe(404);
  await authenticatedApi.dispose();
  const anonymousApi = await playwrightRequest.newContext({ baseURL });
  expect((await anonymousApi.get(`${root}/reports`)).status()).toBe(401);
  await anonymousApi.dispose();
});
