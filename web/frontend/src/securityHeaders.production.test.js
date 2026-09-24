import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cwd } from "node:process";
import { describe, expect, it } from "vitest";

const compose = readFileSync(resolve(cwd(), "../docker-compose.yml"), "utf8");
const headersTemplate = readFileSync(resolve(cwd(), "security_headers.conf.template"), "utf8");
const storefrontHeaders = readFileSync(resolve(cwd(), "storefront_frame_headers.conf.template"), "utf8");
const adminPreviewHeaders = readFileSync(resolve(cwd(), "admin_preview_frame_headers.conf.template"), "utf8");
const nginxTemplate = readFileSync(resolve(cwd(), "nginx.conf.template"), "utf8");
const baseStyles = readFileSync(resolve(cwd(), "src/styles/core/base.css"), "utf8");

describe("production Content Security Policy", () => {
  it("frames only storefront pages from the platform and retains the default deny policy", () => {
    expect(headersTemplate).toContain("frame-ancestors 'none'");
    expect(headersTemplate).toContain("X-Frame-Options \"DENY\"");
    expect(headersTemplate).toContain("frame-src 'self' https://*.${MADAR_PUBLIC_SITE_DOMAIN}");
    expect(storefrontHeaders).toContain("frame-ancestors https://${MADAR_PUBLIC_SITE_DOMAIN}");
    expect(storefrontHeaders).not.toContain("X-Frame-Options");
    expect(storefrontHeaders).not.toContain("frame-ancestors *");
    expect(nginxTemplate).toContain("location ~ ^/shop(?:/|$)");
    expect(nginxTemplate).toContain("include /etc/nginx/conf.d/includes/storefront_frame_headers.conf;");
  });
  it("frames internal draft previews only on the platform origin", () => {
    expect(adminPreviewHeaders).toContain("frame-ancestors 'self'");
    expect(adminPreviewHeaders).toContain('X-Frame-Options "SAMEORIGIN"');
    expect(adminPreviewHeaders).toContain('X-Robots-Tag "noindex, nofollow, noarchive"');
    expect(adminPreviewHeaders).not.toContain("frame-ancestors 'none'");
    expect(adminPreviewHeaders).not.toContain('X-Frame-Options "DENY"');
    expect(adminPreviewHeaders).not.toContain("frame-ancestors *");
    expect(nginxTemplate).toMatch(/location ~ \^\/ecommerce-preview\(\?:\/\|\$\) \{\s*try_files \/index\.html =404;\s*add_header Cache-Control "no-cache, no-store, must-revalidate" always;\s*include \/etc\/nginx\/conf\.d\/includes\/admin_preview_frame_headers\.conf;/);
  });
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
    expect(renderedHeaders.match(/style-src\s+([^;]+);/)?.[1]).toBe("'self' 'unsafe-inline'");
    expect(baseStyles).not.toMatch(/fonts\.googleapis\.com|@import\s+url\(https?:\/\//);
  });
});
