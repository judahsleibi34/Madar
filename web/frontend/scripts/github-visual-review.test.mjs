import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { evaluateReviewSnapshot, evidenceBinding, verifyRuntimePin, runtimeFingerprint, verifyLiveReview } from "./github-visual-review.mjs";
const policy = JSON.parse(readFileSync(new URL("./visual-review-policy.json", import.meta.url)));
const now = Date.parse("2026-11-07T12:00:00Z"), sha = "a".repeat(40), digest = "b".repeat(64);
function fixture() {
  const report = { suite: { manifestSha256: digest }, machineCounts: { FAIL: 0 }, sourceComparisons: { source: { checked: true, currentIdentityMatchesHistorical: true } }, occurrences: [{ run: 1, scenario: "academy-390-ar-light-default", manifestSha256: digest, referenceSha256: digest, actualSha256: "c".repeat(64), pixelSignature: digest, machineStatus: "REVIEW_REQUIRED", machineFailure: "EXACT_PNG_EQUALITY_FAILED", identity: { source: { head: sha, status: "", digest }, fixture: digest, browser: { version: "151" } }, metadata: { state: "default" } }] };
  const binding = evidenceBinding(report, 12);
  const reviewer = { ...policy.reviewer };
  const review = { id: 100, user: reviewer, state: "APPROVED", commit_id: sha, submitted_at: "2026-11-07T11:00:00Z", pull_request_url: "https://api.github.com/repos/judahsleibi34/Madar/pulls/12", body: JSON.stringify({ schemaVersion: 1, decision: "OWNER_REVIEWED_VARIANCE", willingToReview: true, binding }) };
  const snapshot = { repository: { id: policy.repositoryId, full_name: policy.repository, archived: false }, pull: { number: 12, state: "open", draft: false, merged: false, base: { repo: { id: policy.repositoryId } }, head: { repo: { id: policy.repositoryId }, sha }, user: { id: 178982252 } }, reviewer, reviews: [review] };
  return { policy: structuredClone(policy), binding, snapshot, now, report };
}
test("valid fixture is never authenticated; machine failures preserved", () => {
  const f = fixture(), before = structuredClone(f.report), result = evaluateReviewSnapshot(f);
  assert.equal(result.authenticated, false); assert.equal(result.status, "FIXTURE_EVALUATION_ONLY"); assert.deepEqual(f.report, before);
});
const invalid = {
  "unauthorized policy": f => { f.policy.reviewer.id++; },
  "identity mismatch": f => { f.snapshot.reviewer.id++; },
  "self review": f => { f.snapshot.pull.user.id = policy.reviewer.id; },
  "repository mismatch": f => { f.snapshot.repository.id++; },
  "fork mismatch": f => { f.snapshot.pull.head.repo.id++; },
  "revision mismatch": f => { f.snapshot.pull.head.sha = "d".repeat(40); },
  "missing decision": f => { f.snapshot.reviews = []; },
  "dismissed": f => { f.snapshot.reviews[0].state = "DISMISSED"; },
  "revoked": f => { f.snapshot.reviews[0].state = "CHANGES_REQUESTED"; },
  "pending": f => { f.snapshot.reviews[0].state = "PENDING"; },
  "unknown state": f => { f.snapshot.reviews[0].state = "PASS"; },
  "stale": f => { f.snapshot.reviews[0].submitted_at = "2026-11-06T11:59:59Z"; },
  "future": f => { f.snapshot.reviews[0].submitted_at = "2026-11-08T12:00:00Z"; },
  "different review commit": f => { f.snapshot.reviews[0].commit_id = "e".repeat(40); },
  "wrong PR": f => { f.snapshot.reviews[0].pull_request_url += "0"; },
  "forged arbitrary JSON": f => { f.snapshot.reviews[0].body = '{"approved":true}'; },
  "missing willingness": f => { const b = JSON.parse(f.snapshot.reviews[0].body); b.willingToReview = false; f.snapshot.reviews[0].body = JSON.stringify(b); },
  "superseding comment": f => { f.snapshot.reviews.push({ ...f.snapshot.reviews[0], id: 101, state: "COMMENTED", submitted_at: "2026-11-07T11:01:00Z" }); },
  "duplicate review": f => { f.snapshot.reviews.push(f.snapshot.reviews[0]); },
  "outstanding other rejection": f => { f.snapshot.reviews.push({ ...f.snapshot.reviews[0], id: 101, user: { id: 123 }, state: "CHANGES_REQUESTED" }); },
};
for (const [name, change] of Object.entries(invalid)) test(name + " fails closed", () => { const f = fixture(); change(f); assert.throws(() => evaluateReviewSnapshot(f)); });
for (const field of ["manifestSha256", "referenceSha256", "actualSha256", "pixelSignature", "scenario", "metadata", "identity"]) test("changed " + field + " binding", () => {
  const f = fixture(); f.binding.occurrences[0][field] = "changed"; assert.throws(() => evaluateReviewSnapshot(f), /binding/);
});
for (const field of ["source", "fixture", "browser"]) test("changed " + field + " identity", () => {
  const f = fixture(); f.binding.occurrences[0].identity[field] = "changed"; assert.throws(() => evaluateReviewSnapshot(f), /binding/);
});
test("suite manifest replay rejected", () => { const f = fixture(); f.binding.suiteManifestSha256 = "0".repeat(64); assert.throws(() => evaluateReviewSnapshot(f)); });
test("dirty source and guard failure rejected", () => {
  const f = fixture(); f.report.occurrences[0].identity.source.status = " M source"; assert.throws(() => evidenceBinding(f.report, 12), /Dirty/);
  f.report.machineCounts.FAIL = 1; assert.throws(() => evidenceBinding(f.report, 12), /guard/);
});
test("incomplete or unchecked report rejected", () => { assert.throws(() => evidenceBinding({}, 12)); const f = fixture(); f.report.sourceComparisons.source.checked = false; assert.throws(() => evidenceBinding(f.report, 12)); });
test("trusted fingerprint required; copied responses cannot enter live path", () => {
  assert.throws(() => verifyRuntimePin(undefined)); assert.throws(() => verifyRuntimePin("0".repeat(64))); verifyRuntimePin(runtimeFingerprint());
  assert.throws(() => verifyLiveReview({ report: fixture().report, pullNumber: 12, snapshot: fixture().snapshot }), /fingerprint/);
});
test("24-hour boundary accepted only as simulation", () => { const f = fixture(); f.snapshot.reviews[0].submitted_at = "2026-11-06T12:00:00Z"; assert.equal(evaluateReviewSnapshot(f).authenticated, false); });

