import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const dist = path.join(root, "dist");
const html = readFileSync(path.join(dist, "index.html"), "utf8");
const manifest = JSON.parse(readFileSync(path.join(dist, ".vite/manifest.json"), "utf8"));

const entry = manifest["index.html"];
assert.ok(entry?.isEntry, "Missing HTML application entry");
assert.ok(entry.dynamicImports?.includes("src/tenantMain.jsx"), "Hosted tenant entry is not route selected");
assert.ok(entry.dynamicImports?.includes("src/appMain.jsx"), "Main application entry is missing");

const preloadCount = (html.match(/rel="modulepreload"/g) || []).length;
assert.ok(preloadCount <= 5, `Universal module preloads exceeded budget: ${preloadCount}`);
assert.ok(!html.includes("form-flow-pilates-loading.jpg"), "Standalone form image is globally preloaded");

function staticGraph(key, visited = new Set()) {
  if (visited.has(key)) return visited;
  const chunk = manifest[key];
  assert.ok(chunk, `Missing manifest chunk: ${key}`);
  visited.add(key);
  for (const dependency of chunk.imports || []) staticGraph(dependency, visited);
  return visited;
}

const tenantGraph = staticGraph("src/tenantMain.jsx");
const runtimeGraph = staticGraph("src/components/PageBuilder/runtime/TenantSiteRuntime.jsx");
const publicGraph = new Set([...tenantGraph, ...runtimeGraph]);
for (const key of publicGraph) {
  const chunk = manifest[key];
  const label = `${key} ${chunk.name || ""} ${chunk.file || ""}`;
  assert.doesNotMatch(label, /appMain|AdminRoutes|PageBuilder\.api|src\/components\/PageBuilder\/index|assets\/PageBuilder-[\w-]+\.js|vendor-three|OrbitVisual|EcommerceStorefront|CountUpText|assets\/proxy-/,
    `Route-irrelevant code entered hosted public graph: ${label}`);
}

const publicIcons = Object.values(manifest).find((chunk) => chunk.name === "public-icons");
assert.ok(publicIcons, "Bounded public icon chunk is missing");
assert.ok([...publicGraph].some((key) => manifest[key].file === publicIcons.file),
  "Public icon chunk is not present in the hosted tenant graph");
assert.ok(statSync(path.join(dist, publicIcons.file)).size <= 30_000,
  "Public icon chunk exceeded its 30 KB uncompressed budget");

const tenantCss = [...tenantGraph, ...runtimeGraph].flatMap((key) => manifest[key].css || []);
const uniqueCss = [...new Set(tenantCss)];
const cssBytes = uniqueCss.reduce((total, file) => total + statSync(path.join(dist, file)).size, 0);
assert.ok(cssBytes <= 650_000, `Hosted published renderer CSS exceeded budget: ${cssBytes} bytes`);

console.log(`Tenant bundle audit passed: ${preloadCount} universal preloads; ${tenantGraph.size} entry chunks; ${runtimeGraph.size} renderer chunks; ${cssBytes} public CSS bytes.`);
