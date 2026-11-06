// Test-only triage. This module deliberately has no approval-consumption API.
import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
export const WRITER_SHA256 = '035fa8f0635784edbbcdac59660a486ee8e0587eab4441f39430218b260a24ab';
export function sourceIdentity(root) {
  const git = args => execFileSync('git', args, { cwd: root, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 });
  const files = Object.fromEntries([...new Set(git(['ls-files', '-z', '--cached', '--others', '--exclude-standard']).split('\0').filter(Boolean))].sort().map(name => [name, sha256(readFileSync(path.join(root, name)))]));
  return { head: git(['rev-parse', 'HEAD']).trim(), status: git(['status', '--porcelain=v1']), files, digest: sha256(JSON.stringify(files)) };
}
export function differences(expected, actual, at = '$') {
  if (isDeepStrictEqual(expected, actual)) return [];
  if (expected && actual && typeof expected === 'object' && typeof actual === 'object') {
    return [...new Set([...Object.keys(expected), ...Object.keys(actual)])].flatMap(key => differences(expected[key], actual[key], `${at}.${key}`));
  }
  return [{ path: at, expected: expected ?? null, actual: actual ?? null }];
}
// Existing diagnostic infrastructure, not a new npm dependency. Failure to decode
// either complete PNG is fatal. No tolerance, crop, mask or selected-image retry.
export function pixelDifferences(reference, actual) {
  if (!Buffer.isBuffer(reference) || !Buffer.isBuffer(actual)) throw Error('Missing screenshot');
  const script = `import sys,json,base64,io
from PIL import Image
p=json.load(sys.stdin)
def decode(s):
 b=base64.b64decode(s,validate=True)
 im=Image.open(io.BytesIO(b))
 if im.format!='PNG': raise ValueError('Not PNG')
 im.verify()
 im=Image.open(io.BytesIO(b)); im.load()
 return im.convert('RGBA')
a,b=map(decode,p)
changes=[]
for y in range(max(a.height,b.height)):
 for x in range(max(a.width,b.width)):
  av=list(a.getpixel((x,y))) if x<a.width and y<a.height else None
  bv=list(b.getpixel((x,y))) if x<b.width and y<b.height else None
  if av!=bv: changes.append({'x':x,'y':y,'reference':av,'actual':bv})
print(json.dumps({'referenceSize':list(a.size),'actualSize':list(b.size),'pixels':changes}))`;
  return JSON.parse(execFileSync('python3', ['-c', script], { input: JSON.stringify([reference.toString('base64'), actual.toString('base64')]), maxBuffer: 256 * 1024 * 1024 }).toString());
}
export function evaluateVisual({ reference, actual, expected, metadata, identity, expectedIdentity, checks, approval }) {
  try {
    if (!expected || !metadata || !identity || !expectedIdentity) throw Error('Missing evidence identity or metadata');
    for (const key of ['source', 'fixture', 'browser', 'scenario']) {
      if (!identity[key] || !expectedIdentity[key]) throw Error(`Missing ${key} identity`);
    }
    if (!Array.isArray(checks) || !checks.length || checks.some(c => !c.name || typeof c.pass !== 'boolean')) throw Error('Invalid mandatory checks');
    const pixels = pixelDifferences(reference, actual);
    const metadataDifferences = differences(expected, metadata);
    const identityDifferences = differences(expectedIdentity, identity);
    const failedChecks = checks.filter(c => !c.pass);
    if (!isDeepStrictEqual(pixels.referenceSize, pixels.actualSize)) failedChecks.push({ name: 'screenshot dimensions', pass: false });
    const exact = reference.equals(actual);
    const status = metadataDifferences.length || identityDifferences.length || failedChecks.length ? 'FAIL' : exact ? 'EXACT_PASS' : 'REVIEW_REQUIRED';
    return { status, machineFailure: exact ? null : 'EXACT_PNG_EQUALITY_FAILED', referenceHash: sha256(reference), actualHash: sha256(actual), pixels, metadataDifferences, identityDifferences, checks, failedChecks, identity, approval: approval === undefined ? 'NOT_PROVIDED_NOT_CONSUMED' : 'UNSUPPORTED_NOT_CONSUMED' };
  } catch (error) {
    return { status: 'FAIL', machineFailure: 'INVALID_EVIDENCE', error: error.message };
  }
}
export async function loadEvidenceWriter(filename) {
  if (!filename || sha256(readFileSync(filename)) !== WRITER_SHA256) throw Error('Verified atomic evidence writer required');
  return (await import(pathToFileURL(filename).href)).runEvidence;
}
export async function writeReviewPacket({ directory, writer, result, reference, actual, expected, metadata, observations, interactions }) {
  if (!result || result.status === 'FAIL' && result.machineFailure === 'INVALID_EVIDENCE') throw Error('Cannot seal invalid evidence as a review packet');
  if (sha256(reference) !== result.referenceHash || sha256(actual) !== result.actualHash) throw Error('Evidence changed after evaluation');
  return writer(directory, async ({ write, writeJson }) => {
    write('reference.png', reference); write('actual.png', actual);
    writeJson('review.json', { ...result, expected, metadata, observations, interactions, ownerDecision: 'PENDING_EXTERNAL_AUTHENTICATED_REVIEW', acceptance: 'NOT_AUTHORIZED' });
  }, ['reference.png', 'actual.png', 'review.json']);
}
export function packetDirectory(root, name) {
  if (!root || !path.isAbsolute(root) || !/^[a-z0-9-]+$/.test(name)) throw Error('Persistent evidence root and safe name required');
  return path.join(root, `${name}-${randomUUID()}`);
}

