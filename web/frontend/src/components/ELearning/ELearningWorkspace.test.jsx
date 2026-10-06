import { act, cleanup, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningWorkspace from "./ELearningWorkspace";
import { ELearningRouteSkeleton } from "./ELearningSkeleton";
import * as api from "../../services/elearningCourses";
import * as directory from "../../services/elearningDirectory";
import * as contentApi from "../../services/elearningContent";
import * as structureApi from "../../services/elearningStructure";
import { fetchCourseProgress, fetchCourseEnrollments, fetchEnrollmentCandidates, enrollCourseUsers, changeEnrollmentStatus } from "../../services/elearningParticipation";
import { fetchELearningSettings, saveELearningSettings } from "../../services/elearningSettings";
import { getELearningTerminology, elearningTerminologyGroups } from "../../config/elearningTerminology";
vi.mock("../../services/elearningCourses", () => ({ fetchCourses: vi.fn(), fetchCourse: vi.fn(), createCourse: vi.fn(), updateCourse: vi.fn(), archiveCourse: vi.fn(), deleteCourse: vi.fn(), duplicateCourse: vi.fn(), uploadCourseCover: vi.fn() }));
vi.mock("../../services/elearningSettings", () => ({ fetchELearningSettings: vi.fn(), saveELearningSettings: vi.fn(), uploadELearningLogo: vi.fn() }));
vi.mock("../../services/elearningDirectory", () => ({ fetchDirectory: vi.fn(), createDirectoryItem: vi.fn(), updateDirectoryItem: vi.fn(), archiveDirectoryItem: vi.fn() }));
vi.mock("../../services/elearningStructure", () => ({ fetchStructure: vi.fn(), fetchLesson: vi.fn(), executeStructureCommand: vi.fn() }));
vi.mock("../../services/elearningContent", () => ({ fetchContent: vi.fn(), executeContentCommand: vi.fn(), uploadContentMedia: vi.fn() }));
vi.mock("../../services/elearningParticipation", () => ({ fetchCourseProgress: vi.fn(), fetchCourseEnrollments: vi.fn(), fetchEnrollmentCandidates: vi.fn(), enrollCourseUsers: vi.fn(), changeEnrollmentStatus: vi.fn() }));
const settings = { course_label: "Program", section_label: "Module", lesson_label: "Topic", group_label: "Cohort", instructor_label: "Trainer" };
const course = { id: "course-a", name: "English", description: "Communication skills", status: "published", access_type: "paid", revision: 1, structure_revision: 1, deletion_available: true, section_count: 0, lesson_count: 0, learner_count: 0, created_at: "2026-10-04T10:00:00Z", updated_at: "2026-10-04T10:00:00Z" };
function workspace(path = "/e-learning/courses", user = { id: 1, tenant_id: "tenant-a" }) {
  return <MemoryRouter initialEntries={[path]}><Routes><Route path="/e-learning/*" element={<ELearningWorkspace user={user} />} /></Routes></MemoryRouter>;
}
beforeEach(async () => {
  await i18n.changeLanguage("en");
  fetchELearningSettings.mockResolvedValue({ settings, available: true });
  api.fetchCourses.mockResolvedValue({ courses: [course], available: true, has_more: false });
  api.fetchCourse.mockResolvedValue({ course });
  directory.fetchDirectory.mockResolvedValue({ items: [], available: true, has_more: false });
  structureApi.fetchStructure.mockResolvedValue({ available: true, revision: 1, sections: [], section_count: 0, lesson_count: 0, published_count: 0, draft_count: 0 });
  fetchCourseProgress.mockResolvedValue({ available: true, learner_count: 0, average_progress: 0, not_started_count: 0, active_count: 0, completed_count: 0, enrollments: [] });
  fetchCourseEnrollments.mockResolvedValue({ available: true, learner_count: 0, enrollment_active_count: 0, completed_count: 0, not_started_count: 0, enrollments: [] });
  fetchEnrollmentCandidates.mockResolvedValue({ users: [], has_more: false });
  contentApi.fetchContent.mockResolvedValue({ revision: 1, blocks: [], editable: true, lesson: { id: "lesson-a", name: "Introductions", status: "draft", description: "Practice greetings" }, section: { id: "section-a", name: "Foundations" } });
  structureApi.fetchLesson.mockResolvedValue({ lesson: { id: "lesson-a", name: "Introductions", description: "Practice greetings", status: "draft" }, section: { id: "section-a", name: "Foundations" } });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it.each([
  ["/e-learning/settings", ".elearning-form"],
  ["/e-learning/courses/course-a/settings", ".elearning-course-tabs"],
])("uses the matching Arabic route fallback for %s", (pathname, selector) => {
  const { container } = render(<ELearningRouteSkeleton pathname={pathname} lang="ar" label="جارٍ التحميل" />);
  expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
  expect(container.querySelector(selector)).toBeTruthy();
  expect(screen.getByRole("status").textContent).toContain("جارٍ التحميل");
  expect(screen.queryByRole("button")).toBeNull();
});
it.each([
  ["courses", "courses"],
  ["courses/course-a", "course"],
  ["courses/course-a/structure", "course"],
  ["courses/course-a/learners", "course"],
  ["courses/course-a/progress", "course"],
  ["courses/course-a/settings", "course"],
  ["courses/course-a/lessons/lesson-a", "lesson"],
  ["groups", "groups"],
  ["instructors", "instructors"],
  ["settings", "settings"],
])("shows a layout skeleton until terminology finishes loading on %s", async (path, variant) => {
  let resolveSettings;
  const pendingSettings = new Promise((resolve) => { resolveSettings = resolve; });
  fetchELearningSettings.mockReturnValue(pendingSettings);
  const { container } = render(workspace(`/e-learning/${path}`));
  await act(async () => {});
  const skeleton = container.querySelector(".elearning-skeleton");
  expect(skeleton).toBeTruthy();
  expect(skeleton.getAttribute("aria-busy")).toBe("true");
  expect(screen.getByRole("status").textContent).toContain("Loading");
  expect(screen.queryByRole("button")).toBeNull();
  expect(skeleton.querySelector(".page-header-skeleton")).toBeTruthy();
  if (variant === "courses") expect(skeleton.querySelectorAll(".elearning-course-card")).toHaveLength(4);
  if (variant === "course") expect(skeleton.querySelectorAll(".elearning-course-tabs i")).toHaveLength(7);
  if (variant === "settings") expect(skeleton.querySelectorAll(".settings-card")).toHaveLength(5);
  await act(async () => { resolveSettings({ settings, available: true }); });
  await waitFor(() => expect(container.querySelector(".elearning-skeleton")).toBeNull());
});

it("keeps course content behind the skeleton until the course request completes", async () => {
  let resolveCourse;
  api.fetchCourse.mockReturnValue(new Promise((resolve) => { resolveCourse = resolve; }));
  const { container } = render(workspace("/e-learning/courses/course-a"));
  await act(async () => {});
  expect(container.querySelector(".elearning-skeleton")).toBeTruthy();
  expect(screen.queryByText("English")).toBeNull();
  await act(async () => { resolveCourse({ course }); });
  expect(container.querySelector(".elearning-skeleton")).toBeNull();
  expect(screen.getByRole("heading", { name: "English" })).toBeTruthy();
});

it("provides defaults and explicit plurals for every controlled label", () => {
  expect(getELearningTerminology({ course_label: " ", section_label: null }).course).toBe("Course");
  expect(getELearningTerminology().plural.instructor).toBe("Instructors");
  for (const group of elearningTerminologyGroups) for (const field of group.fields) for (const option of field.options) {
    const key = field.key.replace("_label", "");
    expect(getELearningTerminology({ [field.key]: option })[key]).toBe(option);
    expect(getELearningTerminology({ [field.key]: option }).plural[key]).toBeTruthy();
  }
  expect(getELearningTerminology({ group_label: "Class", instructor_label: "Coach" }).plural).toMatchObject({ group: "Classes", instructor: "Coaches" });
});
it("keeps headings normalized while create/edit/duplicate/archive use saved labels and revisions", async () => {
  api.createCourse.mockImplementation(async (payload) => ({ course: { ...course, ...payload, id: "new", revision: 1 } }));
  api.duplicateCourse.mockResolvedValue({ course: { ...course, id: "copy", name: "Copy of English", status: "draft" } });
  api.archiveCourse.mockResolvedValue({ course: { ...course, status: "archived", revision: 2 } });
  render(workspace());
  await screen.findByText("English");
  expect(screen.getByRole("heading", { name: "Courses", level: 1 })).toBeTruthy();
  expect(screen.getByText("Modules")).toBeTruthy();
  expect(screen.getByText("Topics")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Create Program" }));
  fireEvent.change(screen.getByLabelText("Program Name"), { target: { value: "New Program" } });
  expect(screen.getByLabelText("Access Type").value).toBe("private");
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("New Program");
  expect(api.createCourse).toHaveBeenCalledWith(expect.objectContaining({ name: "New Program", status: "draft", access_type: "private" }));
  const card = screen.getByText("English").closest("article");
  fireEvent.click(within(card).getByRole("button", { name: "Duplicate" }));
  await screen.findByText("Copy of English");
  expect(api.duplicateCourse).toHaveBeenCalledWith(course);
  fireEvent.click(within(card).getByRole("button", { name: "Archive" }));
  expect(api.archiveCourse).not.toHaveBeenCalled();
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Archive" }));
  await waitFor(() => expect(api.archiveCourse).toHaveBeenCalledWith(course));
  await waitFor(() => expect(within(card).queryByRole("button", { name: "Archive" })).toBeNull());
  expect(fetchELearningSettings).toHaveBeenCalledTimes(1);
});
it("preserves edits and hides internal details after a stale edit", async () => {
  api.updateCourse.mockRejectedValue({ status: 409, message: "internal SQL" });
  render(workspace());
  fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
  fireEvent.change(screen.getByLabelText("Program Name"), { target: { value: "Revised" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Program Name").value).toBe("Revised");
  expect(api.updateCourse).toHaveBeenCalledWith("course-a", expect.objectContaining({ expected_revision: 1 }));
  expect(document.body.textContent).not.toContain("internal SQL");
});
it("opens Manage at Overview with the cover and normalized tabs", async () => {
  const cover = "/uploads/tenant_17/builder_assets/" + "a".repeat(32) + ".png";
  api.fetchCourse.mockResolvedValue({ course: { ...course, cover_asset: cover } });
  render(workspace());
  fireEvent.click(await screen.findByRole("link", { name: "Manage" }));
  expect(await screen.findByAltText("Cover for English")).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Courses", level: 1 })).toBeTruthy();
  for (const tab of ["Overview", "Structure", "Learners", "Groups", "Instructors", "Progress", "Settings"]) expect(screen.getByRole("link", { name: tab })).toBeTruthy();
  expect(screen.getByText("Modules")).toBeTruthy();
  expect(screen.getByText("Topics")).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Settings" }));
  fireEvent.click(await screen.findByRole("button", { name: "Edit Program" }));
  expect(screen.getByLabelText("Program Name").value).toBe("English");
});
it("uses normalized tabs and saved labels for structure actions", async () => {
  render(workspace("/e-learning/courses/course-a/structure"));
  expect(await screen.findByRole("button", { name: "Add Module" })).toHaveProperty("disabled", false);
  expect(screen.queryByRole("button", { name: "Add Topic" })).toBeNull();
  expect(screen.getByRole("link", { name: "Structure" })).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Overview" }));
  await screen.findByRole("link", { name: "Assigned Trainers" });
  expect(fetchELearningSettings).toHaveBeenCalledTimes(1);
});
it.each([["groups", "Groups", "Create Cohort"], ["instructors", "Instructors", "Add Trainer"]])("keeps %s heading static", async (route, title, action) => {
  render(workspace(`/e-learning/${route}`));
  expect(await screen.findByRole("button", { name: action })).toHaveProperty("disabled", false);
  expect(screen.getByRole("heading", { name: title, level: 1 })).toBeTruthy();
});
it.each([["groups", "Create Cohort", "Cohort Name"], ["instructors", "Add Trainer", "Trainer Name"]])("creates, edits and archives %s using real management actions", async (kind, action, field) => {
  const item = { id: "directory-a", name: "New record", description: "", status: "active", revision: 1, ...(kind === "instructors" ? { email: "teacher@example.com" } : {}) };
  directory.createDirectoryItem.mockResolvedValue({ item });
  directory.updateDirectoryItem.mockResolvedValue({ item: { ...item, name: "Updated record", revision: 2 } });
  directory.archiveDirectoryItem.mockResolvedValue({ item: { ...item, name: "Updated record", status: "archived", revision: 3 } });
  render(workspace(`/e-learning/${kind}`));
  fireEvent.click(await screen.findByRole("button", { name: action }));
  fireEvent.change(screen.getByLabelText(field), { target: { value: "New record" } });
  if (kind === "instructors") fireEvent.change(screen.getByLabelText("Email (optional)"), { target: { value: "teacher@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("heading", { name: "New record" });
  expect(directory.createDirectoryItem).toHaveBeenCalledWith(kind, expect.objectContaining({ name: "New record", status: "active" }));
  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  fireEvent.change(screen.getByLabelText(field), { target: { value: "Updated record" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("heading", { name: "Updated record" });
  expect(directory.updateDirectoryItem).toHaveBeenCalledWith(kind, item.id, expect.objectContaining({ expected_revision: 1 }));
  fireEvent.click(screen.getByRole("button", { name: "Archive" }));
  expect(directory.archiveDirectoryItem).not.toHaveBeenCalled();
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Archive" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(directory.archiveDirectoryItem).toHaveBeenCalledWith(kind, expect.objectContaining({ revision: 2 }));
  expect(screen.getByText("Archived")).toBeTruthy();
});
it("preserves instructor edits after a conflict and allows retry", async () => {
  const item = { id: "instructor-a", name: "Teacher", email: "", description: "", status: "active", revision: 1 };
  directory.fetchDirectory.mockResolvedValue({ items: [item], available: true, has_more: false });
  directory.updateDirectoryItem.mockRejectedValue({ status: 409, message: "internal SQL" });
  render(workspace("/e-learning/instructors"));
  fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
  fireEvent.change(screen.getByLabelText("Trainer Name"), { target: { value: "Revised teacher" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Trainer Name").value).toBe("Revised teacher");
  expect(document.body.textContent).not.toContain("internal SQL");
});
it.each(["groups", "instructors"])("fails closed before the directory migration on %s", async (kind) => {
  directory.fetchDirectory.mockResolvedValue({ items: [], available: false, has_more: false });
  render(workspace(`/e-learning/${kind}`));
  expect(await screen.findByRole("button", { name: kind === "groups" ? "Create Cohort" : "Add Trainer" })).toHaveProperty("disabled", true);
  expect(screen.getByText(/Group and instructor management is temporarily unavailable/)).toBeTruthy();
});
it("retries directory errors and keeps Arabic layout and saved labels", async () => {
  await i18n.changeLanguage("ar");
  directory.fetchDirectory.mockRejectedValueOnce({ status: 503 });
  const { container } = render(workspace("/e-learning/groups"));
  const error = await screen.findByRole("alert");
  fireEvent.click(within(error).getByRole("button"));
  await waitFor(() => expect(directory.fetchDirectory).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(container.querySelector(".elearning-skeleton")).toBeNull());
  expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
});
it("disables creation before migration and retries load failures", async () => {
  api.fetchCourses.mockRejectedValueOnce(new Error("internal failure"));
  api.fetchCourses.mockResolvedValueOnce({ courses: [], available: false, has_more: false });
  render(workspace());
  fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
  await waitFor(() => expect(api.fetchCourses).toHaveBeenCalledTimes(2));
  expect(screen.getByRole("button", { name: "Create Program" }).disabled).toBe(true);
  expect(document.body.textContent).not.toContain("internal failure");
});
it("resets terminology and data when the active tenant changes", async () => {
  const { rerender } = render(workspace());
  await screen.findByText("English");
  fetchELearningSettings.mockResolvedValue({ settings: { course_label: "Training" }, available: true });
  api.fetchCourses.mockResolvedValue({ courses: [], available: true, has_more: false });
  rerender(workspace("/e-learning/courses", { id: 1, tenant_id: "tenant-b" }));
  await screen.findByRole("button", { name: "Create Training" });
  expect(screen.queryByText("English")).toBeNull();
});

it("applies saved labels immediately when returning from Settings", async () => {
  const complete = { ...settings, enabled: false, platform_name: "Academy", description: "", primary_display_name: "", logo_url: "", sequential_progression: false, allow_locked_content: false, track_learner_progress: true, assessments_enabled: false, certificates_enabled: false, default_passing_score: 70 };
  fetchELearningSettings.mockResolvedValue({ settings: complete, available: true });
  saveELearningSettings.mockImplementation(async (saved) => ({ settings: saved, available: true }));
  render(<MemoryRouter initialEntries={["/e-learning/settings"]}><Link to="/e-learning/courses">Return to Courses</Link><Routes><Route path="/e-learning/*" element={<ELearningWorkspace user={{ id: 1, tenant_id: "tenant-a" }} />} /></Routes></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText("Course Label"), { target: { value: "Training" } });
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await screen.findByText("E-Learning settings saved successfully.");
  fireEvent.click(screen.getByRole("link", { name: "Return to Courses" }));
  expect(await screen.findByRole("button", { name: "Create Training" })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Courses", level: 1 })).toBeTruthy();
  expect(fetchELearningSettings).toHaveBeenCalledTimes(2);
});

it("uses the shared cover upload and sends its managed asset path on save", async () => {
  const cover = "/uploads/tenant_17/builder_assets/" + "a".repeat(32) + ".png";
  api.uploadCourseCover.mockResolvedValue({ asset_url: cover });
  api.createCourse.mockResolvedValue({ course: { ...course, id: "covered", name: "With Cover", cover_asset: cover } });
  render(workspace());
  fireEvent.click(await screen.findByRole("button", { name: "Create Program" }));
  const upload = screen.getByLabelText("Upload Image");
  fireEvent.change(upload, { target: { files: [new File(["image"], "cover.png", { type: "image/png" })] } });
  await screen.findByAltText("Cover image preview");
  fireEvent.change(screen.getByLabelText("Program Name"), { target: { value: "With Cover" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("With Cover");
  expect(api.createCourse).toHaveBeenCalledWith(expect.objectContaining({ cover_asset: cover }));
});

it("shows archive failures inside the confirmation dialog and allows cancellation", async () => {
  api.archiveCourse.mockRejectedValue({ status: 409 });
  render(workspace());
  fireEvent.click(await screen.findByRole("button", { name: "Archive" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.click(within(dialog).getByRole("button", { name: "Archive" }));
  expect(await within(dialog).findByRole("alert")).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByText("English")).toBeTruthy();
});

const lesson = { id: "lesson-a", section_id: "section-a", name: "Introductions", description: "Practice greetings", status: "draft", position: 0 };
const section = { id: "section-a", name: "Foundations", description: "", status: "draft", position: 0, lessons: [lesson] };
const otherSection = { id: "section-b", name: "Communication", description: "", status: "published", position: 1, lessons: [] };
function snapshot(sections, revision = 1) {
  return { available: true, revision, sections, section_count: sections.filter((item) => item.status !== "archived").length, lesson_count: sections.filter((item) => item.status !== "archived").flatMap((item) => item.lessons).filter((item) => item.status !== "archived").length, published_count: 0, draft_count: 1 };
}
function openActions(name) {
  const menu = screen.getByLabelText(`Actions for ${name}`).closest("details");
  menu.open = true;
  return within(menu);
}
it("creates generic sections and lessons and uses the updated structure revision", async () => {
  structureApi.executeStructureCommand.mockResolvedValueOnce(snapshot([{ ...section, lessons: [] }], 2)).mockResolvedValueOnce(snapshot([section], 3));
  render(workspace("/e-learning/courses/course-a/structure"));
  fireEvent.click(await screen.findByRole("button", { name: "Add Module" }));
  fireEvent.change(screen.getByLabelText("Module Name"), { target: { value: "Foundations" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("heading", { name: "Foundations" });
  expect(structureApi.executeStructureCommand).toHaveBeenNthCalledWith(1, "course-a", { action: "create_section", expected_revision: 1, payload: { name: "Foundations", description: "", status: "draft" } });
  fireEvent.click(screen.getByRole("button", { name: "Add Topic" }));
  fireEvent.change(screen.getByLabelText("Topic Name"), { target: { value: "Introductions" } });
  expect(screen.getByLabelText("Status").value).toBe("draft");
  expect(screen.getByLabelText("Topic Short Description")).toBeTruthy();
  expect(screen.queryByText("Video Lesson")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("link", { name: "Introductions" });
  expect(structureApi.executeStructureCommand).toHaveBeenNthCalledWith(2, "course-a", { action: "create_lesson", expected_revision: 2, payload: { name: "Introductions", description: "", status: "draft", section_id: section.id } });
  fireEvent.click(screen.getByRole("link", { name: "Overview" }));
  expect(screen.getByText("Topics").closest("div").textContent).toContain("1");
});
it("persists reordering and moves a lesson without changing its identity", async () => {
  structureApi.fetchStructure.mockResolvedValue(snapshot([section, otherSection]));
  structureApi.executeStructureCommand.mockResolvedValueOnce(snapshot([{ ...otherSection, position: 0 }, { ...section, position: 1 }], 2)).mockResolvedValueOnce(snapshot([{ ...otherSection, lessons: [{ ...lesson, section_id: otherSection.id }] }, { ...section, lessons: [] }], 3));
  render(workspace("/e-learning/courses/course-a/structure"));
  fireEvent.click(await screen.findByRole("button", { name: "Move Foundations down" }));
  await waitFor(() => expect(structureApi.executeStructureCommand).toHaveBeenCalledWith("course-a", { action: "reorder_section", entity_id: section.id, expected_revision: 1, payload: { direction: "down" } }));
  await screen.findByText("Learning structure updated.");
  fireEvent.click(openActions("Introductions").getByRole("button", { name: "Move" }));
  expect(screen.getByRole("combobox").value).toBe(otherSection.id);
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Move" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(structureApi.executeStructureCommand).toHaveBeenLastCalledWith("course-a", { action: "move_lesson", entity_id: lesson.id, expected_revision: 2, payload: { section_id: otherSection.id } });
  expect(screen.getByRole("link", { name: "Introductions" }).getAttribute("href")).toBe("/e-learning/courses/course-a/lessons/lesson-a");
  expect(screen.getByRole("link", { name: "Introductions" }).closest("article").textContent).toContain("Communication");
});
it("requires deletion confirmation and protects sections containing lessons", async () => {
  structureApi.fetchStructure.mockResolvedValue(snapshot([section, otherSection]));
  structureApi.executeStructureCommand.mockResolvedValue(snapshot([section], 2));
  render(workspace("/e-learning/courses/course-a/structure"));
  await screen.findByRole("heading", { name: "Foundations" });
  expect(openActions("Foundations").getByRole("button", { name: "Delete" }).disabled).toBe(true);
  fireEvent.click(openActions("Communication").getByRole("button", { name: "Delete" }));
  expect(structureApi.executeStructureCommand).not.toHaveBeenCalled();
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(structureApi.executeStructureCommand).toHaveBeenCalledWith("course-a", { action: "delete_section", entity_id: otherSection.id, expected_revision: 1, payload: { confirmed: true } });
  expect(screen.queryByRole("heading", { name: "Communication" })).toBeNull();
});
it("preserves structure form input after a conflict and permits a fresh reload", async () => {
  structureApi.fetchStructure.mockResolvedValue(snapshot([section]));
  structureApi.executeStructureCommand.mockRejectedValue({ status: 409, message: "internal SQL secret" });
  render(workspace("/e-learning/courses/course-a/structure"));
  await screen.findByRole("heading", { name: "Foundations" });
  fireEvent.click(openActions("Foundations").getByRole("button", { name: "Edit" }));
  fireEvent.change(screen.getByLabelText("Module Name"), { target: { value: "New foundations" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Module Name").value).toBe("New foundations");
  expect(document.body.textContent).not.toContain("internal SQL secret");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "Reload structure" }));
  await waitFor(() => expect(structureApi.fetchStructure).toHaveBeenCalledTimes(2));
});
it("opens the authorized generic lesson builder and returns to Structure", async () => {
  render(workspace("/e-learning/courses/course-a/lessons/lesson-a"));
  expect(await screen.findByRole("heading", { name: "Lesson Builder" })).toBeTruthy();
  expect(contentApi.fetchContent).toHaveBeenCalledWith("course-a", "lesson-a");
  expect(screen.getByText("No learning content yet.")).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Topic Content" })).toBeTruthy();
  expect(screen.getAllByRole("button", { name: "Add Block" }).every((button) => !button.disabled)).toBe(true);
  fireEvent.click(screen.getByRole("link", { name: "Back to Structure" }));
  expect(await screen.findByRole("button", { name: "Add Module" })).toBeTruthy();
});
it("gates Structure before its migration and keeps Arabic hierarchy direction", async () => {
  await i18n.changeLanguage("ar");
  structureApi.fetchStructure.mockResolvedValue({ ...snapshot([]), available: false });
  const { container } = render(workspace("/e-learning/courses/course-a/structure"));
  await waitFor(() => expect(container.querySelector(".elearning-skeleton")).toBeNull());
  expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
  expect(container.querySelector(".elearning-structure-header button").disabled).toBe(true);
  expect(structureApi.executeStructureCommand).not.toHaveBeenCalled();
});

it("displays backend-derived learner and section progress using saved labels", async () => {
  fetchCourseProgress.mockResolvedValue({ available: true, learner_count: 1, average_progress: 50, not_started_count: 0, active_count: 1, completed_count: 0, enrollments: [{ id: "enrollment-a", name: "Test Learner 01", email: "learner01@example.invalid", access_source: "manual", completed_lessons: 1, total_lessons: 2, progress_percent: 50, progress_status: "active", sections: [{ id: "section-a", name: "Foundations", status: "published", total_lessons: 2, completed_lessons: 1, progress_percent: 50, lessons: [{ id: "lesson-a", name: "Greetings", completed: true }, { id: "lesson-b", name: "Questions", completed: false }] }] }] });
  render(workspace("/e-learning/courses/course-a/progress"));
  await screen.findByRole("rowheader", { name: /Test Learner 01/ });
  expect(fetchCourseProgress).toHaveBeenCalledWith("course-a");
  expect(screen.getByText("1 / 2")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "View Progress for Test Learner 01" }));
  const detail = screen.getByRole("dialog");
  expect(within(detail).getAllByText("1 / 2 Topics completed")).toHaveLength(2);
  expect(within(detail).getByRole("progressbar", { name: "Progress for Test Learner 01" }).value).toBe(50);
  expect(screen.getByText("Progress by Modules")).toBeTruthy();
  expect(within(detail).getByRole("heading", { name: "Module: Foundations" })).toBeTruthy();
  expect(within(detail).getByText("Topic: Greetings")).toBeTruthy();
  expect(within(detail).getByText("Published")).toBeTruthy();
});
it("retries participation errors without showing internal details", async () => {
  fetchCourseEnrollments.mockRejectedValueOnce({ status: 500, message: "internal SQL" });
  render(workspace("/e-learning/courses/course-a/learners"));
  const error = await screen.findByRole("alert");
  expect(document.body.textContent).not.toContain("internal SQL");
  fireEvent.click(within(error).getByRole("button", { name: "Try again" }));
  await screen.findByText("No learners enrolled yet.");
  expect(fetchCourseEnrollments).toHaveBeenCalledTimes(2);
});

it("requires the exact course name before permanently deleting a card", async () => {
  api.deleteCourse.mockResolvedValue({ id: course.id, deleted: true });
  render(workspace());
  fireEvent.click(await screen.findByRole("button", { name: "Delete", exact: true }));
  const dialog = screen.getByRole("dialog");
  const confirm = within(dialog).getByRole("button", { name: "Delete" });
  expect(confirm.disabled).toBe(true);
  expect(within(dialog).getByText(/completion history/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Type English to confirm"), { target: { value: "Wrong" } });
  expect(confirm.disabled).toBe(true);
  expect(api.deleteCourse).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Type English to confirm"), { target: { value: "English" } });
  fireEvent.click(confirm);
  await screen.findByText("Program deleted.");
  expect(api.deleteCourse).toHaveBeenCalledWith(course, "English");
  expect(screen.queryByText("English")).toBeNull();
});
it("keeps the card and typed confirmation when course deletion fails", async () => {
  api.deleteCourse.mockRejectedValue({ status: 409 });
  render(workspace());
  fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
  fireEvent.change(screen.getByLabelText("Type English to confirm"), { target: { value: "English" } });
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Type English to confirm").value).toBe("English");
  expect(screen.getByRole("heading", { name: "English" })).toBeTruthy();
});

it("filters the progress table while preserving the full-course overview", async () => {
  const learners = [
    { id: "new", name: "New learner", email: "new@example.invalid", completed_lessons: 0, total_lessons: 2, progress_percent: 0, progress_status: "not_started", sections: [] },
    { id: "active", name: "Active learner", email: "active@example.invalid", completed_lessons: 1, total_lessons: 2, progress_percent: 50, progress_status: "active", sections: [] },
    { id: "done", name: "Finished learner", email: "done@example.invalid", completed_lessons: 2, total_lessons: 2, progress_percent: 100, progress_status: "completed", sections: [] },
  ];
  fetchCourseProgress.mockResolvedValue({ learner_count: 3, average_progress: 50, completed_count: 1, active_count: 1, not_started_count: 1, enrollments: learners });
  render(workspace("/e-learning/courses/course-a/progress"));
  await screen.findByRole("rowheader", { name: /New learner/ });
  fireEvent.change(screen.getByRole("combobox", { name: "Progress status" }), { target: { value: "active" } });
  expect(screen.getAllByRole("rowheader")).toHaveLength(1);
  expect(screen.getByRole("rowheader", { name: /Active learner/ })).toBeTruthy();
  expect(screen.getByText("Showing 1 of 3 learners")).toBeTruthy();
  expect(screen.getByText("Total enrolled learners").nextSibling.textContent).toBe("3");
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "done@example.invalid" } });
  expect(screen.getByText("No learners match these filters.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getAllByRole("rowheader")).toHaveLength(3);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: " DONE@EXAMPLE.INVALID " } });
  expect(screen.getByRole("rowheader", { name: /Finished learner/ })).toBeTruthy();
  expect(screen.getByRole("progressbar", { name: "Progress for Finished learner" }).value).toBe(100);
});
it("uses eligible sections for current progress and hides draft details", async () => {
  const sections = [
    { id: "draft", name: "Hidden draft", status: "draft", total_lessons: 0, completed_lessons: 0, progress_percent: 0, lessons: [] },
    { id: "done", name: "Completed section", status: "published", total_lessons: 1, completed_lessons: 1, progress_percent: 100, lessons: [{ id: "one", name: "Completed topic", completed: true }] },
    { id: "next", name: "Next section", status: "published", total_lessons: 1, completed_lessons: 0, progress_percent: 0, lessons: [{ id: "two", name: "Next topic", completed: false }] },
  ];
  fetchCourseProgress.mockResolvedValue({ learner_count: 1, average_progress: 50, completed_count: 0, active_count: 1, not_started_count: 0, enrollments: [{ id: "active", name: "Active learner", email: "active@example.invalid", completed_lessons: 1, total_lessons: 2, progress_percent: 50, progress_status: "active", sections }] });
  render(workspace("/e-learning/courses/course-a/progress"));
  await screen.findByRole("rowheader", { name: /Active learner/ });
  expect(screen.getByText("Next section")).toBeTruthy();
  expect(screen.getByText("Unavailable")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "View Progress for Active learner" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).queryByText(/Hidden draft/)).toBeNull();
  expect(within(dialog).getByText("Topic: Completed topic")).toBeTruthy();
  expect(within(dialog).getByText("Topic: Next topic")).toBeTruthy();
  expect(within(dialog).getByText("100%")).toBeTruthy();
  expect(within(dialog).getByText("0%")).toBeTruthy();
  fireEvent.click(within(dialog).getAllByRole("button", { name: "Close" }).at(-1));
  expect(screen.queryByRole("dialog")).toBeNull();
});

const enrollmentFixture = { id: "enrollment-a", learner_id: "learner-a", user_id: 3, name: "Existing User", email: "existing@example.invalid", enrollment_status: "active", learner_status: "active", enrolled_at: "2026-10-04T10:00:00Z", access_source: "manual", completed_lessons: 1, total_lessons: 2, progress_percent: 50, progress_status: "active", sections: [{ id: "section-a", name: "Foundations", status: "published", total_lessons: 2, completed_lessons: 1, progress_percent: 50, lessons: [{ id: "lesson-a", name: "Greetings", completed: true }] }], group_id: null, payment_status: null };
const enrollmentReport = (rows) => ({ available: true, learner_count: rows.length, enrollment_active_count: rows.filter((row) => row.enrollment_status === "active").length, completed_count: rows.filter((row) => row.progress_status === "completed").length, not_started_count: rows.filter((row) => row.progress_status === "not_started").length, enrollments: rows });
it("shows enrollment records with independent access and progress filters and shared details", async () => {
  fetchCourseEnrollments.mockResolvedValue(enrollmentReport([enrollmentFixture, { ...enrollmentFixture, id: "cancelled", name: "Cancelled Learner", email: "cancelled@example.invalid", enrollment_status: "archived", progress_percent: 100, progress_status: "completed", completed_lessons: 2 }]));
  render(workspace("/e-learning/courses/course-a/learners"));
  await screen.findByRole("rowheader", { name: "Existing User" });
  expect(screen.getByRole("combobox", { name: "Cohort" }).disabled).toBe(true);
  expect(screen.getAllByText("Not connected").length).toBeGreaterThan(0);
  fireEvent.change(screen.getByRole("combobox", { name: "Enrollment status" }), { target: { value: "archived" } });
  expect(screen.getAllByRole("rowheader")).toHaveLength(1);
  expect(screen.getByRole("rowheader", { name: "Cancelled Learner" })).toBeTruthy();
  fireEvent.change(screen.getByRole("combobox", { name: "Progress status" }), { target: { value: "active" } });
  expect(screen.getByText("No learners match these filters.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: " EXISTING@EXAMPLE.INVALID " } });
  expect(screen.getAllByRole("rowheader")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "View Progress for Existing User" }));
  const detail = screen.getByRole("dialog");
  expect(within(detail).getByRole("heading", { name: "Module: Foundations" })).toBeTruthy();
  expect(within(detail).getByText("Topic: Greetings")).toBeTruthy();
  expect(within(detail).getByText("existing@example.invalid")).toBeTruthy();
});
it("requires confirmation for suspension and sends the current enrollment status", async () => {
  fetchCourseEnrollments.mockResolvedValueOnce(enrollmentReport([enrollmentFixture])).mockResolvedValue(enrollmentReport([{ ...enrollmentFixture, enrollment_status: "suspended" }]));
  changeEnrollmentStatus.mockResolvedValue({ enrollment_id: enrollmentFixture.id });
  render(workspace("/e-learning/courses/course-a/learners"));
  fireEvent.click(await screen.findByLabelText("Actions for Existing User"));
  fireEvent.click(screen.getByRole("button", { name: "Suspend Access" }));
  expect(changeEnrollmentStatus).not.toHaveBeenCalled();
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText(/Madar account and completed lessons will be retained/)).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Suspend Access" }));
  await waitFor(() => expect(within(screen.getByRole("table")).getByText("Suspended")).toBeTruthy());
  fireEvent.click(screen.getByLabelText("Actions for Existing User"));
  expect(screen.getByRole("button", { name: "Reactivate" })).toBeTruthy();
  expect(changeEnrollmentStatus).toHaveBeenCalledWith("course-a", enrollmentFixture, "suspend");
  expect(screen.getByRole("progressbar", { name: "Progress for Existing User" }).value).toBe(50);
});
it("bulk enrolls existing tenant users and disables already-enrolled candidates", async () => {
  fetchEnrollmentCandidates.mockResolvedValue({ users: [{ id: 3, name: "Existing User", email: "existing@example.invalid", already_enrolled: false }, { id: 4, name: "Second User", email: "second@example.invalid", already_enrolled: false }, { id: 5, name: "Already Enrolled", email: "already@example.invalid", already_enrolled: true }], has_more: false });
  enrollCourseUsers.mockResolvedValue({ enrollment_ids: ["one", "two"] });
  render(workspace("/e-learning/courses/course-a/learners"));
  fireEvent.click(await screen.findByRole("button", { name: "Enroll Learner" }));
  const dialog = screen.getByRole("dialog");
  const existing = await within(dialog).findByRole("checkbox", { name: /Existing User/ });
  expect(within(dialog).getByRole("checkbox", { name: /Already Enrolled/ }).disabled).toBe(true);
  expect(within(dialog).getByRole("button", { name: "Enroll selected users" }).disabled).toBe(true);
  fireEvent.click(existing); fireEvent.click(within(dialog).getByRole("checkbox", { name: /Second User/ }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Enroll selected users" }));
  await waitFor(() => expect(enrollCourseUsers).toHaveBeenCalledWith("course-a", [3, 4], "manual"));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

it("shows tenant-labeled order and read-only persisted positions without sending arbitrary offsets", async () => {
  structureApi.fetchStructure.mockResolvedValue(snapshot([section, otherSection]));
  render(workspace("/e-learning/courses/course-a/structure"));
  await screen.findByRole("heading", { name: "Foundations" });
  expect(screen.getByText("Module 1")).toBeTruthy();
  expect(screen.getByText("Module 2")).toBeTruthy();
  expect(screen.getByText("Topic 1")).toBeTruthy();
  fireEvent.click(openActions("Introductions").getByRole("button", { name: "Edit Details" }));
  expect(screen.getByLabelText("Topic Short Description").value).toBe("Practice greetings");
  expect(screen.getByRole("spinbutton", { name: "Position" }).value).toBe("1");
  expect(screen.getByRole("spinbutton", { name: "Position" }).readOnly).toBe(true);
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getAllByRole("button", { name: "Add Module" }).at(-1));
  expect(screen.getByRole("spinbutton", { name: "Position" }).value).toBe("3");
  expect(screen.getByRole("heading", { name: "Structure" })).toBeTruthy();
  expect(structureApi.executeStructureCommand).not.toHaveBeenCalled();
});

it.each(["lesson name", "Open / Edit Content", "actions menu"])("reaches the builder from Courses → Manage → Structure via %s", async (entry) => {
  structureApi.fetchStructure.mockResolvedValue(snapshot([section]));
  render(workspace());
  fireEvent.click(await screen.findByRole("link", { name: "Manage" }));
  fireEvent.click(await screen.findByRole("link", { name: "Structure", exact: true }));
  await screen.findByRole("link", { name: "Introductions" });
  if (entry === "lesson name") fireEvent.click(screen.getByRole("link", { name: "Introductions" }));
  else if (entry === "actions menu") fireEvent.click(openActions("Introductions").getByRole("link", { name: "Open / Edit Content" }));
  else fireEvent.click(screen.getAllByRole("link", { name: "Open / Edit Content" })[0]);
  expect(await screen.findByRole("heading", { name: "Lesson Builder" })).toBeTruthy();
  expect(contentApi.fetchContent).toHaveBeenCalledWith("course-a", "lesson-a");
  expect(screen.getByRole("heading", { name: "Topic Content" })).toBeTruthy();
  expect(screen.getByText("Add your first content block.")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Program" }).getAttribute("href")).toBe("/e-learning/courses/course-a");
  fireEvent.click(screen.getAllByRole("button", { name: "Add Block" })[0]);
  const choices = within(screen.getByRole("dialog"));
  for (const type of ["Text", "Audio / Voice", "Video"]) expect(choices.getByRole("button", { name: type })).toBeTruthy();
  fireEvent.click(choices.getByRole("button", { name: "Close" }));
  fireEvent.click(screen.getByRole("link", { name: "Back to Structure" }));
  expect(await screen.findByRole("link", { name: "Introductions" })).toBeTruthy();
});

it("adds a Manual grant independently of an existing Free grant", async () => {
  api.fetchCourse.mockResolvedValue({ course: { ...course, access_type: "free" } });
  fetchEnrollmentCandidates.mockResolvedValue({ users: [{ id: 3, name: "Existing Free User", email: "free@example.invalid", already_enrolled: true, individual_sources: ["free"] }], has_more: false });
  enrollCourseUsers.mockResolvedValue({ enrollment_ids: ["existing"] });
  render(workspace("/e-learning/courses/course-a/learners"));
  fireEvent.click(await screen.findByRole("button", { name: "Enroll Learner" }));
  const dialog = within(screen.getByRole("dialog"));
  await dialog.findByText("Existing Free User");
  expect(dialog.getByRole("checkbox").disabled).toBe(true);
  fireEvent.change(dialog.getByLabelText("Access source"), { target: { value: "manual" } });
  await waitFor(() => expect(dialog.getByRole("checkbox").disabled).toBe(false));
  fireEvent.click(dialog.getByRole("checkbox"));
  fireEvent.click(dialog.getByRole("button", { name: "Enroll selected users" }));
  await waitFor(() => expect(enrollCourseUsers).toHaveBeenCalledWith("course-a", [3], "manual"));
});


it("enrolls more than 100 selected users in API batches and retries only unfinished users", async () => {
  const users = Array.from({ length: 101 }, (_, index) => ({ id: index + 10, name: `Bulk learner ${index}`, email: `bulk${index}@example.invalid`, already_enrolled: false }));
  fetchEnrollmentCandidates.mockResolvedValue({ users, has_more: false });
  enrollCourseUsers.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error("Temporary failure")).mockResolvedValueOnce({});
  render(workspace("/e-learning/courses/course-a/learners"));
  fireEvent.click(await screen.findByRole("button", { name: "Enroll Learner" }));
  const dialog = screen.getByRole("dialog");
  await within(dialog).findByRole("checkbox", { name: /Bulk learner 100/ });
  for (const checkbox of within(dialog).getAllByRole("checkbox")) fireEvent.click(checkbox);
  expect(within(dialog).getAllByRole("checkbox").filter((checkbox) => checkbox.checked)).toHaveLength(101);
  const submit = within(dialog).getByRole("button", { name: "Enroll selected users" });
  fireEvent.click(submit);
  await within(dialog).findByRole("alert");
  expect(enrollCourseUsers.mock.calls[0]).toEqual(["course-a", users.slice(0, 100).map((user) => user.id), "manual"]);
  expect(enrollCourseUsers.mock.calls[1]).toEqual(["course-a", [110], "manual"]);
  expect(within(dialog).getAllByRole("checkbox").filter((checkbox) => checkbox.checked)).toHaveLength(1);
  expect(within(dialog).getAllByRole("checkbox").filter((checkbox) => checkbox.disabled)).toHaveLength(100);
  fireEvent.click(submit);
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(enrollCourseUsers.mock.calls[2]).toEqual(["course-a", [110], "manual"]);
});
