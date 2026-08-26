const required = /^(1|true|yes|on)$/i.test(
  String(process.env.MADAR_REQUIRE_PRODUCTION_API_URL || "")
);

if (!required) {
  console.log("Production API origin check skipped for non-production build.");
  process.exit(0);
}

const expected = "https://api.madarportal.com";
const configured = String(process.env.VITE_API_URL || "").trim().replace(/\/+$/, "");

if (configured !== expected) {
  console.error("Production API origin is missing or does not match the canonical Madar API origin.");
  process.exit(1);
}

console.log("Production API origin contract passed.");
