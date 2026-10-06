import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import AcademyLandingPageEntry from "./AcademyLandingPageEntry";
import { initializeAcademyLanding } from "../../services/elearningAcademy";

vi.mock("../../services/elearningAcademy", () => ({ initializeAcademyLanding: vi.fn() }));
function Destination() { return <p>{useLocation().pathname}</p>; }
vi.mock("../PageBuilder", () => ({ default: () => <p>Academy editor</p> }));
function mount(path = "/e-learning/landing-page") {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/e-learning/landing-page" element={<AcademyLandingPageEntry />} />
    <Route path="/e-learning/landing-page/projects/:projectId/*" element={<AcademyLandingPageEntry />} />
    <Route path="*" element={<Destination />} />
  </Routes></MemoryRouter>);
}
beforeEach(async () => { await i18n.changeLanguage("en"); vi.resetAllMocks(); });
afterEach(cleanup);
it("opens the dedicated project returned by the authorized initializer", async () => {
  initializeAcademyLanding.mockResolvedValue({ id: "owner-academy", usage_profile: "academy" });
  mount(); await screen.findByText("Academy editor");
  expect(initializeAcademyLanding).toHaveBeenCalledTimes(2);
});
it("keeps rejected access on the entry page and retries without exposing server details", async () => {
  initializeAcademyLanding.mockRejectedValueOnce({ status: 403, message: "private record" }).mockResolvedValue({ id: "allowed-academy", usage_profile: "academy" });
  mount(); expect((await screen.findByRole("alert")).textContent).toContain("permission");
  expect(document.body.textContent).not.toContain("private record");
  expect(screen.getByRole("link").getAttribute("href")).toBe("/e-learning/academy-access");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByText("Academy editor");
});

it("refuses guessed project URLs that are not the authorized owner's Academy", async () => {
  initializeAcademyLanding.mockResolvedValue({ id: "owner-academy", usage_profile: "academy" });
  mount("/e-learning/landing-page/projects/other-academy/pages");
  await screen.findByRole("alert");
  expect(screen.queryByText("Academy editor")).toBeNull();
});

it("explains required plan access and links to My Plan on a 402", async () => {
  initializeAcademyLanding.mockRejectedValue({ status: 402, message: "private commercial details" });
  mount();
  expect((await screen.findByRole("alert")).textContent).toContain("active Builder access");
  expect(screen.getByRole("link", { name: "Review My Plan" }).getAttribute("href")).toBe("/my-plan");
  expect(document.body.textContent).not.toContain("private commercial details");
  expect(screen.queryByText("Academy editor")).toBeNull();
});

it("refuses a normal website project returned from an invalid Academy binding", async () => {
  initializeAcademyLanding.mockResolvedValue({ id: "website", usage_profile: "website" });
  mount("/e-learning/landing-page/projects/website/pages");
  await screen.findByRole("alert");
  expect(screen.queryByText("Academy editor")).toBeNull();
});