// Serializable browser observer. Read-only: never changes the page or capture.
export function observeAcademy() {
  const selectors = ['.academy-presentation', '.academy-builder-landing', '.built-site-header', '.built-site-footer', '.built-site-mobile-menu', '.built-site-mobile-menu > summary', '.builder-element-heading', '.builder-element-text', '.builder-element-button'];
  return { viewport: [innerWidth, innerHeight], dpr: devicePixelRatio, nodes: selectors.flatMap(selector => [...document.querySelectorAll(selector)].map(node => {
    const css = getComputedStyle(node), r = node.getBoundingClientRect();
    const lines = [];
    if (selector === '.builder-element-text' || selector === '.builder-element-heading') {
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) { const range = document.createRange(); range.selectNodeContents(walker.currentNode); for (const box of range.getClientRects()) lines.push([box.x, box.y, box.width, box.height]); }
    }
    return { selector, tag: node.tagName, rect: [r.x, r.y, r.width, r.height], lines, disabled: node.disabled ?? null, focus: node === document.activeElement, focusVisible: node.matches(':focus-visible'), hover: node.matches(':hover'), styles: Object.fromEntries(['backgroundColor', 'backgroundImage', 'color', 'border', 'borderRadius', 'outline', 'boxShadow', 'textAlign', 'direction', 'fontSize', 'lineHeight', 'display', 'transform'].map(k => [k, css[k]])) };
  })) };
}
export function semanticChecks(observation, { width, language, mode, state }) {
  const checks = [], check = (name, pass) => checks.push({ name, pass: !!pass });
  const nodes = s => observation.nodes.filter(n => n.selector === s);
  check('viewport and DPR', isDeepStrictEqual(observation.viewport, [width, 900]) && observation.dpr === 1);
  const buttons = nodes('.builder-element-button');
  check('authored and disabled buttons present', buttons.length === 2 && buttons[1].disabled === true);
  const action = buttons[0];
  check('authored state colors and gradient', action && action.styles.backgroundColor === (state === 'hover' ? 'rgb(52, 86, 120)' : 'rgb(36, 86, 120)') && action.styles.color === 'rgb(255, 255, 255)' && action.styles.backgroundImage === 'none');
  check('real keyboard focus-visible', state !== 'focus' || action?.focus && action.focusVisible);
  check('hover state', state !== 'hover' || action?.hover);
  for (const selector of ['.built-site-header', '.built-site-footer', '.builder-element-heading', '.builder-element-text']) {
    const found = nodes(selector);
    check(`${selector} visible geometry`, found.length > 0 && found.every(n => n.rect[2] > 0 && n.rect[3] > 0));
  }
  for (const n of [...nodes('.builder-element-heading'), ...nodes('.builder-element-text')]) {
    check(`${n.selector} direction`, n.styles.direction === (language === 'ar' ? 'rtl' : 'ltr'));
    check(`${n.selector} line geometry`, n.lines.length > 0 && n.lines.every(r => r.every(Number.isFinite) && r[2] > 0 && r[3] > 0));
    check(`${n.selector} authored alignment`, n.styles.textAlign === 'left');
  }
  const menu = nodes('.built-site-mobile-menu')[0];
  check('actual details menu', menu?.tag === 'DETAILS');
  if (width === 390 && menu) {
    // Global details styling follows the preserved theme-shadow-rgb token.
    const shadow = mode === 'dark' ? '4, 8, 16' : '22, 32, 51';
    check('mobile menu geometry', menu.rect[2] === 62 && menu.rect[3] === 62);
    check('mobile menu border and radius', menu.styles.border === `1px solid rgba(${shadow}, 0.12)` && menu.styles.borderRadius === '14px');
    check('mobile menu background', menu.styles.backgroundColor === `rgba(${shadow}, 0.024)`);
  }
  // Existing baseline metrics remain authoritative for theme colors, exact
  // header/footer/button rectangles, typography, outline and shadow.
  check('theme identity', mode === 'light' || mode === 'dark');
  return checks;
}
