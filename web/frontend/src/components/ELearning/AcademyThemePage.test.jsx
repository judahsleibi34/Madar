import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import AcademyThemePage from "./AcademyThemePage";
import { fetchELearningSettings, saveELearningSettings, uploadELearningLogo } from "../../services/elearningSettings";
import { initializeAcademyLanding } from "../../services/elearningAcademy";
import { fetchBuilderProject, updateBuilderProject, publishBuilderProject } from "../PageBuilder/services/PageBuilder.api";

vi.mock("../../services/elearningSettings", () => ({ fetchELearningSettings: vi.fn(), saveELearningSettings: vi.fn(), uploadELearningLogo: vi.fn() }));
vi.mock("../../services/elearningAcademy", () => ({ initializeAcademyLanding: vi.fn() }));
vi.mock("../PageBuilder/services/PageBuilder.api", () => ({ fetchBuilderProject: vi.fn(), updateBuilderProject: vi.fn(), publishBuilderProject: vi.fn() }));
const settings = { platform_name: "Academy", primary_display_name: "My Academy", logo_url: "", course_label: "Course", academy_enabled: true };
const draft = { pages: [{ id: "home", sections: [{ id: "keep-content" }] }], theme: { accent: "#123456", form: { radius: 6 } }, siteChrome: { brand: "Old name", showFooter: true }, forms: [{ id: "keep-form" }] };
const record = { id: "academy-a", usage_profile: "academy", draft_revision: 7, draft_schema: draft };
function mount() { return render(<MemoryRouter><AcademyThemePage user={{ id: 1, tenant_id: 3 }} /></MemoryRouter>); }
beforeEach(async () => {
  await i18n.changeLanguage("en");
  fetchELearningSettings.mockResolvedValue({ settings, available: true, academy_management: { editor_project_id: record.id } });
  fetchBuilderProject.mockResolvedValue(record);
  updateBuilderProject.mockImplementation(async (id, payload) => ({ ...record, draft_revision: payload.expected_revision + 1, draft_schema: payload.draft_schema }));
  saveELearningSettings.mockImplementation(async value => ({ settings: value }));
  publishBuilderProject.mockResolvedValue({ success: true });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("saves the bound Academy theme and branding without changing page content, then explicitly publishes the acknowledged revision", async () => {
  mount();
  fireEvent.change(await screen.findByLabelText("Main brand color"), { target: { value: "#abcdef" } });
  fireEvent.change(screen.getByLabelText("Display Name"), { target: { value: "New name" } });
  expect(screen.getByRole("button", { name: "Publish theme" }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await screen.findByText("Theme draft and branding saved. Publish when you are ready.");
  expect(updateBuilderProject).toHaveBeenCalledWith(record.id, { expected_revision: 7, draft_schema: { ...draft, theme: { ...draft.theme, accent: "#abcdef" }, siteChrome: { ...draft.siteChrome, brand: "New name", footerStoreName: "New name", logoUrl: "" } } });
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...settings, primary_display_name: "New name" });
  expect(publishBuilderProject).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Publish theme" }));
  await screen.findByText("Website theme published successfully.");
  expect(publishBuilderProject).toHaveBeenCalledWith(record.id, 8);
});

it("blocks publishing and repeated stale writes after a revision conflict until the project is reloaded", async () => {
  updateBuilderProject.mockRejectedValue({ status: 409 });
  mount();
  fireEvent.change(await screen.findByLabelText("Main brand color"), { target: { value: "#abcdef" } });
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await screen.findByRole("alert");
  expect(saveELearningSettings).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Publish theme" }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Reload latest version" }));
  await waitFor(() => expect(fetchBuilderProject).toHaveBeenCalledTimes(2));
  expect((await screen.findByLabelText("Main brand color")).value).toBe("#123456");
});

it("reports partial branding failure and retries with the newly acknowledged draft revision", async () => {
  saveELearningSettings.mockRejectedValueOnce(new Error("private details"));
  mount();
  fireEvent.change(await screen.findByLabelText("Main brand color"), { target: { value: "#abcdef" } });
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  expect((await screen.findByRole("alert")).textContent).toContain("branding settings could not be saved");
  expect(screen.getByRole("button", { name: "Publish theme" }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await screen.findByText("Theme draft and branding saved. Publish when you are ready.");
  expect(updateBuilderProject.mock.calls[1][1].expected_revision).toBe(8);
});

it("rejects unrelated website projects before exposing editing controls", async () => {
  fetchBuilderProject.mockResolvedValue({ ...record, usage_profile: "website" });
  mount(); await screen.findByRole("alert");
  expect(screen.queryByLabelText("Main brand color")).toBeNull();
  expect(updateBuilderProject).not.toHaveBeenCalled();
});

it("uploads a validated logo and saves it in both branding and the Home Page header", async () => {
  uploadELearningLogo.mockResolvedValue({ asset_url: "/uploads/tenant_3/builder_assets/logo.png" });
  mount();
  const input = await screen.findByLabelText("Upload Image");
  fireEvent.change(input, { target: { files: [new File(["png"], "logo.png", { type: "image/png" })] } });
  await screen.findByRole("button", { name: "Remove logo" });
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await screen.findByText("Theme draft and branding saved. Publish when you are ready.");
  expect(updateBuilderProject.mock.calls[0][1].draft_schema.siteChrome.logoUrl).toBe("/uploads/tenant_3/builder_assets/logo.png");
  expect(saveELearningSettings.mock.calls[0][0].logo_url).toBe("/uploads/tenant_3/builder_assets/logo.png");
});

it("does not create projects on page load and requires an explicit setup action", async () => {
  fetchELearningSettings.mockResolvedValue({ settings, available: true });
  initializeAcademyLanding.mockResolvedValue(record);
  mount();
  const create = await screen.findByRole("button", { name: "Create Home Page" });
  expect(initializeAcademyLanding).not.toHaveBeenCalled();
  fireEvent.click(create);
  await screen.findByLabelText("Main brand color");
  expect(initializeAcademyLanding).toHaveBeenCalledTimes(1);
});

it("uses translated Arabic controls and right-to-left layout", async () => {
  await i18n.changeLanguage("ar");
  const { container } = mount();
  await screen.findByLabelText("اللون الرئيسي للهوية");
  expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
});

it("allows retrying a transient publish failure without modifying the saved draft", async () => {
  publishBuilderProject.mockRejectedValueOnce(new Error("unavailable"));
  mount(); await screen.findByLabelText("Main brand color");
  fireEvent.click(screen.getByRole("button", { name: "Publish theme" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Publish theme" }).disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Publish theme" }));
  await screen.findByText("Website theme published successfully.");
  expect(publishBuilderProject).toHaveBeenCalledTimes(2);
  expect(updateBuilderProject).not.toHaveBeenCalled();
});

it("blocks invalid hex colors from being saved and restores the stored theme", async () => {
  mount();
  fireEvent.change(await screen.findByLabelText("Main brand color"), { target: { value: "#oops" } });
  expect(screen.getByRole("alert").textContent).toContain("six hex digits");
  expect(screen.getByRole("button", { name: "Save draft" }).disabled).toBe(true);
  fireEvent.submit(screen.getByRole("form"));
  expect(updateBuilderProject).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Restore original colors" }));
  expect(screen.getByLabelText("Main brand color").value).toBe("#123456");
  expect(screen.getByRole("button", { name: "Save draft" }).disabled).toBe(false);
});
