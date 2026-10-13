import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it } from "vitest";
import i18n from "../../i18n";
import AcademyNav from "./AcademyNav";

const site = { subdomain: "tenant", brand: "Academy", academy_registration: "open" };
const mount = chrome => render(<MemoryRouter><AcademyNav site={site} chrome={chrome} /></MemoryRouter>);
beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => cleanup());

it("keeps the shared Sign up label and icon switcher for academies without header settings", () => {
  mount(undefined);
  expect(screen.getByRole("link", { name: "Sign up" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "العربية" }).querySelector("svg")).toBeTruthy();
  expect(screen.queryByRole("group", { name: "Language" })).toBeNull();
});

it("uses the academy's own Register label and English | العربية text switcher", async () => {
  mount({ signUpLabel: { en: "Register", ar: "التسجيل" }, languageSwitcher: "text" });
  expect(screen.getByRole("link", { name: "Register" }).getAttribute("href")).toBe("/academy/tenant/login?register=1");
  const group = screen.getByRole("group", { name: "Language" });
  expect(group.textContent).toBe("English|العربية");
  expect(screen.getByRole("button", { name: "English" }).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByRole("button", { name: "العربية" }));
  expect(i18n.language.startsWith("ar")).toBe(true);
  expect(await screen.findByRole("link", { name: "التسجيل" })).toBeTruthy();
});
