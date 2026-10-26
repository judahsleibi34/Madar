import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { test, expect, request as playwrightRequest } from "@playwright/test";

const projectId = process.env.MADAR_E2E_PROJECT_ID;
const crossTenantProjectId = process.env.MADAR_E2E_CROSS_TENANT_PROJECT_ID;
const accessToken = process.env.MADAR_E2E_ACCESS_TOKEN;
const controlUrl = process.env.MADAR_E2E_CONTROL_URL;
const controlToken = process.env.MADAR_E2E_CONTROL_TOKEN;
const screenshotDir = process.env.MADAR_E2E_SCREENSHOT_DIR;
const userId = 7001;

async function control(endpoint, payload) {
  const hasPayload = payload !== undefined;
  const response = await fetch(`${controlUrl}${endpoint}`, {
    method: hasPayload ? "POST" : "GET",
    headers: {
      "X-Madar-E2E-Control": controlToken,
      ...(hasPayload ? { "Content-Type": "application/json" } : {}),
    },
    ...(hasPayload ? { body: JSON.stringify(payload) } : {}),
  });
  const body = await response.json();
  expect(response.ok, JSON.stringify(body)).toBe(true);
  return body;
}

function signed(body, secret, eventId, timestamp = Math.floor(Date.now() / 1000)) {
  const signature = crypto.createHmac("sha256", secret).update(`${timestamp}.${body}`).digest("hex");
  return {
    "Content-Type": "application/json",
    "X-Madar-Timestamp": String(timestamp),
    "X-Madar-Event-Id": eventId,
    "X-Madar-Signature": `v1=${signature}`,
  };
}

