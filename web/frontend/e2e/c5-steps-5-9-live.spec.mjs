import fs from "node:fs";
import path from "node:path";
import { test, expect, request as playwrightRequest } from "@playwright/test";

const projectId = process.env.MADAR_E2E_PROJECT_ID;
const crossTenantProjectId = process.env.MADAR_E2E_CROSS_TENANT_PROJECT_ID;
const ownerToken = process.env.MADAR_E2E_ACCESS_TOKEN;
const memberToken = process.env.MADAR_E2E_MEMBER_ACCESS_TOKEN;
const crossToken = process.env.MADAR_E2E_CROSS_TENANT_ACCESS_TOKEN;
const controlUrl = process.env.MADAR_E2E_CONTROL_URL;
const controlToken = process.env.MADAR_E2E_CONTROL_TOKEN;
const screenshotDir = process.env.MADAR_E2E_SCREENSHOT_DIR;
const ownerId = 7001;
const memberId = 7003;

for (const [name, value] of Object.entries({ memberToken, crossToken })) {
  if (!value) throw new Error(`${name} is required for the C5 Steps 5-9 integration checkpoint`);
}

async function body(response) {
  const value = await response.json();
  expect(response.ok(), JSON.stringify(value)).toBe(true);
  return value;
}

async function session(baseURL, token) {
  const bootstrap = await playwrightRequest.newContext({
    baseURL,
    extraHTTPHeaders: { Cookie: `madar_access_token=${token}`, Origin: baseURL },
  });
  const status = await bootstrap.get("/api/auth/user_status");
  expect(status.ok(), await status.text()).toBe(true);
  const payload = await status.json();
  const csrfToken = status.headers()["x-csrf-token"] || payload.csrf_token;
  expect(csrfToken).toBeTruthy();
  await bootstrap.dispose();
  return playwrightRequest.newContext({
    baseURL,
    extraHTTPHeaders: {
      Cookie: `madar_access_token=${token}; madar_csrf_token=${csrfToken}`,
      Origin: baseURL,
      "X-CSRF-Token": csrfToken,
    },
  });
}

