import './c5-steps-5-9-live.spec.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import http from 'node:http';
import { test, expect, request as playwrightRequest } from '@playwright/test';

const project = process.env.MADAR_E2E_PROJECT_ID;
const root = `/api/users/7001/data/projects/${project}`;
const token = process.env.MADAR_E2E_ACCESS_TOKEN;

async function checked(response) {
  const value = await response.json();
  expect(response.ok(), JSON.stringify(value)).toBe(true);
  return value;
}

async function session(baseURL, accessToken) {
  const bootstrap = await playwrightRequest.newContext({ baseURL,
    extraHTTPHeaders: { Cookie: `madar_access_token=${accessToken}`, Origin: baseURL } });
  const status = await bootstrap.get('/api/auth/user_status');
  const value = await checked(status);
  const csrf = status.headers()['x-csrf-token'] || value.csrf_token;
  await bootstrap.dispose();
  const client = await playwrightRequest.newContext({ baseURL, extraHTTPHeaders: {
    Cookie: `madar_access_token=${accessToken}; madar_csrf_token=${csrf}`,
    Origin: baseURL, 'X-CSRF-Token': csrf,
  } });
  client.phase6Csrf = csrf;
  return client;
}

function slowUpload(baseURL, accessToken, user, projectId, csrf, interrupted = false) {
  return new Promise((resolve, reject) => {
    const boundary = `phase6-${crypto.randomUUID()}`;
    const head = Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="concurrent.csv"\r\nContent-Type: text/csv\r\n\r\n`);
    const tail = Buffer.from(`\r\n--${boundary}--\r\n`);
    const chunk = Buffer.from('1,2\n'.repeat(16384));
    let sent = 0;
    let timer;
    const req = http.request(new URL(`/api/users/${user}/data/projects/${projectId}/datasets/upload`, baseURL), {
      method: 'POST', headers: { Cookie: `madar_access_token=${accessToken}; madar_csrf_token=${csrf}`,
        'X-CSRF-Token': csrf, Origin: baseURL,
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        'Content-Length': head.length + 4 + chunk.length * 32 + tail.length },
    }, response => {
      response.resume();
      response.on('end', () => { clearInterval(timer); resolve(response.statusCode); });
    });
    req.on('error', error => { clearInterval(timer); interrupted ? resolve('interrupted') : reject(error); });
    req.write(head); req.write('a,b\n');
    timer = setInterval(() => {
      if (interrupted && sent === 20) { clearInterval(timer); req.destroy(); return; }
      if (sent++ < 32) req.write(chunk);
      else { clearInterval(timer); req.end(tail); }
    }, 40);
  });
}

test('schema166 multi-worker browser scalability checkpoint', async ({ page, context, baseURL }) => {
  const owner = await session(baseURL, token);
  const cross = await session(baseURL, process.env.MADAR_E2E_CROSS_TENANT_ACCESS_TOKEN);
  const control = await playwrightRequest.newContext({ baseURL: process.env.MADAR_E2E_CONTROL_URL,
    extraHTTPHeaders: { 'x-madar-e2e-control': process.env.MADAR_E2E_CONTROL_TOKEN } });
  const source = process.env.MADAR_E2E_LARGE_CSV;
  expect(fs.statSync(source).size).toBeGreaterThan(240_000_000);
  expect(fs.statSync(source).size).toBeLessThanOrEqual(250_000_000);
  const digest = crypto.createHash('sha256');
  for await (const chunk of fs.createReadStream(source)) digest.update(chunk);
  const expectedHash = digest.digest('hex');
  await context.addCookies([{ name: 'madar_access_token', value: token, url: baseURL,
    httpOnly: true, sameSite: 'Lax' }]);
  await page.goto('/');
  // Browser-native File/FormData transfer: no arrayBuffer or Node request-body
  // copy. This exercises customer cookie/CSRF auth through the Nginx ingress.
  await page.evaluate(() => {
    const input = document.createElement('input'); input.type = 'file'; input.id = 'phase6-file';
    document.body.append(input);
  });
  await page.locator('#phase6-file').setInputFiles(source);
  const measurements = {};
  const persistMeasurements = () => fs.writeFileSync(
    path.join(process.env.MADAR_E2E_SCREENSHOT_DIR, 'phase6-measurements.json'),
    JSON.stringify({ source_bytes: fs.statSync(source).size, source_sha256: expectedHash, ...measurements }, null, 2));
  let started = Date.now();
  const uploaded = await page.evaluate(async uploadRoot => {
    const status = await fetch('/api/auth/user_status', { credentials: 'include' });
    const auth = await status.json();
    const csrf = status.headers.get('x-csrf-token') || auth.csrf_token;
    const form = new FormData(); form.append('file', document.querySelector('#phase6-file').files[0]);
    const response = await fetch(`${uploadRoot}/datasets/upload`, { method: 'POST',
      credentials: 'include', headers: { 'X-CSRF-Token': csrf }, body: form });
    return { status: response.status, body: await response.json() };
  }, root);
  measurements.upload_seconds = (Date.now() - started) / 1000;
  persistMeasurements();
  expect(uploaded.status, JSON.stringify(uploaded.body)).toBe(201);
  const dataset = uploaded.body.persistent_dataset_id;
  const version = uploaded.body.dataset_version_id;
  expect(uploaded.body.rows).toBe(5_300_000);
  const versions = await checked(await owner.get(`${root}/datasets/${dataset}/versions`));
  expect(versions.items.find(item => item.id === version).content_hash).toBe(expectedHash);
  const fault = async action => checked(await control.post('/control/scalability', {
    data: { dataset_id: dataset, version_id: version, action },
  }));
  expect((await fault('evidence')).source_sha256).toBe(expectedHash);
  const denied = await cross.post(`/api/users/7002/data/projects/${project}/datasets/${dataset}/versions/${version}/explore`, {
    data: { columns: ['row_id'], limit: 5, offset: 0 },
  });
  expect(denied.status()).toBe(404);
  const query = { columns: ['row_id', 'group_key', 'amount'],
    filters: [{ field: 'group_key', operator: 'eq', value: 'g099' }],
    sort: [{ field: 'amount', direction: 'desc' }], limit: 100, offset: 100 };
  started = Date.now();
  const first = await checked(await owner.post(`${root}/datasets/${dataset}/versions/${version}/explore`, { data: query }));
  measurements.first_explore_seconds = (Date.now() - started) / 1000;
  expect(first.pagination.total).toBe(53000);
  started = Date.now();
  const repeated = await Promise.all(Array.from({ length: 4 }, () => owner.post(
    `${root}/datasets/${dataset}/versions/${version}/explore`, { data: query })));
  measurements.concurrent_explore_seconds = (Date.now() - started) / 1000;
  measurements.concurrent_explore_statuses = repeated.map(response => response.status());
  persistMeasurements();
  for (const response of repeated) {
    if (response.ok()) expect(await response.json()).toEqual(first);
    else expect(response.status()).toBe(429);
  }
  expect((await fault('evidence')).artifacts).toBe(1);
  expect(await fault('disk-refusal')).toEqual({ status: 507, body_reads: 0 });
  for (const action of ['corrupt', 'symlink']) {
    await fault(action);
    const recovered = await checked(await owner.post(`${root}/datasets/${dataset}/versions/${version}/explore`, { data: query }));
    expect(recovered).toEqual(first);
    expect((await fault('evidence')).source_sha256).toBe(expectedHash);
  }

  let dashboard = await checked(await owner.post(`${root}/dashboards`, { data: {
    name: 'Phase6 near-250MB', description: 'Disposable scalability checkpoint' } }));
  const mutation = await checked(await owner.post(`${root}/dashboards/${dashboard.id}/widgets`, { data: {
    expected_revision: dashboard.revision, widget_type: 'kpi', title: 'Exact large rows',
    dataset_id: dataset, dataset_version_id: version, version_policy: 'pinned',
    analysis_spec: { operation: 'count' }, layout_config: {}, display_options: {},
  } }));
  dashboard = mutation.dashboard;
  started = Date.now();
  const execution = await checked(await owner.post(`${root}/dashboards/${dashboard.id}/widgets/${mutation.widget.id}/execute`, {
    data: { refresh_latest: false, language: 'en' },
  }));
  measurements.dashboard_seconds = (Date.now() - started) / 1000;
  expect(execution.status).toBe('ready');
  expect(execution.result.kpis[0].value).toBe(5_300_000);
  expect(execution.provenance.content_hash).toBe(expectedHash);
  const queued = await checked(await owner.post(`${root}/reports`, { data: {
    dashboard_id: dashboard.id, idempotency_key: `phase6-${crypto.randomUUID()}` } }));
  started = Date.now();
  await checked(await control.post('/control/report-worker', { data: { limit: 5 } }));
  measurements.report_worker_seconds = (Date.now() - started) / 1000;
  const report = await checked(await owner.get(`${root}/reports/${queued.id}`));
  expect(report.status).toBe('completed');
  expect(report.result_snapshot.widgets[0].result).toEqual(execution.result);
  expect(report.version_vector[0].content_hash).toBe(expectedHash);
  for (const format of ['pdf', 'xlsx']) {
    started = Date.now();
    const response = await owner.get(`${root}/reports/${queued.id}/export.${format}`);
    expect(response.status()).toBe(200);
    expect((await response.body()).subarray(0, format === 'pdf' ? 5 : 2).toString())
      .toBe(format === 'pdf' ? '%PDF-' : 'PK');
    measurements[`${format}_seconds`] = (Date.now() - started) / 1000;
  }
  persistMeasurements();
  const bigDate = await checked(await owner.post(`${root}/dashboards/${dashboard.id}/widgets`, { data: {
    expected_revision: dashboard.revision, widget_type: 'table', title: 'Honest date refusal',
    dataset_id: dataset, dataset_version_id: version, version_policy: 'pinned',
    analysis_spec: { operation: 'date_aggregate', date_column: 'event_date', aggregation: 'count',
      period: 'month', timezone: 'America/New_York' }, layout_config: {}, display_options: {},
  } }));
  const unsupported = await checked(await owner.post(`${root}/dashboards/${dashboard.id}/widgets/${bigDate.widget.id}/execute`, {
    data: { refresh_latest: false, language: 'en' } }));
  expect(unsupported.status).toBe('needs_attention');
  expect(unsupported.reason).toBe('analysis_not_supported');

  const dateDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'madar-phase6-dates-'));
  try {
    const datePath = path.join(dateDirectory, 'dates.csv');
    const pattern = '2026-03-08T07:30:00Z,1\n2026-11-01T06:30:00Z,2\nbad,3\n,4\n';
    fs.writeFileSync(datePath, 'event_date,amount\n' + pattern.repeat(25000) + '2026-03-08T07:30:00Z,1\n');
    const dateUpload = await checked(await owner.post(`${root}/datasets/upload`, {
      multipart: { file: fs.createReadStream(datePath) },
    }));
    expect(dateUpload.rows).toBe(100001);
    let dateDashboard = await checked(await owner.post(`${root}/dashboards`, { data: {
      name: 'Phase6 supported dates', description: 'Cold CSV date worker' } }));
    const dateMutation = await checked(await owner.post(`${root}/dashboards/${dateDashboard.id}/widgets`, { data: {
      expected_revision: dateDashboard.revision, widget_type: 'table', title: 'Supported DST counts',
      dataset_id: dateUpload.persistent_dataset_id, dataset_version_id: dateUpload.dataset_version_id,
      version_policy: 'pinned', analysis_spec: { operation: 'date_aggregate', date_column: 'event_date',
        aggregation: 'count', period: 'month', timezone: 'America/New_York',
        start_date: '2026-03-08', end_date: '2026-11-01' }, layout_config: {}, display_options: {},
    } }));
    dateDashboard = dateMutation.dashboard;
    const dateExecuted = await checked(await owner.post(`${root}/dashboards/${dateDashboard.id}/widgets/${dateMutation.widget.id}/execute`, {
      data: { refresh_latest: false, language: 'en' } }));
    expect(dateExecuted.status).toBe('ready');
    expect(dateExecuted.result.metadata.mappings_used).toMatchObject({
      missing_date_count: 25000, invalid_date_count: 25000, selected_row_count: 50001,
      timezone: 'America/New_York',
    });
    const dateRun = await checked(await owner.post(`${root}/reports`, { data: {
      dashboard_id: dateDashboard.id, idempotency_key: `phase6-date-${crypto.randomUUID()}` } }));
    await checked(await control.post('/control/report-worker', { data: { limit: 5 } }));
    const dateReport = await checked(await owner.get(`${root}/reports/${dateRun.id}`));
    expect(dateReport.status).toBe('completed');
    expect(dateReport.result_snapshot.widgets[0].result).toEqual(dateExecuted.result);
    measurements.supported_date_rows = 100001;
    persistMeasurements();
  } finally {
    fs.rmSync(dateDirectory, { recursive: true });
  }

  const concurrent = await Promise.all(Array.from({ length: 6 }, (_, index) => slowUpload(baseURL,
    index % 2 ? process.env.MADAR_E2E_CROSS_TENANT_ACCESS_TOKEN : token,
    index % 2 ? 7002 : 7001,
    index % 2 ? process.env.MADAR_E2E_CROSS_TENANT_PROJECT_ID : project,
    index % 2 ? cross.phase6Csrf : owner.phase6Csrf)));
  measurements.concurrent_upload_statuses = concurrent;
  persistMeasurements();
  expect(concurrent).toContain(201);
  expect(concurrent).toContain(429);
  expect(await slowUpload(baseURL, token, 7001, project, owner.phase6Csrf, true)).toBe('interrupted');
  expect((await fault('evidence')).partials).toBe(0);
  await page.evaluate(selected => window.sessionStorage.setItem(
    'madar:selected-data-project:7001:7001', selected), project);
  await page.goto(`/business-intelligence/projects/${project}/data`);
  await page.locator('#bi-dashboard-panel-tab').click();
  await page.locator('#bi-dashboard-panel select').first().selectOption(dashboard.id);
  await expect(page.getByRole('heading', { name: 'Exact large rows' })).toBeVisible();
  await page.screenshot({ path: path.join(process.env.MADAR_E2E_SCREENSHOT_DIR, 'phase6-large-dashboard.png') });
  await page.goto(`/builder-data/projects/${project}/data`);
  await expect(page.locator('.daw-stepper button')).toHaveCount(5);
  measurements.data_logs_steps = await page.locator('.daw-stepper button strong').allTextContents();
  await expect(page.locator('.bi-tabs')).toHaveCount(0);
  fs.writeFileSync(path.join(process.env.MADAR_E2E_SCREENSHOT_DIR, 'phase6-measurements.json'),
    JSON.stringify({ source_bytes: fs.statSync(source).size, source_sha256: expectedHash, ...measurements }, null, 2));
  console.log('PHASE6_MEASUREMENTS', JSON.stringify(measurements));
  await owner.dispose(); await cross.dispose(); await control.dispose();
});
