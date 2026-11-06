// Reporting only. Never execute a candidate PR's validator with credentials.
// Bootstrap: a trusted operator must verify this entire runtime BEFORE execution,
// and supply its independently approved fingerprint. A self-computed fingerprint
// is not a trust anchor. The OS, Node, gh, Python/Pillow and credential store are
// trusted prerequisites. This module cannot authenticate its own initial loading.
import { createHash } from "node:crypto";
import { readFileSync, realpathSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { isDeepStrictEqual } from "node:util";

const hash = value => createHash("sha256").update(value).digest("hex");
const check = (ok, message) => { if (!ok) throw Error(message); };
const digest = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const policyURL = new URL("./visual-review-policy.json", import.meta.url);
const runtimeFiles = ["./github-visual-review.mjs", "./reconcile-academy-visual-review.mjs", "./visual-review-policy.json", "../e2e/academy-visual-contract.mjs"];
export function runtimeFingerprint() {
  return hash(JSON.stringify(runtimeFiles.map(name => [name, hash(readFileSync(new URL(name, import.meta.url)))])));
}
export function verifyRuntimePin(pin) {
  check(digest(pin) && pin === runtimeFingerprint(), "Missing or mismatched independently trusted runtime fingerprint");
}
function policyCheck(policy) {
  check(policy.schemaVersion === 1 && policy.repository === "judahsleibi34/Madar" && policy.repositoryId === 1233897731 && policy.reviewer?.id === 75858844 && policy.reviewer.login === "Saliba-codes" && policy.reviewer.type === "User" && policy.maximumAgeMs === 86400000 && policy.requiresExplicitWillingness === true && policy.purpose === "AUTHENTICATED_REPORTING_ONLY", "Unsupported reviewer policy");
}
// The review BODY must be exactly JSON.stringify({schemaVersion:1,
// decision:"OWNER_REVIEWED_VARIANCE", willingToReview:true, binding:<below>}).
// Hashes bind byte identities; they do not attest that a test producer is honest.
export function evidenceBinding(report, pullNumber) {
  check(Number.isSafeInteger(pullNumber) && pullNumber > 0, "Invalid PR number");
  check(report?.occurrences?.length > 0 && digest(report.suite?.manifestSha256), "Incomplete report");
  check(report.machineCounts.FAIL === 0 && report.occurrences.every(o => ["EXACT_PASS", "REVIEW_REQUIRED"].includes(o.machineStatus)), "Mandatory guard failure");
  const comparisons = Object.values(report.sourceComparisons);
  check(comparisons.length > 0 && comparisons.every(c => c.checked && c.currentIdentityMatchesHistorical), "Current source identity not verified");
  const revision = report.occurrences[0].identity.source.head;
  check(/^[a-f0-9]{40}$/.test(revision) && report.occurrences.every(o => o.identity.source.head === revision && o.identity.source.status === ""), "Dirty or mixed capture revision");
  const occurrences = report.occurrences.filter(o => o.machineStatus === "REVIEW_REQUIRED").map(o => ({
    run: o.run, scenario: o.scenario, manifestSha256: o.manifestSha256,
    referenceSha256: o.referenceSha256, actualSha256: o.actualSha256,
    pixelSignature: o.pixelSignature, identity: o.identity, metadata: o.metadata,
    machineStatus: o.machineStatus, machineFailure: o.machineFailure,
  }));
  check(occurrences.length > 0, "No review-required occurrences");
  return { repository: "judahsleibi34/Madar", repositoryId: 1233897731, pullNumber, revision, suiteManifestSha256: report.suite.manifestSha256, occurrences };
}
// Pure predicate for controlled regression fixtures. Its result is deliberately
// NEVER an authenticated receipt. Production has no injectable API transport.
export function evaluateReviewSnapshot({ policy, binding, snapshot, now }) {
  policyCheck(policy);
  check(Number.isFinite(now), "Missing verification time");
  const { repository, pull, reviewer, reviews } = snapshot;
  check(repository.id === policy.repositoryId && repository.full_name === policy.repository && repository.archived === false, "Repository mismatch");
  check(pull.number === binding.pullNumber && pull.state === "open" && pull.draft === false && pull.merged === false && pull.base?.repo?.id === policy.repositoryId && pull.head?.repo?.id === policy.repositoryId && pull.head.sha === binding.revision, "PR revision or repository mismatch");
  check(Number.isSafeInteger(pull.user?.id) && pull.user.id !== policy.reviewer.id, "Self-review or unknown author");
  check(reviewer.id === policy.reviewer.id && reviewer.login === policy.reviewer.login && reviewer.type === "User", "Reviewer identity mismatch");
  check(Array.isArray(reviews) && reviews.length > 0, "Missing reviews");
  const seen = new Set();
  for (const r of reviews) {
    check(Number.isSafeInteger(r.id) && !seen.has(r.id) && Number.isSafeInteger(r.user?.id) && ["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"].includes(r.state), "Ambiguous review data"); seen.add(r.id);
    check(r.state !== "PENDING", "Pending review prevents complete assessment");
    check(Number.isFinite(Date.parse(r.submitted_at)) && Date.parse(r.submitted_at) <= now, "Invalid review time");
  }
  // Conservative: any currently outstanding request for changes blocks reporting.
  // Comments/dismissals by the designated reviewer supersede their earlier approval.
  const byActor = new Map(), objections = new Map();
  for (const r of [...reviews].sort((a, b) => Date.parse(a.submitted_at) - Date.parse(b.submitted_at) || a.id - b.id)) {
    byActor.set(r.user.id, r);
    if (r.state !== "COMMENTED") objections.set(r.user.id, r.state);
  }
  check(![...objections.values()].includes("CHANGES_REQUESTED"), "Outstanding rejection");
  const review = byActor.get(policy.reviewer.id);
  check(review && review.state === "APPROVED" && review.user.login === reviewer.login && review.user.type === "User", "Missing, revoked or superseded approval");
  check(review.commit_id === binding.revision && now - Date.parse(review.submitted_at) <= policy.maximumAgeMs, "Stale approval");
  check(review.pull_request_url === `https://api.github.com/repos/${policy.repository}/pulls/${binding.pullNumber}`, "Review PR mismatch");
  let body;
  try { body = JSON.parse(review.body); } catch { throw Error("Missing structured review binding"); }
  check(isDeepStrictEqual(body, { schemaVersion: 1, decision: "OWNER_REVIEWED_VARIANCE", willingToReview: true, binding }), "Review evidence binding or willingness mismatch");
  return { status: "FIXTURE_EVALUATION_ONLY", authenticated: false, reviewId: review.id, reviewerId: reviewer.id, bodySha256: hash(review.body), submittedAt: review.submitted_at };
}
function api(endpoint) {
  // Fixed executable/host, no shell, no cache, no response files, bounded reads.
  check(endpoint.startsWith("/repos/judahsleibi34/Madar") || endpoint === "/user" || endpoint === "/users/Saliba-codes", "Disallowed API endpoint");
  try {
    const env = { ...process.env, GH_HOST: "github.com", GH_PROMPT_DISABLED: "1" };
    delete env.GH_DEBUG;
    return JSON.parse(execFileSync("/usr/bin/gh", ["api", "--hostname", "github.com", "--method", "GET", "-H", "Accept: application/vnd.github+json", "-H", "X-GitHub-Api-Version: 2022-11-28", endpoint], { env, encoding: "utf8", timeout: 30000, maxBuffer: 8 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"] }));
  } catch { throw Error("Live GitHub read failed; no cached authorization is permitted"); }
}
function snapshot(pullNumber) {
  const repository = api("/repos/judahsleibi34/Madar");
  const pull = api(`/repos/judahsleibi34/Madar/pulls/${pullNumber}`);
  const reviewer = api("/users/Saliba-codes"), reviews = [];
  for (let page = 1; page <= 100; page++) {
    const batch = api(`/repos/judahsleibi34/Madar/pulls/${pullNumber}/reviews?per_page=100&page=${page}`);
    check(Array.isArray(batch) && batch.length <= 100, "Incomplete review pagination");
    reviews.push(...batch);
    if (batch.length < 100) return { repository, pull, reviewer, reviews };
  }
  throw Error("Review pagination limit exceeded");
}
export function verifyLiveReview({ report, pullNumber, trustedRuntimeSha256, sourceRoot }) {
  verifyRuntimePin(trustedRuntimeSha256);
  check(sourceRoot && realpathSync(sourceRoot) !== realpathSync(new URL("../../../", import.meta.url)), "Run an independently trusted validator copy outside the candidate checkout");
  const policy = JSON.parse(readFileSync(policyURL)); policyCheck(policy);
  const binding = evidenceBinding(report, pullNumber);
  const account = api("/user"); check(Number.isSafeInteger(account.id) && account.type === "User", "Authenticated GitHub user unavailable");
  const first = snapshot(pullNumber), second = snapshot(pullNumber);
  check(isDeepStrictEqual(first, second), "GitHub state changed during verification");
  const now = Date.now(), evaluated = evaluateReviewSnapshot({ policy, binding, snapshot: second, now });
  verifyRuntimePin(trustedRuntimeSha256);
  return { ...evaluated, status: "AUTHENTICATED_OWNER_REVIEWED_VARIANCE", authenticated: true, automaticAcceptance: false, verifiedAt: new Date(now).toISOString(), expiresAt: new Date(Date.parse(evaluated.submittedAt) + policy.maximumAgeMs).toISOString(), repositoryId: policy.repositoryId, pullNumber, revision: binding.revision, suiteManifestSha256: binding.suiteManifestSha256, runtimeSha256: trustedRuntimeSha256, snapshotSha256: hash(JSON.stringify(second)), warning: "Point-in-time live verification only; reverify before any future use. Not QA acceptance or producer attestation." };
}
