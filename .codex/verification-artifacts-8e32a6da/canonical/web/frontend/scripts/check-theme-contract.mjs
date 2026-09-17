import { readdirSync, readFileSync } from "node:fs";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../src/", import.meta.url));
const tokenFile = "styles/core/tokens.css";
const authoredThemeFiles = new Set([
  "components/PageBuilder/core/PageBuilder.constants.js",
  "components/PageBuilder/core/PageBuilder.theme.js",
  "components/PageBuilder/tabs/PageBuilderThemeTab.jsx",
]);
const violations = [];

function walk(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) walk(path);
    else if ([".css", ".js", ".jsx"].includes(extname(entry.name))) inspect(path);
  }
}

function inspect(path) {
  const name = relative(root, path).replaceAll("\\", "/");
  if (name === tokenFile) return;
  if (authoredThemeFiles.has(name)) return;
  // Test fixtures intentionally exercise customer-selected literal colors;
  // they are not shipped application styling and must not weaken the runtime
  // theme-token audit.
  if (/\.(?:test|spec)\.[cm]?[jt]sx?$/.test(name)) return;

  const source = readFileSync(path, "utf8");
  const checks = extname(path) === ".css"
    ? [
        [/background(?:-color)?\s*:\s*#[0-9a-f]{3,8}\b/gi, "opaque background literal"],
        [/--[\w-]*(?:bg|background|surface)[\w-]*\s*:\s*#[0-9a-f]{3,8}\b/gi, "local surface token"],
      ]
    : [
        [/background(?:Color)?\s*:\s*["']#[0-9a-f]{3,8}\b/gi, "inline opaque background literal"],
      ];

  for (const [pattern, reason] of checks) {
    for (const match of source.matchAll(pattern)) {
      const line = source.slice(0, match.index).split("\n").length;
      violations.push(`${name}:${line} ${reason}: ${match[0]}`);
    }
  }
}

walk(root);

if (violations.length) {
  console.error("Theme contract violations:\n" + violations.join("\n"));
  process.exit(1);
}

console.log("Theme contract passed: application styles contain no opaque background literals outside core tokens.");
