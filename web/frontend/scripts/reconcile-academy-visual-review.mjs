// Documentary reporting only. No input can authorize acceptance or change a runner exit.
import { readFileSync, lstatSync, realpathSync, readdirSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import { isDeepStrictEqual } from "node:util";
import { sha256, loadEvidenceWriter, pixelDifferences } from "../e2e/academy-visual-contract.mjs";

const uncertainDirectory = "/home/judah/madar-qa-evidence/phase-38.1/offline-skia-analysis/execution-20261106-01";
const safeName = name => typeof name === "string" && /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(name) && name !== "." && name !== "..";
const digest = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const canonical = value => JSON.stringify(sort(value));
function sort(value) {
  if (Array.isArray(value)) return value.map(sort);
  return value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map(k => [k, sort(value[k])])) : value;
}
function requireValue(condition, message) { if (!condition) throw new Error(message); }
function regular(file) {
  const st = lstatSync(file);
  requireValue(st.isFile() && !st.isSymbolicLink(), `Non-regular evidence: ${file}`);
  return readFileSync(file);
}
export function verifyEvidence(directory, expectedManifest) {
  requireValue(path.isAbsolute(directory) && realpathSync(directory) === directory, "Evidence directory must be absolute and non-symlinked");
  requireValue(directory !== uncertainDirectory && !directory.startsWith(uncertainDirectory + path.sep), "Provenance-uncertain historical evidence excluded");
  const raw = regular(path.join(directory, "manifest.json"));
  const manifest = JSON.parse(raw), completion = JSON.parse(regular(path.join(directory, "completion.json")));
  const manifestHash = sha256(raw);
  requireValue(completion.status === "COMPLETE" && completion.manifestSha256 === manifestHash, "Incomplete or corrupt evidence seal");
  if (expectedManifest !== undefined) requireValue(digest(expectedManifest) && expectedManifest === manifestHash, "Evidence manifest binding mismatch");
  requireValue(manifest.status === "ARTIFACTS_COMPLETE" && manifest.files && !Array.isArray(manifest.files), "Invalid evidence manifest");
  requireValue(isDeepStrictEqual(manifest.excludes, ["manifest.json", "completion.json"]), "Unexpected manifest exclusions");
  const files = new Map();
  for (const [name, entry] of Object.entries(manifest.files)) {
    requireValue(safeName(name) && !manifest.excludes.includes(name) && name !== "failure.json", "Unsafe or failed artifact inventory");
    const bytes = regular(path.join(directory, name));
    requireValue(Number.isSafeInteger(entry.bytes) && entry.bytes >= 0 && digest(entry.sha256) && bytes.length === entry.bytes && sha256(bytes) === entry.sha256, `Artifact hash mismatch: ${name}`);
    files.set(name, bytes);
  }
  requireValue(isDeepStrictEqual(readdirSync(directory).sort(), [...files.keys(), ...manifest.excludes].sort()), "Incomplete or unexpected evidence inventory");
  const json = name => { requireValue(files.has(name), `Missing evidence: ${name}`); return JSON.parse(files.get(name)); };
  return { directory, manifestHash, files, json };
}
function validateSource(source) {
  requireValue(source && digest(source.digest) && typeof source.head === "string" && typeof source.status === "string" && source.files && !Array.isArray(source.files), "Invalid source identity");
  requireValue(Object.keys(source.files).length > 0 && sha256(JSON.stringify(source.files)) === source.digest, "Source identity hash mismatch");
  for (const [name, hash] of Object.entries(source.files)) requireValue(!path.isAbsolute(name) && !name.split(/[\\/]/).some(p => !p || p === "." || p === "..") && digest(hash), "Invalid source file binding");
}
function sourceComparison(source, root) {
  if (!root) return { checked: false, reason: "Current checkout not supplied; historical identity only" };
  requireValue(path.isAbsolute(root) && realpathSync(root) === root, "Source root must be absolute and non-symlinked");
  for (const [name, hash] of Object.entries(source.files)) requireValue(sha256(regular(path.join(root, name))) === hash, `Current source hash mismatch: ${name}`);
  const git = args => execFileSync("git", args, { cwd: root, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 });
  const names = [...new Set(git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"]).split("\0").filter(Boolean))].sort();
  const addedFiles = names.filter(n => !Object.hasOwn(source.files, n));
  const head = git(["rev-parse", "HEAD"]).trim(), status = git(["status", "--porcelain=v1"]);
  return { checked: true, historicalFileHashesMatch: true, currentIdentityMatchesHistorical: !addedFiles.length && head === source.head && status === source.status, addedFiles, head, status, scope: "Historical decisions do not cover any new execution or changed identity" };
}
function decisionMatches(decision, item, review) {
  return decision.run === item.run && decision.scenario === item.scenario && decision.originalPacket === item.packet && decision.originalManifestSha256 === item.manifestSha256 && decision.referenceSha256 === review.referenceHash && decision.actualSha256 === review.actualHash && decision.pixelSignature === item.pixelSignature && decision.changedPixels === review.pixels.pixels.length && isDeepStrictEqual(decision.identity, review.identity) && isDeepStrictEqual(decision.metadata, review.metadata) && decision.originalMachineStatus === review.status && decision.originalMachineFailure === review.machineFailure;
}
export function reconcile({ suiteDirectory, decisionDirectory, sourceRoot }) {
  const suite = verifyEvidence(suiteDirectory), runs = suite.json("results.json");
  requireValue(Array.isArray(runs) && runs.length > 0, "Missing suite runs");
  let decisions = [], decisionInput = { supplied: false, trust: "NONE" };
  if (decisionDirectory) {
    const evidence = verifyEvidence(decisionDirectory), record = evidence.json("adjudicated-occurrences.json");
    requireValue(record.recordType === "DOCUMENTARY_OWNER_ADJUDICATION_NOT_MACHINE_AUTHORIZATION" && record.machineConsumable === false && Array.isArray(record.occurrences), "Unsupported or forged authenticated-approval input");
    requireValue(!record.authenticated && !record.trusted && !record.signature && !record.automaticAcceptance, "Local authentication claims are not supported");
    decisions = record.occurrences;
    requireValue(decisions.every(d => d.ownerDisposition === "OWNER_REVIEWED_VARIANCE"), "Unsupported documentary disposition");
    decisionInput = { supplied: true, directory: decisionDirectory, manifestSha256: evidence.manifestHash, trust: "DOCUMENTARY_UNAUTHENTICATED", provenance: record.provenance ?? null, warning: "Local claims and their provenance are not independently authenticated; hashes establish byte integrity only" };
  }
  const occurrences = [], originals = [], seen = new Set(), sourceChecks = new Map(), pixelCache = new Map(), usedDecisions = new Set();
  for (const run of runs) {
    requireValue(Number.isSafeInteger(run.i) && run.i >= 0 && Number.isSafeInteger(run.exit) && run.exit >= 0 && run.unsafe === false && Array.isArray(run.statuses) && run.statuses.length === 36, "Incomplete or unsafe Academy suite (36 states required)");
    requireValue(!originals.some(r => r.run === run.i + 1), "Duplicate run identity");
    originals.push({ run: run.i + 1, playwrightExit: run.exit });
    const matrix = new Set();
    for (const capture of run.statuses) {
      requireValue(capture.packet && typeof capture.packet.directory === "string", "Missing packet binding");
      const packet = verifyEvidence(capture.packet.directory, capture.packet.manifestSha256), review = packet.json("review.json");
      const { metadata, identity } = review;
      requireValue(metadata && identity && [390, 768, 1200].includes(metadata.width) && metadata.height === 900 && ["en", "ar"].includes(metadata.language) && ["light", "dark"].includes(metadata.mode) && ["default", "hover", "focus"].includes(metadata.state), "Invalid scenario metadata");
      const scenario = `academy-${metadata.width}-${metadata.language}-${metadata.mode}-${metadata.state}`;
      requireValue(scenario === capture.academyVisual && identity.scenario === scenario && !matrix.has(scenario), "Scenario/state mismatch or duplicate"); matrix.add(scenario);
      requireValue(digest(metadata.fixtureHash) && identity.fixture === metadata.fixtureHash && identity.browser && identity.browser.version && identity.browser.version.product?.split("/").at(-1) === metadata.browser && typeof identity.browser.version.revision === "string" && metadata.dpr === 1, "Fixture/browser/environment identity mismatch");
      validateSource(identity.source);
      const sourceKey = sha256(canonical(identity.source));
      if (!sourceChecks.has(sourceKey)) sourceChecks.set(sourceKey, sourceComparison(identity.source, sourceRoot));
      const reference = packet.files.get("reference.png"), actual = packet.files.get("actual.png");
      requireValue(reference && actual && sha256(reference) === review.referenceHash && sha256(actual) === review.actualHash, "Screenshot/reference hash mismatch");
      const pixelKey = review.referenceHash + review.actualHash;
      if (!pixelCache.has(pixelKey)) pixelCache.set(pixelKey, pixelDifferences(reference, actual));
      const pixels = pixelCache.get(pixelKey);
      requireValue(pixels.referenceSize[0] === metadata.width && pixels.actualSize[0] === metadata.width && pixels.referenceSize[1] >= metadata.height && pixels.actualSize[1] >= metadata.height, "Screenshot dimensions do not match viewport");
      requireValue(isDeepStrictEqual(pixels, review.pixels), "Pixel evidence mismatch");
      requireValue(Array.isArray(review.checks) && review.checks.length > 0 && review.checks.every(c => typeof c.name === "string" && typeof c.pass === "boolean") && review.expected && Array.isArray(review.metadataDifferences) && Array.isArray(review.identityDifferences) && Array.isArray(review.failedChecks), "Missing mandatory checks");
      const guardFailed = review.checks.some(c => !c.pass) || review.failedChecks.length > 0 || review.identityDifferences.length > 0 || !isDeepStrictEqual(review.expected, metadata) || !isDeepStrictEqual(pixels.referenceSize, pixels.actualSize);
      const machineStatus = guardFailed ? "FAIL" : reference.equals(actual) ? "EXACT_PASS" : "REVIEW_REQUIRED";
      requireValue(capture.status === machineStatus && review.status === machineStatus, "Machine verdict inconsistent with evidence");
      requireValue(review.machineFailure === (reference.equals(actual) ? null : "EXACT_PNG_EQUALITY_FAILED"), "Original pixel failure classification mismatch");
      const key = `${run.i + 1}:${scenario}`; requireValue(!seen.has(key), "Duplicate occurrence"); seen.add(key);
      const item = { run: run.i + 1, scenario, packet: packet.directory, manifestSha256: packet.manifestHash, pixelSignature: sha256(canonical(pixels.pixels)), machineStatus, machineFailure: review.machineFailure, referenceSha256: review.referenceHash, actualSha256: review.actualHash, identity, metadata, documentary: { status: "MISSING", trust: "NONE" }, authenticatedApproval: false, automaticAcceptance: false };
      const candidates = decisions.map((d, i) => ({ d, i })).filter(({ d }) => d.run === item.run && d.scenario === scenario);
      requireValue(candidates.length <= 1, "Ambiguous duplicate documentary decisions");
      if (candidates.length) {
        const { d, i } = candidates[0]; usedDecisions.add(i);
        item.documentary = { status: decisionMatches(d, item, review) && machineStatus === "REVIEW_REQUIRED" ? "BOUND_HISTORICAL_CLAIM" : "STALE_OR_MISMATCHED", claimedDisposition: d.ownerDisposition, trust: "DOCUMENTARY_UNAUTHENTICATED", occurrence: d.occurrence ?? null };
      }
      occurrences.push(item);
    }
    requireValue(run.exit !== 0 || occurrences.filter(o => o.run === run.i + 1).every(o => o.machineStatus === "EXACT_PASS"), "Non-green captures with a successful runner exit");
  }
  const counts = Object.fromEntries(["EXACT_PASS", "REVIEW_REQUIRED", "FAIL"].map(s => [s, occurrences.filter(o => o.machineStatus === s).length]));
  return { schemaVersion: 1, purpose: "LOCAL_DOCUMENTARY_REPORT_ONLY", evidenceTrust: "LOCAL_CHECKSUM_VERIFIED_NOT_AUTHENTICATED", suite: { directory: suiteDirectory, manifestSha256: suite.manifestHash }, machineCounts: counts, originalPlaywrightResults: originals, decisionInput, documentaryBoundClaims: occurrences.filter(o => o.documentary.status === "BOUND_HISTORICAL_CLAIM").length, unusedDocumentaryDecisions: decisions.map((d, i) => ({ i, run: d.run, scenario: d.scenario })).filter(d => !usedDecisions.has(d.i)), sourceComparisons: Object.fromEntries(sourceChecks), occurrences, automaticAcceptance: false, authenticatedApproval: false, blockers: ["AUTOMATED_ACCEPTANCE_NOT_IMPLEMENTED: GitHub owner PR reviews are a future target, not an authenticated provider", ...(counts.REVIEW_REQUIRED ? ["ORIGINAL_REVIEW_REQUIRED_REMAINS_NON_GREEN"] : []), ...(counts.FAIL ? ["MANDATORY_GUARD_FAILURE"] : []), ...(originals.some(r => r.playwrightExit !== 0) ? ["ORIGINAL_PLAYWRIGHT_EXECUTION_FAILED"] : []), ...([...sourceChecks.values()].some(s => !s.checked || !s.currentIdentityMatchesHistorical) ? ["CURRENT_IDENTITY_NOT_PROVEN_IDENTICAL_TO_HISTORICAL_CAPTURE"] : [])] };
}
export async function writeReport(options) {
  const writer = await loadEvidenceWriter(options.writerPath);
  return writer(options.outputDirectory, async ({ write, writeJson }) => {
    const report = reconcile(options);
    writeJson("reconciliation.json", report);
    write("REPORT.txt", `LOCAL DOCUMENTARY RECONCILIATION — AUTOMATED ACCEPTANCE STILL BLOCKED\n\nMachine counts: ${JSON.stringify(report.machineCounts)}\nOriginal Playwright exits: ${JSON.stringify(report.originalPlaywrightResults)}\nBound documentary claims: ${report.documentaryBoundClaims}\nTrust: DOCUMENTARY_UNAUTHENTICATED. No owner identity or consent is verified by this tool.\nNo machine verdict is changed. A completed report is not a QA PASS.\nBlockers:\n${report.blockers.join("\n")}\n\nFull exact bindings, missing/stale claims and unchanged machine failures: reconciliation.json\n`);
  }, ["reconciliation.json", "REPORT.txt"]);
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    const names = { "--suite": "suiteDirectory", "--decisions": "decisionDirectory", "--source-root": "sourceRoot", "--writer": "writerPath", "--output": "outputDirectory" }, options = {};
    for (let i = 2; i < process.argv.length; i += 2) {
      requireValue(names[process.argv[i]] && process.argv[i + 1] && !options[names[process.argv[i]]], "Invalid or duplicate CLI arguments");
      options[names[process.argv[i]]] = process.argv[i + 1];
    }
    requireValue(options.suiteDirectory && options.writerPath && options.outputDirectory, "Usage: --suite ABS_DIR [--decisions ABS_DIR] [--source-root ABS_REPO] --writer VERIFIED_MODULE --output NEW_ABS_DIR");
    console.log(JSON.stringify({ report: await writeReport(options), reportGenerated: true, qaPass: false }));
  } catch (error) { console.error(`RECONCILIATION FAILED: ${error.message}`); process.exitCode = 1; }
}