test("signed webhook reaches durable history, checkpoint, and browser status", async ({ page, context, baseURL }) => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  await context.addCookies([{
    name: "madar_access_token", value: accessToken,
    url: baseURL, httpOnly: true, sameSite: "Lax",
  }]);
  const api = await playwrightRequest.newContext({ baseURL });
  const authenticatedApi = await playwrightRequest.newContext({
    baseURL, extraHTTPHeaders: { Cookie: `madar_access_token=${accessToken}` },
  });
  let sourceId = "";
  let provisioned;
  page.on("response", async response => {
    const pathname = new URL(response.url()).pathname;
    if (response.request().method() === "POST" && /\/data\/projects\/[^/]+\/sources$/.test(pathname)) {
      try { sourceId = (await response.json()).id || sourceId; } catch {}
    }
    if (response.request().method() === "POST" && pathname.endsWith("/webhook")) {
      try { provisioned = await response.json(); } catch {}
    }
  });

  const capabilitiesResponse = await authenticatedApi.get(
    `/api/users/${userId}/data/projects/${projectId}/source-capabilities`
  );
  const capabilities = await capabilitiesResponse.json();
  expect(capabilitiesResponse.ok(), JSON.stringify(capabilities)).toBe(true);
  expect(capabilities.webhook_ingestion_available).toBe(true);
  expect(capabilities.providers).toEqual(expect.arrayContaining([
    expect.objectContaining({ key: "webhook_fixture" }),
  ]));

  await page.goto("/data-sources");
  const chooser = page.getByRole("dialog", { name: "Choose a data project" });
  await chooser.getByRole("button", { name: "My Projects" }).click();
  await page.getByRole("button", { name: "Browser API project" }).click();
  await page.getByRole("button", { name: /Approved API connection/ }).click();
  await page.getByPlaceholder("Example: Monthly sales uploads").fill("Signed webhook records");
  await page.getByLabel("Provider").selectOption("webhook_fixture");
  await expect(page.getByLabel("Resource type")).toHaveValue("records");
  await page.getByRole("button", { name: "Add API source" }).click();
  await expect(page.getByRole("heading", { name: "Signed webhook records" })).toBeVisible();
  expect(sourceId).toMatch(/^[0-9a-f-]{36}$/);

  await page.getByRole("button", { name: "Provision webhook" }).click();
  await expect(page.getByText("One-time verification secret")).toBeVisible();
  expect(provisioned?.one_time_secret).toBeTruthy();
  expect(provisioned?.ingress_path).toMatch(/^\/data\/webhooks\/[0-9a-f-]{36}$/);
  const secret = provisioned.one_time_secret;
  const ingress = `/api${provisioned.ingress_path}`;
  await expect(page.locator(".daw-webhook-secret code")).toHaveText(secret);
  await page.getByRole("button", { name: "Enable endpoint" }).click();
  await expect(page.getByText("The webhook endpoint is enabled.")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "webhook-01-enabled.png"), fullPage: true });

  const firstBody = JSON.stringify({
    event_type: "record.upsert", resource: "records",
    record: { id: "A", version: 1, data: { name: "Alpha", amount: 10 } },
  });
  const invalid = await api.post(ingress, {
    data: Buffer.from(firstBody),
    headers: { ...signed(firstBody, "wrong-secret", "evt-invalid-signature-0001") },
  });
  expect(invalid.status()).toBe(401);
  const tampered = await api.post(ingress, {
    data: Buffer.from(firstBody.replace("Alpha", "Tampered")),
    headers: signed(firstBody, secret, "evt-tampered-payload-0001"),
  });
  expect(tampered.status()).toBe(401);
  const unknownEndpoint = await api.post("/api/data/webhooks/00000000-0000-4000-8000-000000000099", {
    data: Buffer.from(firstBody), headers: signed(firstBody, secret, "evt-unknown-endpoint-0001"),
  });
  expect(unknownEndpoint.status()).toBe(404);
  const expired = await api.post(ingress, {
    data: Buffer.from(firstBody),
    headers: signed(firstBody, secret, "evt-expired-timestamp-0001", Math.floor(Date.now() / 1000) - 600),
  });
  expect(expired.status()).toBe(401);
  const malformed = await api.post(ingress, {
    data: Buffer.from("{not-json"), headers: signed("{not-json", secret, "evt-malformed-json-0001"),
  });
  expect(malformed.status()).toBe(422);
  const deletionBody = JSON.stringify({ event_type: "record.deleted", resource: "records" });
  const deletion = await api.post(ingress, {
    data: Buffer.from(deletionBody), headers: signed(deletionBody, secret, "evt-unsupported-delete-0001"),
  });
  expect(deletion.status()).toBe(422);
  const wrongResourceBody = JSON.stringify({
    event_type: "record.upsert", resource: "other",
    record: { id: "A", version: 1, data: { amount: 999 } },
  });
  const wrongResource = await api.post(ingress, {
    data: Buffer.from(wrongResourceBody),
    headers: signed(wrongResourceBody, secret, "evt-wrong-resource-0001"),
  });
  expect(wrongResource.status()).toBe(422);
  const malformedRecordBody = JSON.stringify({
    event_type: "record.upsert", resource: "records", record: { version: 1, data: {} },
  });
  const malformedRecord = await api.post(ingress, {
    data: Buffer.from(malformedRecordBody),
    headers: signed(malformedRecordBody, secret, "evt-malformed-record-0001"),
  });
  expect(malformedRecord.status()).toBe(422);
  const oversizedBody = JSON.stringify({ value: "x".repeat(70 * 1024) });
  const oversized = await api.post(ingress, {
    data: Buffer.from(oversizedBody), headers: signed(oversizedBody, secret, "evt-oversized-payload-0001"),
  });
  expect(oversized.status()).toBe(413);

  await page.getByRole("button", { name: "Disable endpoint" }).click();
  await expect(page.getByText("The webhook endpoint is disabled.")).toBeVisible();
  const disabledDelivery = await api.post(ingress, {
    data: Buffer.from(firstBody), headers: signed(firstBody, secret, "evt-disabled-endpoint-0001"),
  });
  expect(disabledDelivery.status()).toBe(404);
  await page.getByRole("button", { name: "Enable endpoint" }).click();
  await expect(page.getByText("The webhook endpoint is enabled.")).toBeVisible();

  const accepted = await api.post(ingress, {
    data: Buffer.from(firstBody), headers: signed(firstBody, secret, "evt-authoritative-A-0001"),
  });
  expect(accepted.status()).toBe(202);
  expect(await accepted.json()).toMatchObject({ accepted: true, disposition: "accepted" });
  const duplicate = await api.post(ingress, {
    data: Buffer.from(firstBody), headers: signed(firstBody, secret, "evt-authoritative-A-0001"),
  });
  expect(duplicate.status()).toBe(200);
  expect(await duplicate.json()).toMatchObject({ accepted: true, disposition: "duplicate" });

  const worker = await control("/control/webhook-worker", { limit: 20 });
  expect(worker.process).toBe("run_webhook_ingestion_worker.py");
  expect(worker.claimed).toBe(1);
  expect(worker.results[0]).toMatchObject({ outcome: "processed", committed_revision: 1 });
  const checkpoint = await control("/control/checkpoint-worker", { limit: 20 });
  expect(checkpoint.process).toBe("run_dataset_checkpoint_worker.py");
  expect(checkpoint.claimed).toBeGreaterThanOrEqual(1);
  expect(checkpoint.results.every(item => item.outcome === "ready")).toBe(true);

  const newerBody = JSON.stringify({
    event_type: "record.upsert", resource: "records",
    record: { id: "A", version: 2, data: { name: "Alpha", amount: 25 } },
  });
  const olderBody = JSON.stringify({
    event_type: "record.upsert", resource: "records",
    record: { id: "A", version: 0, data: { name: "Old", amount: 1 } },
  });
  const otherBody = JSON.stringify({
    event_type: "record.upsert", resource: "records",
    record: { id: "B", version: 1, data: { name: "Beta", amount: 40 } },
  });
  for (const [body, eventId] of [
    [newerBody, "evt-authoritative-A-0002"],
    [olderBody, "evt-authoritative-A-older"],
  ]) {
    const response = await api.post(ingress, { data: Buffer.from(body), headers: signed(body, secret, eventId) });
    expect(response.status()).toBe(202);
  }
  const concurrent = await Promise.all(Array.from({ length: 6 }, () => api.post(ingress, {
    data: Buffer.from(otherBody), headers: signed(otherBody, secret, "evt-concurrent-B-0001"),
  })));
  expect(concurrent.every(response => [200, 202].includes(response.status()))).toBe(true);
  const workers = await Promise.all([
    control("/control/webhook-worker", { limit: 20 }),
    control("/control/webhook-worker", { limit: 20 }),
  ]);
  expect(workers.reduce((sum, item) => sum + item.claimed, 0)).toBe(3);
  await control("/control/checkpoint-worker", { limit: 20 });

  const notificationBody = JSON.stringify({
    event_type: "resource.changed", resource: "records", notification: { reason: "fixture" },
  });
  for (const eventId of ["evt-notification-0001", "evt-notification-0002"]) {
    const notification = await api.post(ingress, {
      data: Buffer.from(notificationBody), headers: signed(notificationBody, secret, eventId),
    });
    expect(notification.status()).toBe(202);
  }
  const notificationWorker = await control("/control/webhook-worker", { limit: 20 });
  expect(notificationWorker.claimed).toBe(2);
  expect(notificationWorker.results.every(item => item.outcome === "reconciliation_scheduled")).toBe(true);

  await page.reload();
  await expect(page.getByText("enabled", { exact: true })).toBeVisible();
  await expect(page.getByText("Never", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Ready for the latest revision")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "webhook-02-processed.png"), fullPage: true });

  const evidence = await control("/control/evidence");
  const webhookEvents = evidence.webhook_events.filter(item => item.source_id === sourceId);
  expect(webhookEvents.filter(item => item.provider_event_id === "evt-concurrent-B-0001")).toHaveLength(1);
  expect(webhookEvents.every(item => item.status === "processed")).toBe(true);
  const resource = evidence.resources.find(item => item.source_id === sourceId);
  expect(resource.committed_revision).toBe(3);
  const records = Object.fromEntries(evidence.current_records
    .filter(item => item.dataset_id === resource.dataset_id)
    .map(item => [item.source_record_id, item]));
  expect(records.A.payload.amount).toBe(25);
  expect(records.A.source_order).toBe(2);
  expect(records.B.payload.amount).toBe(40);
  expect(records.B.source_order).toBe(1);
  expect(evidence.versions.filter(item => item.dataset_id === resource.dataset_id)).toHaveLength(3);
  expect(evidence.checkpoints.some(item => (
    item.dataset_id === resource.dataset_id && item.target_revision === 3 && item.status === "ready"
  ))).toBe(true);
  expect(resource.reconciliation_reason).toBe("webhook_notification");
  expect(resource.reconciliation_requested_at).toBeTruthy();
  const revisionOne = await control("/control/reconstruct-revision", {
    source_id: sourceId, target_revision: 1,
  });
  const revisionThree = await control("/control/reconstruct-revision", {
    source_id: sourceId, target_revision: 3,
  });
  expect(revisionOne).toMatchObject({ target_revision: 1, record_count: 1, change_count: 1 });
  expect(revisionThree).toMatchObject({ target_revision: 3, record_count: 2 });
  expect(revisionOne.state_hash).not.toBe(revisionThree.state_hash);
  expect(revisionThree.immutable_bytes_read).toBeGreaterThan(0);

  const recoveredBody = JSON.stringify({
    event_type: "record.upsert", resource: "records",
    record: { id: "C", version: 1, data: { name: "Crash recovered", amount: 60 } },
  });
  expect((await api.post(ingress, {
    data: Buffer.from(recoveredBody), headers: signed(recoveredBody, secret, "evt-crash-recovery-0001"),
  })).status()).toBe(202);
  const crashed = await control("/control/crash-webhook-worker", {});
  expect(crashed).toMatchObject({ claimed: 1, child_exited: true, lease_fence: 1 });
  const recoveredLease = await control("/control/recover-webhook-leases", {});
  expect(recoveredLease).toMatchObject({ expired: 1, reconciled: 1, retry_due: 1 });
  const retryEvidence = await control("/control/evidence");
  expect(retryEvidence.webhook_events.find(item => item.id === crashed.event_id)).toMatchObject({
    status: "retry", attempts: 1, error_category: "worker_lease_expired",
  });
  await page.reload();
  await page.screenshot({ path: path.join(screenshotDir, "webhook-03-retry-visible.png"), fullPage: true });
  const recoveredWorker = await control("/control/webhook-worker", { limit: 20 });
  expect(recoveredWorker.claimed).toBe(1);
  expect(recoveredWorker.results[0]).toMatchObject({ outcome: "processed", committed_revision: 4 });
  expect(await control("/control/stale-webhook-complete", { event_id: crashed.event_id })).toMatchObject({
    completed: false,
  });
  await control("/control/checkpoint-worker", { limit: 20 });

  const rotatedOutBody = JSON.stringify({
    event_type: "record.upsert", resource: "records",
    record: { id: "D", version: 1, data: { name: "Rotated out", amount: 70 } },
  });
  expect((await api.post(ingress, {
    data: Buffer.from(rotatedOutBody), headers: signed(rotatedOutBody, secret, "evt-rotation-fenced-0001"),
  })).status()).toBe(202);
  const rotationClaim = await control("/control/crash-webhook-worker", {});
  expect(rotationClaim.claimed).toBe(1);
  const rotateResponse = page.waitForResponse(response => (
    response.request().method() === "POST" && response.url().endsWith("/webhook")
  ));
  await page.getByRole("button", { name: "Rotate secret" }).click();
  const rotated = await (await rotateResponse).json();
  expect(rotated.one_time_secret).toBeTruthy();
  const rotatedSecret = rotated.one_time_secret;
  await expect(page.locator(".daw-webhook-secret code")).toHaveText(rotatedSecret);
  expect((await api.post(ingress, {
    data: Buffer.from(rotatedOutBody),
    headers: signed(rotatedOutBody, rotatedSecret, "evt-disabled-after-rotation-0001"),
  })).status()).toBe(404);
  expect(await control("/control/stale-webhook-complete", { event_id: rotationClaim.event_id })).toMatchObject({
    completed: false,
  });
  const rotationRecovery = await control("/control/recover-webhook-leases", {});
  expect(rotationRecovery).toMatchObject({ expired: 1, reconciled: 1, retry_due: 0 });
  await page.getByRole("button", { name: "Enable endpoint" }).click();
  await expect(page.getByText("The webhook endpoint is enabled.")).toBeVisible();
  expect((await api.post(ingress, {
    data: Buffer.from(rotatedOutBody), headers: signed(rotatedOutBody, secret, "evt-old-secret-0001"),
  })).status()).toBe(401);
  const rotatedBody = JSON.stringify({
    event_type: "record.upsert", resource: "records",
    record: { id: "D", version: 2, data: { name: "Rotated credential", amount: 80 } },
  });
  expect((await api.post(ingress, {
    data: Buffer.from(rotatedBody), headers: signed(rotatedBody, rotatedSecret, "evt-rotated-secret-0001"),
  })).status()).toBe(202);
  const rotatedWorker = await control("/control/webhook-worker", { limit: 20 });
  expect(rotatedWorker.results[0]).toMatchObject({ outcome: "processed", committed_revision: 5 });
  await control("/control/checkpoint-worker", { limit: 20 });

  expect((await authenticatedApi.get(
    `/api/users/7002/data/projects/${projectId}/sources/${sourceId}/webhook`
  )).status()).toBe(403);
  expect((await authenticatedApi.get(
    `/api/users/${userId}/data/projects/${crossTenantProjectId}/sources/${sourceId}/webhook`
  )).status()).toBe(404);

  const revokedDuringProcessingBody = JSON.stringify({
    event_type: "record.upsert", resource: "records",
    record: { id: "E", version: 1, data: { name: "Revoked", amount: 90 } },
  });
  expect((await api.post(ingress, {
    data: Buffer.from(revokedDuringProcessingBody),
    headers: signed(revokedDuringProcessingBody, rotatedSecret, "evt-revocation-fenced-0001"),
  })).status()).toBe(202);
  const revocationClaim = await control("/control/crash-webhook-worker", {});
  expect(revocationClaim.claimed).toBe(1);
  const revokeResponse = page.waitForResponse(response => (
    response.request().method() === "POST" && response.url().endsWith("/webhook/revoke")
  ));
  await page.getByRole("button", { name: "Revoke webhook" }).click();
  expect((await revokeResponse).status()).toBe(200);
  expect(await control("/control/stale-webhook-complete", { event_id: revocationClaim.event_id })).toMatchObject({
    completed: false,
  });
  expect(await control("/control/recover-webhook-leases", {})).toMatchObject({
    expired: 1, reconciled: 1, retry_due: 0,
  });
  const revokedDelivery = await api.post(ingress, {
    data: Buffer.from(newerBody), headers: signed(newerBody, rotatedSecret, "evt-after-revocation-0001"),
  });
  expect(revokedDelivery.status()).toBe(404);
  await page.reload();
  await expect(page.getByText("revoked", { exact: true })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "webhook-04-revoked.png"), fullPage: true });

  const finalEvidence = await control("/control/evidence");
  const finalEvents = finalEvidence.webhook_events.filter(item => item.source_id === sourceId);
  expect(finalEvents.find(item => item.provider_event_id === "evt-crash-recovery-0001")).toMatchObject({
    status: "processed", attempts: 2, result_revision: 4,
  });
  expect(finalEvents.find(item => item.provider_event_id === "evt-rotation-fenced-0001")).toMatchObject({
    status: "dead_letter", error_category: "webhook_endpoint_fenced",
  });
  expect(finalEvents.find(item => item.provider_event_id === "evt-revocation-fenced-0001")).toMatchObject({
    status: "dead_letter", error_category: "webhook_endpoint_fenced",
  });
  const finalResource = finalEvidence.resources.find(item => item.source_id === sourceId);
  expect(finalResource.committed_revision).toBe(5);
  const finalRecords = Object.fromEntries(finalEvidence.current_records
    .filter(item => item.dataset_id === finalResource.dataset_id)
    .map(item => [item.source_record_id, item]));
  expect(finalRecords.C.payload.amount).toBe(60);
  expect(finalRecords.D.payload.amount).toBe(80);
  expect(finalRecords.E).toBeUndefined();
  expect(finalEvidence.versions.filter(item => item.dataset_id === finalResource.dataset_id)).toHaveLength(5);

  await api.dispose();
  await authenticatedApi.dispose();
});
