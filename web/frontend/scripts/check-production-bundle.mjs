import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const required = /^(1|true|yes|on)$/i.test(
  String(process.env.MADAR_REQUIRE_PRODUCTION_API_URL || "")
);

if (!required) {
  console.log("Production bundle API-origin check skipped for non-production build.");
  process.exit(0);
}

const expected = "https://api.madarportal.com";
const assets = readdirSync("dist/assets")
  .filter((name) => name.endsWith(".js"))
  .map((name) => readFileSync(join("dist/assets", name), "utf8"))
  .join("\n");

if (!assets.includes(expected)) {
  console.error("Production bundle does not contain the canonical Madar API origin.");
  process.exit(1);
}

if (/cdn\.jsdelivr\.net|static\.cloudflareinsights\.com/i.test(assets)) {
  console.error("Production bundle contains an unapproved third-party script origin.");
  process.exit(1);
}

console.log("Production bundle API-origin contract passed.");
