import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { evaluateVisual, loadEvidenceWriter, writeReviewPacket } from './academy-visual-contract.mjs';

const png = colors => execFileSync('python3', ['-c', "from PIL import Image; import sys,json; a=json.load(sys.stdin); im=Image.new('RGBA',(len(a),1)); im.putdata([tuple(c) for c in a]); im.save(sys.stdout.buffer,format='PNG')"], { input: JSON.stringify(colors) });
const original = png([[0, 0, 0, 255], [255, 255, 255, 255]]);
const one = png([[1, 0, 0, 255], [255, 255, 255, 255]]);
const two = png([[1, 0, 0, 255], [255, 254, 255, 255]]);
const identity = { source: { digest: 'source' }, fixture: 'fixture', browser: { revision: 'revision' }, scenario: 'scenario' };
const input = () => ({ reference: original, actual: original, expected: { geometry: [0, 0, 2, 1], color: 'black' }, metadata: { geometry: [0, 0, 2, 1], color: 'black' }, identity, expectedIdentity: identity, checks: [{ name: 'navigation', pass: true }] });
test('exact valid match', () => assert.equal(evaluateVisual(input()).status, 'EXACT_PASS'));
for (const [name, actual, count] of [['one pixel', one, 1], ['multiple pixels', two, 2]]) test(name, () => {
  const result = evaluateVisual({ ...input(), actual });
  assert.equal(result.status, 'REVIEW_REQUIRED'); assert.equal(result.pixels.pixels.length, count);
  assert.deepEqual(result.pixels.pixels[0], { x: 0, y: 0, reference: [0, 0, 0, 255], actual: [1, 0, 0, 255] });
  assert.equal(result.machineFailure, 'EXACT_PNG_EQUALITY_FAILED');
});
for (const key of ['geometry', 'color']) test(`genuine ${key} regression`, () => {
  const args = input(); args.metadata[key] = 'changed'; assert.equal(evaluateVisual(args).status, 'FAIL');
});
for (const actual of [undefined, Buffer.from('invalid PNG')]) test(`missing/invalid screenshot ${actual?.length}`, () => assert.equal(evaluateVisual({ ...input(), actual }).status, 'FAIL'));
for (const field of ['expected', 'identity', 'checks']) test(`missing evidence ${field}`, () => assert.equal(evaluateVisual({ ...input(), [field]: undefined }).status, 'FAIL'));
for (const key of ['source', 'fixture', 'browser', 'scenario']) test(`mismatched ${key} binding`, () => assert.equal(evaluateVisual({ ...input(), identity: { ...identity, [key]: 'changed' } }).status, 'FAIL'));
for (const approval of [undefined, { approved: true }, { approved: true, source: 'stale' }, { ...identity, approved: true }]) test(`no automatic approval ${JSON.stringify(approval)}`, () => assert.equal(evaluateVisual({ ...input(), actual: one, approval }).status, 'REVIEW_REQUIRED'));
test('behavior failure overrides exact pixels', () => assert.equal(evaluateVisual({ ...input(), checks: [{ name: 'focus', pass: false }] }).status, 'FAIL'));
test('writer errors propagate, never return accepted result', async () => {
  await assert.rejects(writeReviewPacket({ ...input(), result: evaluateVisual(input()), writer: async () => { throw Error('disk failure'); } }), /disk failure/);
});
test('tampered image cannot be sealed', async () => {
  await assert.rejects(writeReviewPacket({ ...input(), actual: one, result: evaluateVisual(input()) }), /changed after/);
});
test('verified writer seals complete packet; collision preserves original; producer failure has no completion', async () => {
  const writer = await loadEvidenceWriter(process.env.MADAR_ATOMIC_EVIDENCE_WRITER);
  const parent = mkdtempSync(path.join(os.tmpdir(), 'academy-contract-test-'));
  try {
    const directory = path.join(parent, 'packet');
    const args = { ...input(), directory, writer, result: evaluateVisual(input()), observations: {}, interactions: {} };
    await writeReviewPacket(args);
    const before = readFileSync(path.join(directory, 'manifest.json'));
    await assert.rejects(writeReviewPacket(args), /EEXIST/);
    assert.deepEqual(readFileSync(path.join(directory, 'manifest.json')), before);
    await assert.rejects(writer(path.join(parent, 'failed'), () => { throw Error('producer'); }, []), /producer/);
    assert.equal(existsSync(path.join(parent, 'failed', 'completion.json')), false);
  } finally { rmSync(parent, { recursive: true }); }
});

test('cropped screenshot is FAIL, not review', () => assert.equal(evaluateVisual({ ...input(), actual: png([[0, 0, 0, 255]]) }).status, 'FAIL'));
