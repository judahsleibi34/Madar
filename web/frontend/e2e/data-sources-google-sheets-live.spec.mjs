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
const spreadsheetId = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789";

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
  expect(JSON.stringify(body)).not.toContain("fixture-google-refresh");
  return body;
}

test("Google Sheets OAuth, mapping, stable dataset sync, conservative deletion, and revocation", async ({ page, context, baseURL }) => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  await context.addCookies([{
    name: "madar_access_token", value: accessToken,
    url: baseURL, httpOnly: true, sameSite: "Lax",
  }]);
  const responseBodies = [];
  let sourceId = "";
  page.on("response", async response => {
    if (!response.url().includes("/api/")) return;
    try { responseBodies.push(await response.text()); } catch {}
    if (response.request().method() === "POST" && /\/data\/projects\/[^/]+\/sources$/.test(new URL(response.url()).pathname)) {
      try {
        const body = await response.json();
        if (body.provider_key === "google_sheets") sourceId = body.id;
      } catch {}
    }
  });

  const capabilitiesResponse = await page.request.get(
    `/api/users/${userId}/data/projects/${projectId}/source-capabilities`,
  );
  const capabilities = await capabilitiesResponse.json();
  expect(capabilitiesResponse.ok(), JSON.stringify(capabilities)).toBe(true);
  expect(capabilities.google_sheets_available).toBe(true);
  expect(capabilities.providers).toEqual(expect.arrayContaining([
    expect.objectContaining({ key: "google_sheets", credential_type: "oauth" }),
  ]));

  await page.goto(`/data-sources/projects/${projectId}/data`);
  const chooser = page.getByRole("dialog", { name: "Choose a data project" });
  await expect(chooser).toBeVisible();
  await chooser.getByRole("button", { name: "My Projects" }).click();
  await page.getByRole("button", { name: "Browser API project" }).click();
  await expect(page.getByRole("heading", { name: "Data sources", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Approved API connection/ }).click();
  await page.getByPlaceholder("Example: Monthly sales uploads").fill("Google business sheet");
  await page.getByLabel("Provider").selectOption("google_sheets");
  await expect(page.getByLabel("Resource type")).toHaveValue("sheet");
  await page.getByRole("button", { name: "Add API source" }).click();
  await expect(page.getByRole("heading", { name: "Google business sheet" })).toBeVisible();
  expect(sourceId).toMatch(/^[0-9a-f-]{36}$/);

  await page.getByRole("button", { name: "Connect Google account" }).click();
  await page.waitForURL(new RegExp(`/data-sources/projects/${projectId}/data\\?google_sheets=connected$`));
  const sourceCard = page.locator("article").filter({ hasText: "Google business sheet" });
  await sourceCard.getByRole("button", { name: /Select source|Selected/ }).click();
  await expect(page.getByText("Ready", { exact: true }).first()).toBeVisible();

  await page.getByLabel("Google Sheets link").fill(
    `https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit#gid=5`,
  );
  await page.getByRole("button", { name: "Find spreadsheet tabs" }).click();
  await expect(page.getByRole("combobox", { name: "Spreadsheet tab" })).toHaveValue("5");
  await page.getByRole("button", { name: "Preview data" }).click();
  await expect(page.getByRole("region", { name: "Preview data" })).toContainText("Alpha");
  await expect(page.getByRole("combobox", { name: "Stable record ID column" })).toHaveValue("id");
  await page.getByRole("button", { name: "Save Google Sheets mapping" }).click();
  await expect(page.getByText("The spreadsheet mapping was validated and saved.")).toBeVisible();
  await expect(page.getByText(/Fixture business · Orders/)).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "07-google-mapped.png"), fullPage: true });

  await page.getByRole("button", { name: "Validate and prepare resource" }).click();
  await expect(page.getByText("The connection was validated and the resource is ready for scheduling.")).toBeVisible();
  const toggle = page.getByRole("checkbox", { name: "Automatic synchronization" });
  await toggle.check();
  await page.getByRole("combobox", { name: "Synchronization interval" }).selectOption("900");
  await page.getByRole("button", { name: "Save schedule" }).click();
  await expect(page.getByText("Synchronization settings were saved.")).toBeVisible();

  const unchanged = await control("/control/sync", { source_id: sourceId, force_due: true });
  expect(unchanged.claimed).toBe(1);
  expect(unchanged.outcomes[0], JSON.stringify(unchanged)).toMatchObject({
    outcome: "succeeded", committed_revision: 1,
  });
  await control("/control/google-sheet", { version: 2 });
  const changed = await control("/control/sync", { source_id: sourceId, force_due: true });
  expect(changed.claimed).toBe(1);
  expect(changed.outcomes[0]).toMatchObject({ outcome: "succeeded", committed_revision: 2 });
  await control("/control/checkpoints", {});
  await page.reload();
  await sourceCard.getByRole("button", { name: /Select source|Selected/ }).click();
  await expect(page.getByText("2", { exact: true })).toBeVisible();
  await expect(page.getByText("Ready for the latest revision")).toBeVisible();

  const evidence = await control("/control/evidence");
  const resource = evidence.resources.find(item => item.source_id === sourceId);
  expect(resource).toMatchObject({ committed_revision: 2 });
  expect(resource.committed_cursor).toMatch(/^snapshot:[0-9a-f]{64}$/);
  expect(evidence.google_mappings).toEqual(expect.arrayContaining([
    expect.objectContaining({ source_id: sourceId, spreadsheet_id: spreadsheetId,
                              sheet_id: 5, record_id_column: "id" }),
  ]));
  const rows = Object.fromEntries(evidence.current_records
    .filter(item => item.dataset_id === resource.dataset_id)
    .map(item => [item.source_record_id, item]));
  expect(rows.A.is_deleted).toBe(false);
  expect(rows.B.payload.amount).toBe(25);
  expect(rows.C.payload.amount).toBe(30);
  expect(responseBodies.join("\n")).not.toContain("fixture-google-refresh");
  expect(responseBodies.join("\n")).not.toContain("fixture-google-access");

  const authenticatedApi = await playwrightRequest.newContext({
    baseURL, extraHTTPHeaders: { Cookie: `madar_access_token=${accessToken}` },
  });
  expect((await authenticatedApi.get(
    `/api/users/${userId}/data/projects/${crossTenantProjectId}/sources/${sourceId}/google-sheets/mapping`,
  )).status()).toBe(404);
  await authenticatedApi.dispose();

  await page.getByRole("button", { name: "Revoke credentials" }).click();
  await expect(page.getByText("Credentials were revoked. Automatic synchronization is blocked.")).toBeVisible();
  await control("/control/google-sheet", { version: 2, revoked: true });
  const revoked = await control("/control/sync", { source_id: sourceId, force_due: true });
  expect(revoked.claimed).toBe(1);
  expect(revoked.outcomes[0]).toMatchObject({ outcome: "failed", credential_attention: true });
  await page.screenshot({ path: path.join(screenshotDir, "08-google-revoked.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});
