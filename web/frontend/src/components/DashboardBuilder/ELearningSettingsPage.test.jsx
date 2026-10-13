import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningSettingsPage from "./ELearningSettingsPage";
import { fetchELearningSettings, saveELearningSettings } from "../../services/elearningSettings";

vi.mock("../../services/elearningSettings", () => ({ fetchELearningSettings: vi.fn(), saveELearningSettings: vi.fn() }));
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
  fireEvent.click(await screen.findByRole("tab", { name: "Learning" }));
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
  fireEvent.click(await screen.findByRole("tab", { name: "Learning" }));
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
  fireEvent.click(await screen.findByRole("tab", { name: "Learning" }));
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


it("shows one category at a time and preserves a combined draft across tabs", async () => {
  render(<ELearningSettingsPage />);
  const general = await screen.findByRole("tab", { name: "General", exact: true });
  expect(general.getAttribute("aria-selected")).toBe("true");
  expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
  expect(screen.queryByRole("tab", { name: "Programmes" })).toBeNull();
  fireEvent.change(screen.getByLabelText("Platform Name"), { target: { value: "Draft Academy" } });
  fireEvent.click(screen.getByRole("tab", { name: "Learning" }));
  fireEvent.change(screen.getByLabelText("Course Label"), { target: { value: "Program" } });
  fireEvent.click(general);
  expect(screen.getByLabelText("Platform Name").value).toBe("Draft Academy");
  expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...settings, platform_name: "Draft Academy", course_label: "Program" });
});

it("supports keyboard navigation between settings categories", async () => {
  render(<ELearningSettingsPage />);
  const general = await screen.findByRole("tab", { name: "General", exact: true });
  fireEvent.keyDown(general, { key: "ArrowRight" });
  const learning = screen.getByRole("tab", { name: "Learning" });
  expect(learning.getAttribute("aria-selected")).toBe("true");
  expect(document.activeElement).toBe(learning);
  fireEvent.keyDown(learning, { key: "End" });
  expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Institution" }));
});

it("keeps branding solely in Website Theme and preserves stored branding when saving settings", async () => {
  const stored = { ...settings, primary_display_name: "Theme brand", logo_url: "/uploads/tenant_17/builder_assets/" + "a".repeat(32) + ".png" };
  fetchELearningSettings.mockResolvedValue({ settings: stored, available: true });
  render(<ELearningSettingsPage />);
  await screen.findByRole("tab", { name: "General", exact: true });
  expect(screen.queryByRole("tab", { name: "Branding" })).toBeNull();
  expect(screen.queryByLabelText("Display Name")).toBeNull();
  expect(screen.queryByLabelText("Upload Image")).toBeNull();
  fireEvent.change(screen.getByLabelText("Platform Name"), { target: { value: "Renamed Academy" } });
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...stored, platform_name: "Renamed Academy" });
});
it("groups institution details and student labels while preserving the settings payload", async () => {
  render(<ELearningSettingsPage />);
  fireEvent.click(await screen.findByRole("tab", { name: "Institution" }));
  const details = screen.getByRole("group", { name: "Institution details" });
  const labels = screen.getByRole("group", { name: "Student labels" });
  fireEvent.click(screen.getByRole("switch", { name: "Enable institution classification" }));
  const name = within(details).getByLabelText("Institution name");
  expect(name.required).toBe(true);
  fireEvent.change(name, { target: { value: "Example University" } });
  fireEvent.change(within(details).getByLabelText("Verified email domains (one per line)"), { target: { value: "university.edu\ncollege.edu" } });
  fireEvent.change(within(labels).getByLabelText("Verified institution student label"), { target: { value: "University Student" } });
  fireEvent.change(within(labels).getByLabelText("Default student label"), { target: { value: "Student" } });
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...settings, institution_enabled: true, institution_name: "Example University", institution_email_domains: ["university.edu", "college.edu"], institution_student_label: "University Student", regular_student_label: "Student" });
});