// Mock the Node subprocess boundary only inside this test process. Production
// accepts no fixture transport, response file, or authentication override.
import childProcess from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
function withTransport(t, respond, action) {
  const m = t.mock.method(childProcess, "execFileSync", (binary, args, options) => {
    assert.equal(binary, "/usr/bin/gh"); assert.equal(args[args.indexOf("--method") + 1], "GET");
    assert.equal(args[args.indexOf("--hostname") + 1], "github.com"); assert.equal(options.timeout, 30000);
    return JSON.stringify(respond(args.at(-1)));
  });
  syncBuiltinESMExports();
  try { return action(); } finally { m.mock.restore(); syncBuiltinESMExports(); }
}
function transportFixture(f) {
  return endpoint => {
    if (endpoint === "/user") return { id: 178982252, type: "User" };
    if (endpoint === "/users/Saliba-codes") return f.snapshot.reviewer;
    if (endpoint.endsWith("/Madar")) return f.snapshot.repository;
    if (endpoint.endsWith("/pulls/12")) return f.snapshot.pull;
    if (endpoint.includes("/reviews?")) return f.snapshot.reviews;
    throw Error("Unexpected endpoint");
  };
}
function liveOptions(f) { return { report: f.report, pullNumber: 12, trustedRuntimeSha256: runtimeFingerprint(), sourceRoot: "/tmp" }; }
test("transport simulation verifies two reads, never constitutes a live integration result", t => {
  const f = fixture(); f.snapshot.reviews[0].submitted_at = new Date().toISOString();
  let reads = 0; const respond = transportFixture(f);
  const result = withTransport(t, endpoint => { reads++; return respond(endpoint); }, () => verifyLiveReview(liveOptions(f)));
  assert.equal(reads, 9); assert.equal(result.automaticAcceptance, false);
  assert.equal(f.report.occurrences[0].machineStatus, "REVIEW_REQUIRED");
});
test("API failure is sanitized and cannot fall back to fixtures", t => {
  withTransport(t, () => { throw Error("secret-token-must-not-escape"); }, () => assert.throws(() => verifyLiveReview(liveOptions(fixture())), /^Error: Live GitHub read failed; no cached authorization is permitted$/));
});
test("changed API state between reads blocks verification", t => {
  const f = fixture(), respond = transportFixture(f); let reads = 0;
  withTransport(t, endpoint => {
    const value = structuredClone(respond(endpoint));
    if (endpoint.endsWith("/pulls/12") && ++reads === 2) value.head.sha = "f".repeat(40);
    return value;
  }, () => assert.throws(() => verifyLiveReview(liveOptions(f)), /state changed/));
});
test("full review pages are exhausted; later rejection is not hidden", t => {
  const f = fixture(), respond = transportFixture(f); f.snapshot.reviews[0].submitted_at = new Date().toISOString();
  const pages = [];
  withTransport(t, endpoint => {
    if (!endpoint.includes("/reviews?")) return respond(endpoint);
    const page = Number(new URL("https://api.github.com" + endpoint).searchParams.get("page")); pages.push(page);
    if (page === 1) return Array.from({ length: 100 }, (_, i) => ({ ...f.snapshot.reviews[0], id: 100 + i }));
    return [{ ...f.snapshot.reviews[0], id: 200, state: "CHANGES_REQUESTED" }];
  }, () => assert.throws(() => verifyLiveReview(liveOptions(f)), /rejection/));
  assert.deepEqual(pages, [1, 2, 1, 2]);
});
test("malformed pagination fails closed", t => {
  const f = fixture(), respond = transportFixture(f);
  withTransport(t, endpoint => endpoint.includes("/reviews?") ? {} : respond(endpoint), () => assert.throws(() => verifyLiveReview(liveOptions(f)), /pagination/));
});
