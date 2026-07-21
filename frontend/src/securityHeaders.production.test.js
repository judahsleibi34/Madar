import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cwd } from "node:process";
import { describe, expect, it } from "vitest";

const compose = readFileSync(resolve(cwd(), "../docker-compose.yml"), "utf8");
const headersTemplate = readFileSync(resolve(cwd(), "security_headers.conf.template"), "utf8");

describe("production Content Security Policy", () => {
  it("allows only the public production API connection origin", () => {
    const configuredOrigin = compose.match(
      /MADAR_CSP_CONNECT_SRC:\s*\$\{MADAR_CSP_CONNECT_SRC:-([^}]+)\}/,
    )?.[1];

    expect(configuredOrigin).toBe("https://api.madarportal.com");

    const renderedHeaders = headersTemplate.replace(
      "${MADAR_CSP_CONNECT_SRC}",
      configuredOrigin,
    );
    const connectSrc = renderedHeaders.match(/connect-src\s+([^;]+);/)?.[1];
    const scriptSrc = renderedHeaders.match(/script-src\s+([^;]+);/)?.[1];

    expect(connectSrc).toBe("'self' https://api.madarportal.com");
    expect(connectSrc).not.toMatch(/127\.0\.0\.1:800[12]|localhost|\*/);
    expect(scriptSrc).not.toContain("unsafe-eval");
  });
});
