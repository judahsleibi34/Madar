import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningSettingsPage from "./ELearningSettingsPage";
import { fetchELearningSettings, saveELearningSettings, uploadELearningLogo } from "../../services/elearningSettings";

vi.mock("../../services/elearningSettings", () => ({ fetchELearningSettings: vi.fn(), saveELearningSettings: vi.fn(), uploadELearningLogo: vi.fn() }));
vi.mock("../../services/elearningCourses", () => ({ fetchCourses: vi.fn().mockResolvedValue({ courses: [], has_more: false }) }));
const settings = { enabled: false, platform_name: "Tenant Academy", description: "Welcome", course_label: "Course", section_label: "Level", lesson_label: "Topic", group_label: "Class", instructor_label: "Coach", sequential_progression: false, allow_locked_content: false, track_learner_progress: true, assessments_enabled: false, default_passing_score: 70, certificates_enabled: false, logo_url: "", primary_display_name: "Academy" };

beforeEach(async () => {
  await i18n.changeLanguage("en");
  fetchELearningSettings.mockResolvedValue({ settings, available: true });
  saveELearningSettings.mockImplementation(async (value) => ({ settings: value, available: true }));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("loads stored terminology and saves edits with success feedback", async () => {
  render(<ELearningSettingsPage user={{ id: 3, tenant_id: 17 }} />);
  expect(screen.getByRole("status").textContent).toContain("Loading");
  const name = await screen.findByLabelText("Platform Name");
  expect(name.value).toBe("Tenant Academy");
  expect(screen.getByLabelText("Course Label").value).toBe("Course");
  fireEvent.change(name, { target: { value: "New Academy" } });
  expect(screen.queryByRole("switch", { name: "Enable E-Learning" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...settings, platform_name: "New Academy" });
});

it("preserves edits after a failed save and hides internal error details", async () => {
  saveELearningSettings.mockRejectedValue(new Error("internal SQL secret"));
  render(<ELearningSettingsPage />);
  fireEvent.change(await screen.findByLabelText("Platform Name"), { target: { value: "Retry Academy" } });
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Could not save");
  expect(screen.getByLabelText("Platform Name").value).toBe("Retry Academy");
  expect(document.body.textContent).not.toContain("secret");
});

it("allows retry after loading fails", async () => {
  fetchELearningSettings.mockRejectedValueOnce(new Error("failed"));
  render(<ELearningSettingsPage />);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByLabelText("Platform Name");
  expect(fetchELearningSettings).toHaveBeenCalledTimes(2);
});

it("allows draft edits but disables saving before the schema upgrade", async () => {
  fetchELearningSettings.mockResolvedValue({ settings, available: false });
  render(<ELearningSettingsPage />);
  await screen.findByLabelText("Platform Name");
  const field = screen.getByLabelText("Platform Name");
  expect(field.closest("fieldset").disabled).toBe(false);
  fireEvent.change(field, { target: { value: "Draft Academy" } });
  expect(field.value).toBe("Draft Academy");
  expect(screen.getByRole("button", { name: "Save Changes" }).disabled).toBe(true);
  fireEvent.submit(screen.getByRole("form"));
  expect(saveELearningSettings).not.toHaveBeenCalled();
});

it("shows owner/admin access feedback", async () => {
  fetchELearningSettings.mockRejectedValue({ status: 403 });
  render(<ELearningSettingsPage />);
  expect((await screen.findByRole("alert")).textContent).toContain("Only tenant owners and admins");
  expect(screen.queryByRole("button", { name: "Save Changes" })).toBeNull();
});

it("uses Arabic labels and right-to-left layout", async () => {
  await i18n.changeLanguage("ar");
  const { container } = render(<ELearningSettingsPage />);
  await waitFor(() => expect(container.querySelector("main").getAttribute("dir")).toBe("rtl"));
  await screen.findByLabelText("اسم المنصة");
});

it("explains invalid settings without discarding edits", async () => {
  saveELearningSettings.mockRejectedValue({ status: 422 });
  render(<ELearningSettingsPage />);
  await screen.findByLabelText("Platform Name");
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  expect((await screen.findByRole("alert")).textContent).toContain("passing score must be a whole number from 0 to 100");
});


it("offers the terminology choices in separate groups and saves tenant selections for reopening", async () => {
  const user = { id: 3, tenant_id: 17 };
  const { unmount } = render(<ELearningSettingsPage user={user} />);
  await screen.findByLabelText("Course Label");
  const choices = {
    "Course Label": ["Course", "Program", "Training"],
    "Section Label": ["Level", "Section", "Module", "Unit"],
    "Lesson Label": ["Lesson", "Topic", "Chapter", "Session"],
    "Learner Group Label": ["Group", "Class", "Cohort", "Team", "Batch"],
    "Instructor Label": ["Instructor", "Teacher", "Trainer", "Tutor", "Coach"],
  };
  for (const [label, options] of Object.entries(choices)) {
    const dropdown = screen.getByRole("combobox", { name: label });
    expect(within(dropdown).getAllByRole("option").map((option) => option.value)).toEqual(options);
  }
  const hierarchy = screen.getByRole("group", { name: "Learning Content" });
  expect(within(hierarchy).getAllByRole("combobox").map((select) => select.id))
    .toEqual(["elearning-course_label", "elearning-section_label", "elearning-lesson_label"]);
  expect(screen.queryByText(/Example:/)).toBeNull();
  expect(document.querySelector(".elearning-hierarchy-example")).toBeNull();
  expect(document.getElementById("elearning-logo-help")).toBeNull();
  expect(within(screen.getByRole("group", { name: "Participants" })).getByRole("combobox", { name: "Learner Group Label" })).toBeTruthy();
  expect(within(screen.getByRole("group", { name: "Participants" })).getByRole("combobox", { name: "Instructor Label" })).toBeTruthy();
  for (const [label, value] of Object.entries({ "Course Label": "Program", "Section Label": "Module", "Lesson Label": "Session", "Learner Group Label": "Cohort", "Instructor Label": "Tutor" })) {
    fireEvent.change(screen.getByRole("combobox", { name: label }), { target: { value } });
  }
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  const savedSettings = { ...settings, course_label: "Program", section_label: "Module", lesson_label: "Session", group_label: "Cohort", instructor_label: "Tutor" };
  expect(saveELearningSettings).toHaveBeenCalledWith(savedSettings);
  unmount();
  fetchELearningSettings.mockResolvedValue({ settings: savedSettings, available: true });
  render(<ELearningSettingsPage user={user} />);
  const reopenedCourse = await screen.findByRole("combobox", { name: "Course Label" });
  expect(reopenedCourse.value).toBe("Program");
  expect(screen.getByRole("combobox", { name: "Section Label" }).value).toBe("Module");
  expect(screen.getByRole("combobox", { name: "Lesson Label" }).value).toBe("Session");
  expect(screen.getByRole("combobox", { name: "Learner Group Label" }).value).toBe("Cohort");
  expect(screen.getByRole("combobox", { name: "Instructor Label" }).value).toBe("Tutor");
});

it("preserves an older saved label until an admin selects a replacement", async () => {
  fetchELearningSettings.mockResolvedValue({ settings: { ...settings, course_label: "Workshop" }, available: true });
  render(<ELearningSettingsPage />);
  const course = await screen.findByRole("combobox", { name: "Course Label" });
  expect(course.value).toBe("Workshop");
  expect(within(course).getByRole("option", { name: "Workshop" }).disabled).toBe(true);
  expect(screen.getByText("This is your saved label. Choose an option above to replace it.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  expect(saveELearningSettings).toHaveBeenLastCalledWith({ ...settings, course_label: "Workshop" });
  fireEvent.change(course, { target: { value: "Training" } });
  expect(within(course).queryByRole("option", { name: "Workshop" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  expect(saveELearningSettings).toHaveBeenLastCalledWith({ ...settings, course_label: "Training" });
});


it("uploads a logo and applies the tenant-owned URL only when settings are saved", async () => {
  const assetUrl = "/uploads/tenant_17/builder_assets/" + "a".repeat(32) + ".png";
  uploadELearningLogo.mockResolvedValue({ asset_url: assetUrl });
  render(<ELearningSettingsPage />);
  const upload = await screen.findByLabelText("Upload Image");
  const file = new File(["image bytes"], "logo.png", { type: "image/png" });
  fireEvent.change(upload, { target: { files: [file] } });
  await waitFor(() => expect(screen.getByLabelText("Logo or Image URL").value).toBe(assetUrl));
  expect(uploadELearningLogo).toHaveBeenCalledWith(file);
  expect(saveELearningSettings).not.toHaveBeenCalled();
  expect(screen.getByAltText("Platform logo preview")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...settings, logo_url: assetUrl });
});

it("rejects unsupported or oversized uploads without changing the existing logo", async () => {
  render(<ELearningSettingsPage />);
  const upload = await screen.findByLabelText("Upload Image");
  for (const file of [new File(["svg"], "logo.svg", { type: "image/svg+xml" }), new File([new Uint8Array(5 * 1024 * 1024 + 1)], "large.png", { type: "image/png" })]) {
    fireEvent.change(upload, { target: { files: [file] } });
    expect((await screen.findByRole("alert")).textContent).toContain("up to 5 MB");
  }
  expect(uploadELearningLogo).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Logo or Image URL").value).toBe("");
});

it("keeps the current image after upload failure and blocks saving during upload", async () => {
  let rejectUpload;
  uploadELearningLogo.mockImplementation(() => new Promise((_, reject) => { rejectUpload = reject; }));
  render(<ELearningSettingsPage />);
  const upload = await screen.findByLabelText("Upload Image");
  fireEvent.change(screen.getByLabelText("Logo or Image URL"), { target: { value: "https://example.com/logo.png" } });
  fireEvent.change(upload, { target: { files: [new File(["image"], "logo.png", { type: "image/png" })] } });
  expect(screen.getByRole("button", { name: "Save Changes" }).disabled).toBe(true);
  fireEvent.submit(screen.getByRole("form"));
  expect(saveELearningSettings).not.toHaveBeenCalled();
  rejectUpload(new Error("internal secret"));
  expect((await screen.findByRole("alert")).textContent).toContain("Could not upload");
  expect(screen.getByLabelText("Logo or Image URL").value).toBe("https://example.com/logo.png");
  expect(screen.getByRole("button", { name: "Save Changes" }).disabled).toBe(false);
});


