// Native IndexedDB checks in a fresh disposable browser context; no app/provider access.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "@playwright/test";

const source = await fs.readFile(new URL(
  "../src/components/PageBuilder/DataAnalysisWorkspace/utils/datasetStorage.js", import.meta.url), "utf8");
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const context = await browser.newContext();
  // Fulfill both requests locally. No process listens at this fixture origin.
  const origin = "http://127.0.0.1:61337";
  await context.route(`${origin}/**`, route => route.fulfill({
    status: 200, contentType: route.request().url().endsWith("storage.js") ? "text/javascript" : "text/html",
    body: route.request().url().endsWith("storage.js") ? source : "<!doctype html><title>Disposable archive</title>",
  }));
  const page = await context.newPage();
  await page.goto(`${origin}/fixture`);
  const result = await page.evaluate(async () => {
    const storage = await import("/storage.js");
    const actor = { tenant_id: "tenant-a", id: "user-7" };
    const scope = storage.getProjectArchiveScope(actor, "project-a");
    const other = storage.getProjectArchiveScope({ ...actor, tenant_id: "tenant-b" }, "project-a");
    const csv = "item,amount\napple,3\n";
    await storage.archiveItem({ id: "data", type: "loaded_dataset", scope,
      payload: { loadedDataframe: { csv }, file: new File([csv], "data.csv", { type: "text/csv" }) } });
    await storage.archiveItem({ id: "chart", type: "chart", scope, payload: { url: "/private/chart.png", plotConfig: { chartType: "bar" } } });
    const report = { report: { title: "Recoverable draft" }, blocks: [{ id: "b1", type: "text", body: "Original content" }] };
    await storage.archiveItem({ id: "report", type: "report", scope, payload: report });
    await storage.archiveItem({ id: "report", type: "report", scope: other, payload: { report: { title: "Other tenant" } } });
    await storage.saveDataset(new File([csv], "current.csv"), { scope });
    await storage.clearDataset({ scope });
    const items = await storage.listArchiveItems({ scope });
    const data = items.find(item => item.id === "data");
    const draft = items.find(item => item.id === "report");
    // Reopen from actual content, without deleting the archived copy.
    await storage.saveDataset(data.payload.file, { scope });
    const reopened = await storage.loadDataset({ scope });
    const retained = await storage.listArchiveItems({ scope });
    // Existing tab reads the tenant/user scope exactly, not project descendants.
    const tabItems = await storage.listArchiveItems({ scope: storage.getTenantUserArchiveScope(actor) });
    await storage.deleteArchiveItem("report", { scope });
    const after = await storage.listArchiveItems({ scope });
    const foreign = await storage.listArchiveItems({ scope: other });
    return {
      count: items.length, csv: data.payload.loadedDataframe.csv,
      fileContent: await data.payload.file.text(), reopened: await reopened.text(),
      report: draft.payload, retained: retained.length,
      chartHasInlineImage: Boolean(items.find(item => item.id === "chart").payload.blob),
      tabCount: tabItems.length, afterIds: after.map(item => item.id).sort(),
      foreignTitle: foreign[0].payload.report.title,
      unscoped: await storage.listArchiveItems(),
    };
  });
  assert.equal(result.count, 3);
  assert.equal(result.csv, "item,amount\napple,3\n");
  assert.equal(result.fileContent, result.csv);
  assert.equal(result.reopened, result.csv);
  assert.deepEqual(result.report, { report: { title: "Recoverable draft" }, blocks: [{ id: "b1", type: "text", body: "Original content" }] });
  assert.equal(result.retained, 3);
  assert.equal(result.chartHasInlineImage, false);
  assert.equal(result.tabCount, 0); // Confirmed visibility gap, not a new contract.
  assert.deepEqual(result.afterIds, ["chart", "data"]);
  assert.equal(result.foreignTitle, "Other tenant");
  assert.deepEqual(result.unscoped, []);
  // Context destruction is fixture cleanup, never an application erasure claim.
  await context.close();
  process.stdout.write(JSON.stringify({ verdict: "PASS", native_indexeddb: true,
    content_retained: true, scoped_removal: true, project_items_visible_in_global_tab: false,
    server_permanent_erasure_verified: false }) + "\n");
} finally {
  await browser.close();
}
