import { expect } from "@playwright/test";

export const authSelectors = {
  emailInput: /email/i,
  passwordInput: /^password$/i,
  loginButton: /^log in$/i,
};

export async function expectAppShell(page) {
  await expect(page.locator("body")).toBeVisible();
  await expect(page.locator("#root")).toBeVisible();
}

export async function expectNoFrontendCrash(page) {
  await expect(page.locator("body")).not.toContainText(/unexpected application error/i);
  await expect(page.locator("body")).not.toContainText(/cannot read properties/i);
}

export async function expectMeaningfulPageContent(page) {
  await expect
    .poll(async () => {
      const text = await page.locator("body").innerText();
      return text.trim().length;
    })
    .toBeGreaterThan(20);
}

export async function expectLoginRoute(page) {
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  await expect(page.getByRole("heading", { name: /log in/i })).toBeVisible();
}
