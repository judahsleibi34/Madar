const required = /^(1|true|yes|on)$/i.test(
  String(process.env.MADAR_REQUIRE_PRODUCTION_API_URL || "")
);

if (!required) {
  console.log("Production API origin check skipped for non-production build.");
  process.exit(0);
}

const expected = "/api";
const configured = String(process.env.VITE_API_URL || "").trim().replace(/\/+$/, "");

if (configured !== expected) {
  console.error("Production API base must use the same-origin /api reverse proxy.");
  process.exit(1);
}

console.log("Production API origin contract passed.");
