import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cwd } from "node:process";
import { beforeEach, describe, expect, it } from "vitest";

const indexHtml = readFileSync(resolve(cwd(), "index.html"), "utf8");
const bootstrap = readFileSync(resolve(cwd(), "public/theme-bootstrap.js"), "utf8");
const packageJson = JSON.parse(readFileSync(resolve(cwd(), "package.json"), "utf8"));

describe("CSP-safe early theme bootstrap", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.colorScheme = "";
    document.body.className = "";
  });

  it("contains no executable inline scripts and loads the bootstrap from self", () => {
    const parsed = new DOMParser().parseFromString(indexHtml, "text/html");
    const scripts = [...parsed.querySelectorAll("script")];

    expect(scripts.filter((script) => !script.getAttribute("src"))).toHaveLength(0);
    expect(scripts.map((script) => script.getAttribute("src"))).toContain("/theme-bootstrap.js");
    expect(indexHtml).not.toMatch(/cdn\.jsdelivr\.net|jsdelivr/i);
    expect(packageJson.dependencies.i18next).toBeTruthy();
    expect(packageJson.dependencies["react-i18next"]).toBeTruthy();
  });

  it("applies dark mode to the root and body before application render", () => {
    localStorage.setItem("madar-theme-mode", "dark");
    Function(bootstrap)();

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(document.body.classList.contains("theme-dark")).toBe(true);
  });

  it("fails safely to light mode when storage is unavailable", () => {
    const getItem = localStorage.getItem;
    localStorage.getItem = () => {
      throw new Error("storage unavailable");
    };
    try {
      Function(bootstrap)();
    } finally {
      localStorage.getItem = getItem;
    }

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.body.classList.contains("theme-light")).toBe(true);
  });
});
