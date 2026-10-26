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

async function control(endpoint, payload) {
  let response;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      response = await fetch(`${controlUrl}${endpoint}`, {
        method: payload === undefined ? "GET" : "POST",
        headers: {
          "X-Madar-E2E-Control": controlToken,
          ...(payload === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: payload === undefined ? undefined : JSON.stringify(payload),
      });
      break;
    } catch (error) {
      if (attempt === 1) throw error;
    }
  }
  const body = await response.json();
  expect(response.ok, JSON.stringify(body)).toBe(true);
  expect(JSON.stringify(body)).not.toContain(providerToken);
  return body;
}

test("authorized browser API onboarding, automatic sync, freshness, and revocation", async ({ page, context, baseURL }) => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  await context.addCookies([{
    name: "madar_access_token", value: accessToken,
    url: baseURL, httpOnly: true, sameSite: "Lax",
  }]);
  const consoleMessages = [];
  const responseBodies = [];
  let sourceId = "";
  page.on("console", message => consoleMessages.push(message.text()));
  page.on("response", async response => {
    if (!response.url().includes("/api/")) return;
    try { responseBodies.push(await response.text()); } catch {}
    if (response.request().method() === "POST" && /\/data\/projects\/[^/]+\/sources$/.test(new URL(response.url()).pathname)) {
      try { sourceId = (await response.json()).id || sourceId; } catch {}
    }
  });

  const authStatusResponse = await page.request.get("/api/auth/user_status");
  const authStatus = await authStatusResponse.json();
  expect(authStatusResponse.ok(), JSON.stringify(authStatus)).toBe(true);
  expect(authStatus).toMatchObject({ logged_in: true, user: { id: userId } });
  const capabilityResponse = await page.request.get(
    `/api/users/${userId}/data/projects/${projectId}/source-capabilities`
  );
  const capabilityBody = await capabilityResponse.json();
  expect(capabilityResponse.ok(), JSON.stringify(capabilityBody)).toBe(true);
  expect(capabilityBody).toMatchObject({
    source_registry_available: true,
    api_sources_available: true,
    incremental_resources_available: true,
    credential_vault_available: true,
    automatic_sync_available: true,
  });
  expect(capabilityBody.providers).toEqual(expect.arrayContaining([
    expect.objectContaining({ key: "http_fixture" }),
  ]));

  await page.goto("/data-sources");
  const chooser = page.getByRole("dialog", { name: "Choose a data project" });
  await expect(chooser).toBeVisible();
  await chooser.getByRole("button", { name: "My Projects" }).click();
  await page.getByRole("button", { name: "Browser API project" }).click();
  await expect(page).toHaveURL(new RegExp(`/data-sources/projects/${projectId}/data$`));
  await expect(page.getByRole("heading", { name: "Data sources", exact: true })).toBeVisible();
  await expect(page.getByText("No registered sources yet", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Approved API connection/ })).toBeEnabled();
  await page.screenshot({ path: path.join(screenshotDir, "01-empty-data-sources.png"), fullPage: true });

  await page.getByRole("button", { name: /Approved API connection/ }).click();
  await page.getByPlaceholder("Example: Monthly sales uploads").fill("Browser business records");
  await expect(page.getByLabel("Provider")).toHaveValue("http_fixture");
  await expect(page.getByLabel("Resource type")).toHaveValue("records");
  await page.getByRole("button", { name: "Add API source" }).click();
  await expect(page.getByRole("heading", { name: "Browser business records" })).toBeVisible();
  expect(sourceId).toMatch(/^[0-9a-f-]{36}$/);

  const credentialInput = page.getByLabel(/Provider access token/);
  await expect(credentialInput).toBeVisible();
  await credentialInput.fill(providerToken);
  await page.getByRole("button", { name: "Save credentials" }).click();
  await expect(page.getByText("Credentials were encrypted and saved.")).toBeVisible();
  await expect(page.getByText("Ready", { exact: true }).first()).toBeVisible();
  await expect(credentialInput).toHaveCount(0);

  await page.getByRole("button", { name: "Validate and prepare resource" }).click();
  await expect(page.getByText("The connection was validated and the resource is ready for scheduling.")).toBeVisible();
  const syncToggle = page.getByRole("checkbox", { name: "Automatic synchronization" });
  await expect(syncToggle).toBeEnabled();
  await expect(syncToggle).not.toBeChecked();
  await syncToggle.check();
  await page.getByRole("combobox", { name: "Synchronization interval" }).selectOption("900");
  await page.getByRole("button", { name: "Save schedule" }).click();
  await expect(page.getByText("Synchronization settings were saved.")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "02-connected-and-scheduled.png"), fullPage: true });

  const firstSync = await control("/control/sync", { source_id: sourceId });
  expect(firstSync.claimed).toBe(1);
  expect(firstSync.outcomes[0]).toMatchObject({ outcome: "succeeded", committed_revision: 2 });
  const firstCheckpoints = await control("/control/checkpoints", {});
  expect(firstCheckpoints.claimed).toBeGreaterThanOrEqual(1);
  await page.reload();
  await expect(page.getByText("2", { exact: true })).toBeVisible();
  await expect(page.getByText("Ready for the latest revision")).toBeVisible();

  const secondSync = await control("/control/sync", { source_id: sourceId, force_due: true });
  expect(secondSync.claimed).toBe(1);
  expect(secondSync.outcomes[0]).toMatchObject({ outcome: "succeeded", committed_revision: 3 });
  await page.reload();
  await expect(page.getByText("3", { exact: true })).toBeVisible();
  await expect(page.getByText("Latest revision is not ready for analysis")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "03-checkpoint-pending.png"), fullPage: true });

  const finalCheckpoint = await control("/control/checkpoints", {});
  expect(finalCheckpoint.claimed).toBeGreaterThanOrEqual(1);
  await page.reload();
  await expect(page.getByText("Ready for the latest revision")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "04-current-analytics.png"), fullPage: true });

  const reopenResponse = page.waitForResponse(response => (
    response.request().method() === "GET" && response.url().includes(`/datasets/`)
  ));
  await page.getByRole("button", { name: "Open latest dataset" }).click();
  expect((await reopenResponse).status()).toBe(200);

  await page.goto(`/business-intelligence/projects/${projectId}/data`);
  await expect(page.getByRole("heading", { name: "Business Intelligence", exact: true })).toBeVisible();
  await expect(page.getByLabel("Dataset")).toHaveValue(/.+/);
  await expect(page.getByLabel("Immutable version")).toBeEnabled();
  await expect(page.getByText("Business meaning, unit, currency, row grain, relationship validity, confidence, and approval status are not declared.", { exact: false })).toBeVisible();

  await page.getByRole("tab", { name: "Explore" }).click();
  await expect(page.getByRole("heading", { name: "Bounded record preview" })).toBeVisible();
  await expect(page.getByText("The server applies allowlisted filters", { exact: false })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "value", exact: true }).first()).toBeVisible();

  await page.getByRole("tab", { name: "Metrics" }).click();
  await page.getByLabel("Operation").selectOption("sum");
  await page.getByLabel("Numeric column").selectOption("value");
  await page.getByLabel("Group by (optional)").selectOption("name");
  const metricResponse = page.waitForResponse(response => (
    response.request().method() === "POST" && response.url().includes("/versions/") && response.url().endsWith("/assist")
  ));
  await page.getByRole("button", { name: "Run calculation" }).click();
  expect((await metricResponse).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Sum of selected column" })).toBeVisible();
  await page.locator(".bi-result details").getByText("Result provenance", { exact: true }).click();
  await expect(page.getByText(projectId, { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Visualizations" }).click();
  await expect(page.getByRole("img", { name: "Sum of selected column" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "05-business-intelligence.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Business Intelligence", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshotDir, "06-business-intelligence-mobile.png"), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/data-sources/projects/${projectId}/data`);
  await expect(page.getByRole("heading", { name: "Data sources", exact: true })).toBeVisible();

  const evidence = await control("/control/evidence");
  expect(evidence.resources).toHaveLength(1);
  expect(evidence.resources[0]).toMatchObject({ committed_revision: 3, committed_cursor: "cursor-3" });
  expect(new Set(evidence.resources.map(item => item.dataset_id)).size).toBe(1);
  const recordState = Object.fromEntries(evidence.current_records.map(item => [item.source_record_id, item]));
  expect(recordState.A.is_deleted).toBe(true);
  expect(recordState.B.payload.value).toBe(25);
  expect(recordState.C.payload.value).toBe(35);
  expect(recordState.D.is_deleted).toBe(true);
  expect(recordState.E.payload.value).toBe(50);
  expect(evidence.checkpoints.some(item => item.target_revision === 3 && item.status === "ready")).toBe(true);
  expect(evidence.provider_requests.every(item => item.authorized)).toBe(true);
  expect(JSON.stringify(evidence)).not.toContain(providerToken);

  const authenticatedApi = await playwrightRequest.newContext({
    baseURL,
    extraHTTPHeaders: { Cookie: `madar_access_token=${accessToken}` },
  });
  expect((await authenticatedApi.get(`/api/users/7002/data/projects/${projectId}/sources`)).status()).toBe(403);
  expect((await authenticatedApi.get(`/api/users/${userId}/data/projects/${crossTenantProjectId}/sources`)).status()).toBe(404);
  await authenticatedApi.dispose();
  const anonymousApi = await playwrightRequest.newContext({ baseURL });
  expect((await anonymousApi.get(`/api/users/${userId}/data/projects/${projectId}/sources`)).status()).toBe(401);
  await anonymousApi.dispose();

  await page.getByRole("button", { name: "Revoke credentials" }).click();
  await expect(page.getByText("Credentials were revoked. Automatic synchronization is blocked.")).toBeVisible();
  await expect(page.getByText("Revoked credentials", { exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Automatic synchronization" })).toBeDisabled();
  const revokedRun = await control("/control/sync", { source_id: sourceId, force_due: true });
  expect(revokedRun.claimed).toBe(1);
  expect(revokedRun.outcomes[0]).toMatchObject({ outcome: "failed", credential_attention: true });
  await page.reload();
  await expect(page.getByText(/provider_credentials_revoked/)).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "07-credential-attention.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Data sources", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: path.join(screenshotDir, "08-mobile.png"), fullPage: true });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/builder-data/projects/${projectId}/data`);
  for (const step of ["Source", "Review", "Prepare", "Charts", "Report"]) {
    await expect(page.getByText(step, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText("API connection health", { exact: true })).toHaveCount(0);

  expect(consoleMessages.join("\n")).not.toContain(providerToken);
  expect(responseBodies.join("\n")).not.toContain(providerToken);
});
