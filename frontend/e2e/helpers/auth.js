import { expect } from "@playwright/test";

import { publicRoutes } from "./routes";
import { authSelectors } from "./selectors";

export async function loginWithUi(page, { email, password }) {
  await page.goto(publicRoutes.login);
  await page.getByLabel(authSelectors.emailInput).fill(email);
  await page.getByLabel(authSelectors.passwordInput).fill(password);
  await page.getByRole("button", { name: authSelectors.loginButton }).click();
  await expect(page).toHaveURL(/\/dashboard(?:\/|\?|$)/, { timeout: 30_000 });
}

export async function storageStateForCredentials(browser, credentials) {
  const page = await browser.newPage();
  await loginWithUi(page, credentials);
  const state = await page.context().storageState();
  await page.close();
  return state;
}

// Cleanup note: Stage B tests use pre-provisioned E2E accounts supplied through
// environment variables. They do not create users, submit payments, or mutate
// production data. Use disposable staging accounts and reset them outside the
// test runner when needed.
