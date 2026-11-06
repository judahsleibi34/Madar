import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { sha256 } from "../e2e/academy-visual-contract.mjs";
import { reconcile, verifyEvidence, writeReport } from "./reconcile-academy-visual-review.mjs";

const writerPath = process.env.MADAR_ATOMIC_EVIDENCE_WRITER;
const root = mkdtempSync(path.join(os.tmpdir(), "madar-reconciliation-tests-"));
test.after(() => rmSync(root, { recursive: true, force: true }));
const images = JSON.parse(execFileSync("python3", ["-c", "from PIL import Image; import io,json,base64\nr={}\nfor w in [390,768,1200]:\n im=Image.new('RGBA',(w,900),(0,0,0,255)); b=io.BytesIO();im.save(b,format='PNG'); a=base64.b64encode(b.getvalue()).decode();im.putpixel((0,0),(1,0,0,255));b=io.BytesIO();im.save(b,format='PNG');r[str(w)]=[a,base64.b64encode(b.getvalue()).decode()]\nprint(json.dumps(r))"], { encoding: "utf8" }));
const canonicalPixels = [{ actual: [1, 0, 0, 255], reference: [0, 0, 0, 255], x: 0, y: 0 }];
function seal(directory, entries) {
  mkdirSync(directory, { recursive: true });
  const files = {};
  for (const [name, value] of Object.entries(entries)) {
    const bytes = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value));
    writeFileSync(path.join(directory, name), bytes); files[name] = { bytes: bytes.length, sha256: sha256(bytes) };
  }
  const manifest = Buffer.from(JSON.stringify({ status: "ARTIFACTS_COMPLETE", files, excludes: ["manifest.json", "completion.json"] }));
  writeFileSync(path.join(directory, "manifest.json"), manifest);
  const hash = sha256(manifest);
  writeFileSync(path.join(directory, "completion.json"), JSON.stringify({ status: "COMPLETE", manifestSha256: hash }));
  return hash;
}
function fixture(mutate = () => {}) {
  const dir = mkdtempSync(path.join(root, "case-")), packets = [], statuses = [];
  const files = { "src.txt": sha256("source") }, source = { head: "a".repeat(40), status: "", files, digest: sha256(JSON.stringify(files)) };
  for (const width of [390, 768, 1200]) for (const language of ["en", "ar"]) for (const mode of ["light", "dark"]) for (const state of ["default", "hover", "focus"]) {
    const name = `academy-${width}-${language}-${mode}-${state}`, mismatch = packets.length === 0;
    const reference = Buffer.from(images[width][0], "base64"), actual = Buffer.from(images[width][mismatch ? 1 : 0], "base64");
    const metadata = { width, height: 900, language, mode, state, browser: "151.0", dpr: 1, fixtureHash: sha256("fixture"), metrics: { rect: [0, 0, width, 900], color: "black" } };
    const identity = { source, fixture: metadata.fixtureHash, browser: { version: { product: "HeadlessChrome/151.0", revision: "revision-1" } }, scenario: name };
    const review = { status: mismatch ? "REVIEW_REQUIRED" : "EXACT_PASS", machineFailure: mismatch ? "EXACT_PNG_EQUALITY_FAILED" : null, referenceHash: sha256(reference), actualHash: sha256(actual), metadata, expected: structuredClone(metadata), identity, checks: [{ name: "geometry", pass: true }, { name: "style", pass: true }, { name: "keyboard", pass: true }], failedChecks: [], metadataDifferences: [], identityDifferences: [], pixels: { referenceSize: [width, 900], actualSize: [width, 900], pixels: mismatch ? [{ x: 0, y: 0, reference: [0, 0, 0, 255], actual: [1, 0, 0, 255] }] : [] } };
    const directory = path.join(dir, "packet-" + packets.length);
    const hash = seal(directory, { "reference.png": reference, "actual.png": actual, "review.json": review });
    packets.push({ directory, reference, actual, review }); statuses.push({ academyVisual: name, status: review.status, packet: { directory, manifestSha256: hash } });
  }
  const first = packets[0], r = first.review;
  const decision = { occurrence: "O01", run: 1, scenario: statuses[0].academyVisual, originalPacket: first.directory, originalManifestSha256: statuses[0].packet.manifestSha256, referenceSha256: r.referenceHash, actualSha256: r.actualHash, pixelSignature: sha256(JSON.stringify(canonicalPixels)), changedPixels: 1, identity: structuredClone(r.identity), metadata: structuredClone(r.metadata), originalMachineStatus: r.status, originalMachineFailure: r.machineFailure, ownerDisposition: "OWNER_REVIEWED_VARIANCE" };
  const record = { recordType: "DOCUMENTARY_OWNER_ADJUDICATION_NOT_MACHINE_AUTHORIZATION", machineConsumable: false, occurrences: [decision] };
  const runs = [{ i: 0, exit: 1, unsafe: false, statuses }];
  const f = { dir, packets, statuses, record, decision, runs, suiteDirectory: path.join(dir, "suite"), decisionDirectory: path.join(dir, "decisions") };
  mutate(f);
  for (let i = 0; i < packets.length; i++) {
    const p = packets[i]; const hash = seal(p.directory, { "reference.png": p.reference, "actual.png": p.actual, "review.json": p.review });
    if (statuses[i]) statuses[i].packet.manifestSha256 = hash;
  }
  seal(f.suiteDirectory, { "results.json": runs }); seal(f.decisionDirectory, { "adjudicated-occurrences.json": record });
  return f;
}
const normal = fixture();
test("valid exact evidence plus documentary mismatch preserves all machine results deterministically", () => {
  const a = reconcile(normal), b = reconcile(normal);
  assert.deepEqual(a, b); assert.deepEqual(a.machineCounts, { EXACT_PASS: 35, REVIEW_REQUIRED: 1, FAIL: 0 });
  assert.equal(a.documentaryBoundClaims, 1); assert.equal(a.occurrences[0].machineStatus, "REVIEW_REQUIRED");
  assert.equal(a.occurrences[0].documentary.trust, "DOCUMENTARY_UNAUTHENTICATED");
  assert.equal(a.automaticAcceptance, false); assert.equal(a.authenticatedApproval, false); assert.equal(a.originalPlaywrightResults[0].playwrightExit, 1);
});
test("missing decision leaves mismatch non-green", () => {
  const r = reconcile({ suiteDirectory: normal.suiteDirectory }); assert.equal(r.occurrences[0].documentary.status, "MISSING"); assert.equal(r.machineCounts.REVIEW_REQUIRED, 1);
});
test("forged authenticated approval input is rejected", () => assert.throws(() => reconcile(fixture(f => { f.record.machineConsumable = true; f.record.authenticated = true; })), /forged/));
test("self-authored documentary identity cannot authorize acceptance", () => {
  const r = reconcile(fixture(f => { f.record.provenance = { claimedRole: "Owner", fakeIdentity: "model" }; }));
  assert.equal(r.documentaryBoundClaims, 1); assert.equal(r.authenticatedApproval, false); assert.equal(r.occurrences[0].machineStatus, "REVIEW_REQUIRED");
});
for (const field of ["source", "fixture", "browser"]) test(`stale ${field} decision is not applicable`, () => {
  const r = reconcile(fixture(f => { f.decision.identity[field] = { changed: true }; })); assert.equal(r.occurrences[0].documentary.status, "STALE_OR_MISMATCHED"); assert.equal(r.machineCounts.REVIEW_REQUIRED, 1);
});
for (const field of ["width", "language", "mode"]) test(`changed ${field} binding is stale`, () => {
  const r = reconcile(fixture(f => { f.decision.metadata[field] = "different"; })); assert.equal(r.documentaryBoundClaims, 0);
});
for (const field of ["actualSha256", "referenceSha256", "originalManifestSha256", "pixelSignature"]) test(`changed ${field} cannot reuse historical decision`, () => {
  const r = reconcile(fixture(f => { f.decision[field] = "0".repeat(64); })); assert.equal(r.occurrences[0].documentary.status, "STALE_OR_MISMATCHED");
});
test("corrupted source identity fails", () => assert.throws(() => reconcile(fixture(f => { f.packets[0].review.identity.source.digest = "0".repeat(64); })), /Source identity hash/));
test("fixture identity mismatch fails", () => assert.throws(() => reconcile(fixture(f => { f.packets[0].review.identity.fixture = "0".repeat(64); })), /Fixture\/browser/));
test("incorrect browser identity fails", () => assert.throws(() => reconcile(fixture(f => { f.packets[0].review.identity.browser.version.product = "Chrome/999"; })), /Fixture\/browser/));
test("changed screenshot fails its stored hash", () => assert.throws(() => reconcile(fixture(f => { f.packets[0].actual = f.packets[0].reference; })), /Screenshot\/reference/));
test("corrupt sealed evidence rejected", () => {
  const f = fixture(); writeFileSync(path.join(f.packets[0].directory, "actual.png"), "corrupt"); assert.throws(() => reconcile(f), /Artifact hash mismatch/);
});
test("missing screenshot rejected", () => {
  const f = fixture(); rmSync(path.join(f.packets[0].directory, "reference.png")); assert.throws(() => reconcile(f), /ENOENT/);
});
test("incomplete matrix rejected", () => assert.throws(() => reconcile(fixture(f => f.statuses.pop())), /Incomplete/));
test("incomplete seal rejected", () => {
  const f = fixture(); rmSync(path.join(f.suiteDirectory, "completion.json")); assert.throws(() => reconcile(f), /ENOENT/);
});
for (const kind of ["geometry", "style", "keyboard"]) test(`${kind} failure cannot be approved`, () => {
  const r = reconcile(fixture(f => { f.packets[0].review.checks.find(c => c.name === kind).pass = false; f.packets[0].review.status = "FAIL"; f.statuses[0].status = "FAIL"; }));
  assert.equal(r.machineCounts.FAIL, 1); assert.equal(r.documentaryBoundClaims, 0); assert.ok(r.blockers.includes("MANDATORY_GUARD_FAILURE"));
});
test("false success runner exit rejected", () => assert.throws(() => reconcile(fixture(f => { f.runs[0].exit = 0; })), /successful runner/));
test("sealed report, collision and producer failures preserve evidence", async () => {
  const destination = path.join(root, "report"); await writeReport({ ...normal, writerPath, outputDirectory: destination });
  const report = verifyEvidence(destination).json("reconciliation.json"); assert.equal(report.automaticAcceptance, false);
  const before = readFileSync(path.join(destination, "manifest.json"));
  await assert.rejects(writeReport({ ...normal, writerPath, outputDirectory: destination }), /EEXIST/);
  assert.deepEqual(readFileSync(path.join(destination, "manifest.json")), before);
  const broken = fixture(f => f.statuses.pop()), failed = path.join(root, "failed-report");
  await assert.rejects(writeReport({ ...broken, writerPath, outputDirectory: failed }), /Incomplete/);
  assert.equal(existsSync(path.join(failed, "completion.json")), false); assert.equal(existsSync(path.join(failed, "failure.json")), true);
});
test("CLI success means report generation only, never QA PASS", () => {
  const script = fileURLToPath(new URL("./reconcile-academy-visual-review.mjs", import.meta.url));
  const r = spawnSync(process.execPath, [script, "--suite", normal.suiteDirectory, "--decisions", normal.decisionDirectory, "--writer", writerPath, "--output", path.join(root, "cli-report")], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr); assert.equal(JSON.parse(r.stdout).qaPass, false);
});
test("live reporting without trusted runtime fails without sealing an approval", async () => {
  const destination = path.join(root, "untrusted-live-report");
  await assert.rejects(writeReport({ ...normal, writerPath, outputDirectory: destination, pullNumber: 12 }), /fingerprint/);
  assert.equal(existsSync(path.join(destination, "completion.json")), false);
  assert.equal(existsSync(path.join(destination, "reconciliation.json")), false);
  const r = reconcile(normal); assert.equal(r.authenticatedApproval, false); assert.equal(r.originalPlaywrightResults[0].playwrightExit, 1);
});
