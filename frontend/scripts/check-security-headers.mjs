const baseUrl = String(process.argv[2] || "").replace(/\/$/, "");

if (!/^https?:\/\/(?:127\.0\.0\.1|localhost)(?::\d+)?$/.test(baseUrl)) {
  throw new Error("edge audit requires an explicit loopback HTTP target");
}

const required = {
  "x-content-type-options": "nosniff",
  "referrer-policy": "strict-origin-when-cross-origin",
  "x-frame-options": "DENY",
  "cross-origin-opener-policy": "same-origin",
};

const response = await fetch(`${baseUrl}/`);
if (!response.ok) throw new Error(`app shell returned HTTP ${response.status}`);
for (const [name, expected] of Object.entries(required)) {
  if (response.headers.get(name) !== expected) {
    throw new Error(`${name} header mismatch`);
  }
}
const csp = response.headers.get("content-security-policy") || "";
for (const directive of ["script-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'"]) {
  if (!csp.includes(directive)) throw new Error(`CSP is missing ${directive}`);
}
if (csp.includes("'unsafe-eval'")) throw new Error("CSP must not allow unsafe-eval");
if (!/no-store/.test(response.headers.get("cache-control") || "")) {
  throw new Error("app shell must not be cached");
}
if (process.env.EXPECT_HSTS === "true" && !response.headers.get("strict-transport-security")) {
  throw new Error("HSTS was expected but is absent");
}

const html = await response.text();
const asset = html.match(/(?:src|href)="([^"]+\.(?:js|css))"/)?.[1];
if (!asset) throw new Error("could not find a built JS/CSS asset");
const assetResponse = await fetch(new URL(asset, `${baseUrl}/`));
if (!assetResponse.ok) throw new Error(`asset returned HTTP ${assetResponse.status}`);
if (!/immutable/.test(assetResponse.headers.get("cache-control") || "")) {
  throw new Error("fingerprinted asset is not immutable");
}
if (!assetResponse.headers.get("content-security-policy")) {
  throw new Error("asset response is missing security headers");
}

console.log("Frontend edge security headers passed.");
