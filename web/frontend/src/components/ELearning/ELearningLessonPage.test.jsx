import { act, cleanup, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningLessonPage from "./ELearningLessonPage";
import ContentBlockRenderer from "./content/ContentBlockRenderer";
import * as api from "../../services/elearningContent";
vi.mock("../../services/elearningContent", () => ({ fetchContent: vi.fn(), executeContentCommand: vi.fn(), uploadContentMedia: vi.fn(), fetchAudioMedia: vi.fn().mockResolvedValue({ media: [] }) }));
vi.mock("../../hooks/useELearningTerminology", () => ({ useELearningTerminology: () => ({ labels: { lesson: "Topic", section: "Level" }, loading: false }) }));
const url = "/uploads/tenant_17/builder_assets/" + "a".repeat(32);
const text = (id = "text", body = "Welcome") => ({ id, type: "text", title: "", content: { version: 1, body, formats: ["p"], ranges: [] }, position: 0, archived_at: null });
const snapshot = (blocks = [], extra = {}) => ({ revision: 1, lesson: { name: "Introducing Yourself", description: "Metadata", status: "draft" }, section: { name: "Foundation" }, editable: true, blocks, ...extra });
function page() { return render(<MemoryRouter initialEntries={["/courses/c/lessons/l"]}><Routes><Route path="/courses/:courseId/lessons/:lessonId" element={<ELearningLessonPage />} /></Routes></MemoryRouter>); }
beforeEach(async () => { await i18n.changeLanguage("en"); api.fetchContent.mockResolvedValue(snapshot()); api.executeContentCommand.mockResolvedValue(snapshot([text()], { revision: 2 })); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });
async function add(type) {
  await screen.findByText("No learning content yet.");
  fireEvent.click(screen.getAllByRole("button", { name: "Add Block" })[0]);
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: type }));
  return within(screen.getByRole("dialog"));
}
it("uses tenant labels, normalized heading and layout loading skeleton", async () => {
  let resolve; api.fetchContent.mockReturnValue(new Promise((done) => { resolve = done; }));
  const { container } = page();
  expect(container.querySelector(".elearning-skeleton")).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
  await act(async () => { resolve(snapshot()); });
  expect(screen.getByRole("heading", { name: "Lesson Builder" })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Topic Content" })).toBeTruthy();
  expect(screen.getByText("Add your first content block.")).toBeTruthy();
});
it("creates and edits formatted text through revision checked commands", async () => {
  page(); let form = await add("Text");
  expect(form.getByRole("button", { name: "Save" }).disabled).toBe(true);
  fireEvent.change(form.getByLabelText("Learning content"), { target: { value: "Hello\nPractice" } });
  fireEvent.change(form.getByLabelText("Title (optional)"), { target: { value: "Greetings" } });
  fireEvent.click(form.getByRole("button", { name: "Save" }));
  await screen.findByText("Content saved.");
  expect(api.executeContentCommand).toHaveBeenCalledWith("c", "l", { action: "create", entity_id: null, expected_revision: 1, payload: { type: "text", title: "Greetings", content: { version: 1, body: "Hello\nPractice", formats: ["p", "p"], ranges: [] } } });
  fireEvent.click(screen.getByRole("button", { name: "Edit" })); form = within(screen.getByRole("dialog"));
  fireEvent.change(form.getByLabelText("Learning content"), { target: { value: "Updated" } });
  fireEvent.click(form.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(api.executeContentCommand).toHaveBeenCalledTimes(2));
  expect(api.executeContentCommand.mock.calls[1][2]).toMatchObject({ action: "update", entity_id: "text", expected_revision: 2, payload: { content: { body: "Updated" } } });
});
it.each([["audio", "Audio / Voice", "audio/mpeg", "mp3"], ["video", "Video", "video/mp4", "mp4"]])("uploads and saves a first class %s block by managed ID", async (type, label, mime, ext) => {
  api.uploadContentMedia.mockResolvedValue({ asset_id: "managed-id", asset_url: url + "." + ext });
  page(); const form = await add(label);
  expect(form.getByRole("button", { name: "Save" }).disabled).toBe(true);
  const file = new File(["media"], "intro." + ext, { type: mime });
  fireEvent.change(form.getByLabelText("Upload media"), { target: { files: [file] } });
  await waitFor(() => expect(form.getByRole("button", { name: "Save" }).disabled).toBe(false));
  fireEvent.change(form.getByLabelText("Description / caption (optional)"), { target: { value: "Listen or watch" } });
  fireEvent.click(form.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(api.executeContentCommand).toHaveBeenCalled());
  expect(api.executeContentCommand.mock.calls[0][2].payload).toEqual({ type, title: "", media_id: "managed-id", content: { version: 1, caption: "Listen or watch" } });
  expect(api.uploadContentMedia).toHaveBeenCalledWith("c", "l", file);
});
it("rejects invalid media and keeps upload/save errors visible", async () => {
  page(); const form = await add("Audio / Voice");
  fireEvent.change(form.getByLabelText("Upload media"), { target: { files: [new File(["text"], "bad.txt", { type: "text/plain" })] } });
  expect(api.uploadContentMedia).not.toHaveBeenCalled(); expect(form.getByRole("alert").textContent).toContain("supported");
  api.uploadContentMedia.mockRejectedValue(new Error("Unavailable"));
  fireEvent.change(form.getByLabelText("Upload media"), { target: { files: [new File(["media"], "good.mp3", { type: "audio/mpeg" })] } });
  await waitFor(() => expect(form.getByRole("alert").textContent).toContain("upload failed"));
});
it("persists reorder and duplicate, confirms archive and permanent delete", async () => {
  api.fetchContent.mockResolvedValue(snapshot([text("a"), text("b", "Second")]));
  api.executeContentCommand.mockResolvedValue(snapshot([text("b", "Second"), text("a")], { revision: 2 }));
  page(); await screen.findByText("Second");
  fireEvent.click(screen.getByRole("button", { name: "Move block 2 up" }));
  await screen.findByText("Content saved.");
  expect(api.executeContentCommand.mock.calls[0][2]).toEqual({ action: "reorder", entity_id: "b", expected_revision: 1, payload: { direction: "up" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Duplicate" })[0]);
  await waitFor(() => expect(api.executeContentCommand).toHaveBeenCalledTimes(2));
  expect(api.executeContentCommand.mock.calls[1][2].action).toBe("duplicate");
  fireEvent.click(screen.getAllByRole("button", { name: "Archive" })[0]);
  expect(api.executeContentCommand).toHaveBeenCalledTimes(2);
  api.executeContentCommand.mockResolvedValue(snapshot([{ ...text("b"), archived_at: "2026-10-04" }, text("a")], { revision: 3 }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Archive" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  fireEvent.click(screen.getAllByRole("button", { name: "Delete Permanently" }).at(-1));
  expect(api.executeContentCommand).toHaveBeenCalledTimes(3);
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete Permanently" }));
  await waitFor(() => expect(api.executeContentCommand).toHaveBeenCalledTimes(4));
  expect(api.executeContentCommand.mock.calls[3][2]).toEqual({ action: "delete", entity_id: "b", expected_revision: 3, payload: { confirmed: true } });
});
it("renders reusable preview safely, including lists, audio and video", async () => {
  const blocks = [{ ...text(), title: "Instructions", content: { version: 1, body: "<script>alert(1)</script>\nOne\nTwo", formats: ["h2", "bullet", "bullet"], ranges: [{ start: 0, end: 8, fontWeight: "700" }] } }, { id: "audio", type: "audio", content: {}, media: { url: url + ".mp3", filename: "intro.mp3" } }, { id: "video", type: "video", content: {}, media: { url: url + ".mp4", filename: "intro.mp4" } }];
  api.fetchContent.mockResolvedValue(snapshot(blocks)); const { container } = page(); await screen.findByText("Instructions");
  expect(container.querySelector("script")).toBeNull(); expect(container.querySelectorAll(".elearning-text-content li")).toHaveLength(2);
  expect(container.querySelector("audio").getAttribute("src")).toContain(url); expect(container.querySelector("video").hasAttribute("controls")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Preview Topic" }));
  const preview = screen.getByRole("dialog"); expect(preview.querySelectorAll(".elearning-content-renderer")).toHaveLength(3);
  expect(preview.querySelector("script")).toBeNull(); expect(preview.querySelectorAll("li")).toHaveLength(2);
});
it("supports RTL, archived parents, failures and stale revision recovery", async () => {
  await i18n.changeLanguage("ar"); api.fetchContent.mockResolvedValue(snapshot([text()], { editable: false }));
  const { container } = page(); await waitFor(() => expect(container.querySelector(".elearning-skeleton")).toBeNull());
  expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
  expect(screen.getByRole("button", { name: "إضافة كتلة" }).disabled).toBe(true);
  cleanup(); await i18n.changeLanguage("en");
  api.fetchContent.mockRejectedValue({ status: 404 }); page(); await screen.findByRole("alert");
  expect(screen.getByRole("alert").textContent).toContain("not found");
  api.fetchContent.mockResolvedValue(snapshot([text()])); fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByText("Welcome");
  api.executeContentCommand.mockRejectedValue({ status: 409, code: "elearning_content_conflict" });
  fireEvent.click(screen.getByRole("button", { name: "Duplicate" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("another session"));
  expect(screen.getByRole("button", { name: "Edit" }).disabled).toBe(true);
});
it("handles unsupported or unsafe media without executing embeds", () => {
  const { container } = render(<><ContentBlockRenderer block={{ type: "embed", content: {} }} /><ContentBlockRenderer block={{ type: "video", content: {}, media: { url: "javascript:alert(1)" } }} /></>);
  expect(screen.getByText("This content type is not supported yet.")).toBeTruthy();
  expect(container.querySelector("video")).toBeNull(); expect(screen.getByRole("alert")).toBeTruthy();
});

it("confirms deletion of an active block", async () => {
  api.fetchContent.mockResolvedValue(snapshot([text()]));
  api.executeContentCommand.mockResolvedValue(snapshot([], { revision: 2 }));
  page(); await screen.findByText("Welcome");
  fireEvent.click(screen.getByRole("button", { name: "Delete Permanently" }));
  expect(api.executeContentCommand).not.toHaveBeenCalled();
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
  expect(screen.getByText("Welcome")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Delete Permanently" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete Permanently" }));
  await screen.findByText("No learning content yet.");
  expect(api.executeContentCommand).toHaveBeenCalledWith("c", "l", { action: "delete", entity_id: "text", expected_revision: 1, payload: { confirmed: true } });
});

it("opens the assessment builder from Add Block", async () => {
  api.fetchAudioMedia.mockResolvedValue({ media: [] }); page(); await add("Assessment");
  expect(screen.getByRole("heading", { name: "Assessment Builder" })).toBeTruthy();
  expect(screen.getByLabelText("Required for Topic Completion")).toBeTruthy();
  expect(screen.getByText("No questions yet. Add your first question.")).toBeTruthy();
});