test("C5 Steps 5-9 retain exact results across exports, sharing, delivery, and expiry", async ({ page, context, baseURL }) => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  await context.addCookies([{ name: "madar_access_token", value: ownerToken,
    url: baseURL, httpOnly: true, sameSite: "Lax" }]);
  const ownerRoot = `/api/users/${ownerId}/data/projects/${projectId}`;
  const memberRoot = `/api/users/${memberId}/data/projects/${projectId}`;
  const control = await playwrightRequest.newContext({ baseURL: controlUrl,
    extraHTTPHeaders: { "x-madar-e2e-control": controlToken } });
  const owner = await session(baseURL, ownerToken);
  const member = await session(baseURL, memberToken);
  const crossTenant = await session(baseURL, crossToken);
  const anonymous = await playwrightRequest.newContext({ baseURL });

  // Reuse the source/webhook fixture data and choose an immutable version with
  // the technical date field introduced by the provider fixture.
  const sources = await body(await owner.get(`${ownerRoot}/sources?limit=100`));
  expect(sources.items.length).toBeGreaterThan(0);
  const datasets = await body(await owner.get(`${ownerRoot}/datasets?limit=100`));
  let selection = null;
  for (const dataset of datasets.items) {
    const versions = await body(await owner.get(`${ownerRoot}/datasets/${dataset.id}/versions?limit=100`));
    for (const version of [...versions.items].reverse()) {
      const reopened = await owner.get(`${ownerRoot}/datasets/${dataset.id}/versions/${version.id}`);
      if (!reopened.ok()) continue;
      const value = await reopened.json();
      if ((value.columns || []).includes("occurred_at") && (value.columns || []).includes("value")) {
        selection = { dataset, version, reopened: value };
        break;
      }
    }
    if (selection) break;
  }
  expect(selection).toBeTruthy();

  let dashboard = await body(await owner.post(`${ownerRoot}/dashboards`, { data: {
    name: "C5 5-9 immutable period checkpoint", description: "Disposable integration evidence",
  } }));
  const periodSpec = {
    operation: "date_aggregate", label: "Verified local-day records",
    date_column: "occurred_at", aggregation: "count", period: "day",
    timezone: "America/New_York", start_date: "2026-03-08", end_date: "2026-03-09",
  };
  let mutation = await body(await owner.post(`${ownerRoot}/dashboards/${dashboard.id}/widgets`, { data: {
    expected_revision: dashboard.revision, widget_type: "bar", title: "Local period activity",
    dataset_id: selection.dataset.id, dataset_version_id: selection.version.id,
    version_policy: "pinned", analysis_spec: periodSpec,
    layout_config: { x: 0, y: 0, w: 8, h: 4 },
    display_options: { show_table: true, show_legend: true },
  } }));
  dashboard = mutation.dashboard;
  const periodWidget = mutation.widget;
  mutation = await body(await owner.post(`${ownerRoot}/dashboards/${dashboard.id}/widgets`, { data: {
    expected_revision: dashboard.revision, widget_type: "table", title: "Formula-safe grouped values",
    dataset_id: selection.dataset.id, dataset_version_id: selection.version.id,
    version_policy: "pinned", analysis_spec: {
      operation: "sum", label: "Grouped values", value_column: "value", group_column: "unsafe_label",
    }, layout_config: { x: 0, y: 4, w: 12, h: 4 },
    display_options: { show_table: true, show_legend: false },
  } }));
  dashboard = mutation.dashboard;

  const execution = await body(await owner.post(
    `${ownerRoot}/dashboards/${dashboard.id}/widgets/${periodWidget.id}/execute`,
    { data: { refresh_latest: false, language: "en" } },
  ));
  expect(execution.status).toBe("ready");
  expect(execution.provenance.dataset_version_id).toBe(selection.version.id);
  expect(execution.provenance.reporting_period).toEqual({
    date_column: "occurred_at", start_date: "2026-03-08", end_date: "2026-03-09",
    timezone: "America/New_York", grouping_period: "day",
  });
  const mappings = execution.result.metadata.mappings_used;
  expect(mappings.timezone).toBe("America/New_York");
  expect(mappings.requested_start_date).toBe("2026-03-08");
  expect(mappings.requested_end_date).toBe("2026-03-09");
  expect(mappings.selected_row_count).toBeGreaterThan(0);

  const lifecycle = await body(await owner.patch(`${ownerRoot}/report-lifecycle`, { data: {
    expected_revision: null, retention_days: 7, cleanup_enabled: true,
  } }));
  expect(lifecycle.cleanup_enabled).toBe(true);

  const queued = await body(await owner.post(`${ownerRoot}/reports`, { data: {
    dashboard_id: dashboard.id, idempotency_key: "c5-steps-5-9-manual-report-0001",
  } }));
  const reportRun = await body(await control.post("/control/report-worker", { data: { limit: 5 } }));
  expect(reportRun.results.some((item) => item.id === queued.id && item.status === "completed")).toBe(true);
  const report = await body(await owner.get(`${ownerRoot}/reports/${queued.id}`));
  const periodResult = report.result_snapshot.widgets.find((item) => item.widget_id === periodWidget.id);
  expect(periodResult.result).toEqual(execution.result);
  expect(periodResult.provenance.dataset_version_id).toBe(selection.version.id);
  expect(report.version_vector.find((item) => item.widget_id === periodWidget.id).dataset_version_id).toBe(selection.version.id);
  expect(report.definition_snapshot.widgets.find((item) => item.id === periodWidget.id).analysis_spec).toEqual(periodSpec);

  // Browser reload proves the saved layout/filter contract, then switches the
  // real workspace to Arabic and verifies RTL without changing identifier/date direction.
  await page.goto("/");
  await page.evaluate(({ selectedProjectId }) => window.sessionStorage.setItem(
    "madar:selected-data-project:7001:7001", selectedProjectId,
  ), { selectedProjectId: projectId });
  await page.goto(`/business-intelligence/projects/${projectId}/data`);
  await page.getByRole("tab", { name: "Dashboard" }).click();
  await page.getByLabel("Persistent dashboards").selectOption(dashboard.id);
  await expect(page.locator(".bi-widget").getByRole("heading", { name: "Local period activity" })).toBeVisible();
  await expect(page.locator(".bi-widget").filter({ hasText: "Local period activity" })).toContainText("2026-03-08 — 2026-03-09");
  await expect(page.locator(".bi-widget").filter({ hasText: "Local period activity" })).toContainText("America/New_York");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.locator("button[data-next-language='ar']").click();
  await expect(page.locator("main.bi-workspace")).toHaveAttribute("dir", "rtl");
  await expect(page.locator(".bi-widget").filter({ hasText: "Local period activity" }).locator("dd[dir='ltr']").first()).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "c5-steps-5-9-arabic-dashboard.png"), fullPage: true });

  const pdf = await owner.get(`${ownerRoot}/reports/${report.id}/export.pdf?language=ar`);
  expect(pdf.status()).toBe(200);
  expect(pdf.headers()["content-type"]).toContain("application/pdf");
  expect(pdf.headers()["cache-control"]).toBe("private, no-store");
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  const xlsx = await owner.get(`${ownerRoot}/reports/${report.id}/export.xlsx?language=ar`);
  expect(xlsx.status()).toBe(200);
  expect(xlsx.headers()["content-type"]).toContain("spreadsheetml.sheet");
  expect(xlsx.headers()["cache-control"]).toBe("private, no-store");
  expect((await xlsx.body()).subarray(0, 2).toString()).toBe("PK");
  const exportEvidence = await body(await control.post("/control/report-export-evidence", { data: { report_id: report.id } }));
  expect(exportEvidence).toEqual({
    pdf_magic: true, pdf_private: true, xlsx_private: true, xlsx_rtl: true,
    xlsx_no_formulas: true, xlsx_formula_escaped: true,
    xlsx_has_versions: true, xlsx_has_arabic: true,
  });
  expect((await anonymous.get(`${ownerRoot}/reports/${report.id}/export.pdf?language=ar`)).status()).toBe(401);
  expect((await crossTenant.get(`/api/users/7002/data/projects/${projectId}/reports/${report.id}/export.xlsx?language=ar`)).status()).toBe(404);
  expect((await crossTenant.get(`/api/users/7002/data/projects/${crossTenantProjectId}/reports/${report.id}/export.xlsx?language=ar`)).status()).toBe(404);

  // Dashboard viewers cannot mutate. Editors can update through the owner's
  // revision-fenced resource, and revocation removes both read and write access.
  let share = await body(await owner.put(`${ownerRoot}/dashboards/${dashboard.id}/shares/${memberId}`, { data: {
    expected_revision: dashboard.revision, member_user_id: memberId, permission: "viewer",
  } }));
  dashboard = share.dashboard;
  expect((await member.get(`${memberRoot}/dashboards/${dashboard.id}`)).status()).toBe(200);
  expect((await member.patch(`${memberRoot}/dashboards/${dashboard.id}`, { data: {
    expected_revision: dashboard.revision, name: "Viewer must not edit", description: "denied",
  } })).status()).toBe(404);
  share = await body(await owner.put(`${ownerRoot}/dashboards/${dashboard.id}/shares/${memberId}`, { data: {
    expected_revision: dashboard.revision, member_user_id: memberId, permission: "editor",
  } }));
  dashboard = share.dashboard;
  dashboard = await body(await member.patch(`${memberRoot}/dashboards/${dashboard.id}`, { data: {
    expected_revision: dashboard.revision, name: "Editor-confirmed period dashboard",
    description: "Revision-fenced shared edit",
  } }));
  const revokedDashboard = await body(await owner.delete(
    `${ownerRoot}/dashboards/${dashboard.id}/shares/${memberId}`,
    { data: { expected_revision: dashboard.revision } },
  ));
  dashboard = revokedDashboard.dashboard;
  expect((await member.get(`${memberRoot}/dashboards/${dashboard.id}`)).status()).toBe(404);

  let reportShare = await body(await owner.put(`${ownerRoot}/reports/${report.id}/shares/${memberId}`, { data: {
    member_user_id: memberId, permission: "viewer", expected_share_revision: null,
  } }));
  expect((await member.get(`${memberRoot}/reports/${report.id}`)).status()).toBe(200);
  expect((await member.get(`${memberRoot}/reports/${report.id}/export.pdf?language=ar`)).status()).toBe(200);
  await body(await owner.delete(`${ownerRoot}/reports/${report.id}/shares/${memberId}`, { data: {
    expected_share_revision: reportShare.revision,
  } }));
  expect((await member.get(`${memberRoot}/reports/${report.id}/export.pdf?language=ar`)).status()).toBe(404);

  // Scheduled delivery remains opt-in. A deterministic offline failure becomes
  // retry_pending, then succeeds once; a second poll proves durable deduplication.
  let schedule = await body(await owner.post(`${ownerRoot}/report-schedules`, { data: {
    dashboard_id: dashboard.id, name: "Offline delivery checkpoint", cadence: "daily",
    timezone: "UTC", local_time: "09:00", enabled: true, require_ready_checkpoints: false,
  } }));
  const deliveryConfig = await body(await owner.patch(
    `${ownerRoot}/report-schedules/${schedule.id}/delivery`, { data: {
      expected_schedule_revision: schedule.revision, enabled: true, recipient_user_ids: [memberId],
    } },
  ));
  schedule = deliveryConfig.schedule;
  let dispatched = await body(await control.post("/control/report-scheduler", { data: {
    limit: 5, force_due: true, force_due_slot: 1,
  } }));
  // The same disposable chain intentionally retains the schema-164 recurring
  // schedule, so a forced due slot may also dispatch that compatibility fixture.
  expect(dispatched.schedules.dispatched).toBeGreaterThanOrEqual(1);
  await body(await control.post("/control/report-worker", { data: { limit: 5 } }));
  const reportItems = (await body(await owner.get(`${ownerRoot}/reports?limit=100`))).items;
  const deliveredReport = reportItems.find((item) => item.schedule_id === schedule.id && item.due_slot?.startsWith("2000-01-01"));
  expect(deliveredReport).toBeTruthy();
  let delivery = await body(await control.post("/control/delivery-worker", { data: {
    limit: 5, failure_code: "offline_fixture_retry",
  } }));
  expect(delivery.claimed).toBe(1);
  expect(delivery.results[0].status).toBe("retry_pending");
  expect(delivery.delivered).toEqual([]);
  await body(await control.post("/control/force-delivery-due", { data: { report_id: deliveredReport.id } }));
  delivery = await body(await control.post("/control/delivery-worker", { data: { limit: 5 } }));
  expect(delivery.claimed).toBe(1);
  expect(delivery.results[0].status).toBe("sent");
  expect(delivery.delivered).toHaveLength(1);
  expect(delivery.delivered[0].recipient).toBe("member@example.invalid");
  delivery = await body(await control.post("/control/delivery-worker", { data: { limit: 5 } }));
  expect(delivery.claimed).toBe(0);
  expect(delivery.delivered).toEqual([]);

  // A fresh scheduled report creates a fresh recipient share. Revoke it before
  // delivery and prove the worker records revocation without invoking the adapter.
  dispatched = await body(await control.post("/control/report-scheduler", { data: {
    limit: 5, force_due: true, force_due_slot: 2,
  } }));
  expect(dispatched.schedules.dispatched).toBeGreaterThanOrEqual(1);
  await body(await control.post("/control/report-worker", { data: { limit: 5 } }));
  const afterSecondRun = (await body(await owner.get(`${ownerRoot}/reports?limit=100`))).items;
  const revokedReport = afterSecondRun.find((item) => item.schedule_id === schedule.id && item.due_slot?.startsWith("2000-01-02"));
  expect(revokedReport).toBeTruthy();
  const scheduledShares = await body(await owner.get(`${ownerRoot}/reports/${revokedReport.id}/shares`));
  const recipientShare = scheduledShares.items.find((item) => Number(item.member_user_id) === memberId);
  expect(recipientShare).toBeTruthy();
  await body(await owner.delete(`${ownerRoot}/reports/${revokedReport.id}/shares/${memberId}`, { data: {
    expected_share_revision: recipientShare.revision,
  } }));
  delivery = await body(await control.post("/control/delivery-worker", { data: { limit: 5 } }));
  expect(delivery.delivered).toEqual([]);
  const deliveryHistory = await body(await owner.get(`${ownerRoot}/reports/${revokedReport.id}/deliveries`));
  expect(deliveryHistory.items[0].status).toBe("revoked");
  expect(deliveryHistory.items[0].last_error_code).toBe("recipient_access_revoked");

  // Expiry removes the whole private report directory, including generated
  // PDF/XLSX. Every export route must remain terminally gone and must not regenerate.
  const expired = await body(await control.post("/control/expire-report", { data: { report_id: report.id } }));
  expect(expired.cleanup_jobs).toBe(1);
  const cleanup = await body(await control.post("/control/cleanup-worker", { data: { limit: 5 } }));
  expect(cleanup.results.some((item) => item.status === "completed")).toBe(true);
  for (const suffix of ["export.csv", "export.pdf?language=ar", "export.xlsx?language=ar"]) {
    expect((await owner.get(`${ownerRoot}/reports/${report.id}/${suffix}`)).status()).toBe(410);
  }
  expect((await owner.get(`${ownerRoot}/reports/${report.id}/export.pdf?language=ar`)).status()).toBe(410);

  const compatibility = await body(await control.get("/control/evidence"));
  expect(compatibility.sources.length).toBeGreaterThan(0);
  expect(compatibility.webhook_endpoints.length).toBeGreaterThan(0);
  expect(compatibility.webhook_events.some((item) => item.status === "processed")).toBe(true);
  expect((await owner.get(`${ownerRoot}/report-schedules`)).status()).toBe(200);

  await control.dispose();
  await owner.dispose();
  await member.dispose();
  await crossTenant.dispose();
  await anonymous.dispose();
});
