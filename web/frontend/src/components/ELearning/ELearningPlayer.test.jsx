import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningPlayer from "./ELearningPlayer";
import * as api from "../../services/elearningPlayer";
vi.mock("../../services/elearningPlayer", () => ({ fetchMyLearning: vi.fn(), fetchLearningCourse: vi.fn(), fetchLearningLesson: vi.fn(), completeLearningLesson: vi.fn() }));
const snapshot = (completed = false) => ({ course: { id: "c", name: "English" }, progress: { progress_percent: completed ? 50 : 0, completed_lessons: completed ? 1 : 0, total_lessons: 2, progress_status: "active" }, sections: [{ id: "s", name: "Foundations", progress_percent: 0, lessons: [{ id: "l", name: "Greetings", completed, locked: false }, { id: "next", name: "Next topic", completed: false, locked: !completed }] }], continue_lesson_id: completed ? "next" : "l", lesson: { id: "l", name: "Greetings", section_name: "Foundations", completed }, blocks: [{ id: "b", type: "text", title: "Welcome", content: { version: 1, body: "Learn together", formats: ["p"], ranges: [] } }, ...["audio", "video"].map((type) => ({ id: type, type, content: {}, media: { url: "/uploads/tenant_17/builder_assets/" + "a".repeat(32) + (type === "audio" ? ".wav" : ".webm") } }))] });
function page(path = "/my-learning") { return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/my-learning/*" element={<ELearningPlayer />} /></Routes></MemoryRouter>); }
beforeEach(async () => { await i18n.changeLanguage("en"); api.fetchMyLearning.mockResolvedValue({ courses: [snapshot()], settings: { section_label: "Level", lesson_label: "Topic" }, has_more: false }); api.fetchLearningCourse.mockResolvedValue({ ...snapshot(), lesson: null }); api.fetchLearningLesson.mockResolvedValue(snapshot()); api.completeLearningLesson.mockResolvedValue(snapshot(true)); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it("opens an enrolled course and reuses all block renderers without automatic completion", async () => {
 const { container } = page(); fireEvent.click(await screen.findByRole("link", { name: "Open Course" }));
 await screen.findByRole("heading", { name: "English" }); expect(screen.getByText("0 / 2 Topics completed")).toBeTruthy(); expect(screen.getByText("Level")).toBeTruthy(); expect(screen.queryByRole("link", { name: "Next topic" })).toBeNull();
 fireEvent.click(screen.getByRole("link", { name: "Continue Learning" })); await screen.findByText("Learn together");
 expect(container.querySelector("audio")).toBeTruthy(); expect(container.querySelector("video")).toBeTruthy(); expect(container.querySelectorAll(".elearning-content-renderer")).toHaveLength(3);
 expect(api.completeLearningLesson).not.toHaveBeenCalled(); expect(screen.getByText("Next Topic is locked")).toBeTruthy();
});
it("explicit completion updates progress, unlocks Next and refreshes My Learning on return", async () => {
 page("/my-learning/courses/c/lessons/l"); fireEvent.click(await screen.findByRole("button", { name: "Mark Complete" })); await screen.findByText("50%");
 expect(api.completeLearningLesson).toHaveBeenCalledWith("c", "l"); expect(screen.getByRole("link", { name: "Next Topic" }).getAttribute("href")).toContain("/lessons/next"); expect(screen.queryByRole("button", { name: "Mark Complete" })).toBeNull();
 api.fetchMyLearning.mockResolvedValue({ courses: [snapshot(true)], settings: {}, has_more: false }); fireEvent.click(screen.getAllByRole("link", { name: "My Learning" }).at(-1));
 await screen.findByText("50%"); expect(screen.getByRole("link", { name: "Continue Learning" }).getAttribute("href")).toContain("/lessons/next");
});
it("shows global loading and enrollment empty states", async () => {
 api.fetchMyLearning.mockReturnValue(new Promise(() => {})); const { container } = page(); expect(container.querySelector(".elearning-skeleton")).toBeTruthy(); cleanup();
 api.fetchMyLearning.mockResolvedValue({ courses: [], settings: {} }); page(); await screen.findByText("No enrolled courses yet.");
});
it("keeps locked content unavailable and supports RTL", async () => {
 await i18n.changeLanguage("ar"); api.fetchLearningLesson.mockRejectedValue({ status: 403, detail: { code: "elearning_lesson_locked" } }); const { container } = page("/my-learning/courses/c/lessons/next");
 await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("أكمل الدروس السابقة")); expect(container.querySelector(".elearning-player").getAttribute("dir")).toBe("rtl"); expect(screen.queryByText("Learn together")).toBeNull();
});
it("shows completed courses and keeps completion failures retryable", async () => {
 api.fetchMyLearning.mockResolvedValue({ courses: [{ ...snapshot(true), continue_lesson_id: null, progress: { progress_percent: 100, completed_lessons: 2, total_lessons: 2, progress_status: "completed" } }], settings: {} }); page(); await screen.findByText("Completed"); expect(screen.queryByRole("link", { name: "Continue Learning" })).toBeNull(); cleanup();
 api.completeLearningLesson.mockRejectedValue({ status: 503 }); page("/my-learning/courses/c/lessons/l"); fireEvent.click(await screen.findByRole("button", { name: "Mark Complete" })); await screen.findByRole("alert"); expect(screen.getByRole("button", { name: "Mark Complete" }).disabled).toBe(false);
});
it("keeps 100% lesson progress distinct from final completion and shows locked and passed assessments", async () => {
 const current = { ...snapshot(true), lesson: null, progress: { ...snapshot(true).progress, progress_percent: 100, completion: { completed: false }, completed_lessons: 2 }, continue_lesson_id: null, continue_assessment_id: "final", assessments: [{ placement_id: "final", title: "Final Check", required_for_completion: true, locked: false, attempts: 0 }], sections: [{ ...snapshot(true).sections[0], completion: { completed: true }, assessments: [{ placement_id: "section", title: "Level Check", required_for_completion: true, passed: true, best_score: 85, locked: false }] }, { id: "locked-section", name: "Locked Level", lessons: [], assessments: [{ placement_id: "locked", title: "Locked Check", locked: true, required_for_completion: true }] }] };
 api.fetchLearningCourse.mockResolvedValue(current); page("/my-learning/courses/c"); await screen.findByText("100%"); expect(screen.getByText("Course Not Completed")).toBeTruthy(); expect(screen.getByText(/Passed — 85%/)).toBeTruthy(); expect(screen.queryByRole("link", { name: "Locked Check" })).toBeNull(); expect(screen.getByRole("link", { name: "Continue Learning" }).getAttribute("href")).toContain("/assessments/final");
});
it("uses the saved course label for formal completion on My Learning cards", async () => {
 api.fetchMyLearning.mockResolvedValue({ courses: [{ ...snapshot(true), continue_lesson_id: null, progress: { progress_percent: 100, completed_lessons: 2, total_lessons: 2, progress_status: "completed", completion: { completed: true } } }], settings: { course_label: "Program" } });
 page(); await screen.findByText("Program Completed"); expect(screen.queryByText("Course Completed")).toBeNull();
});
it("shows the issued credential CTA from the server snapshot", async () => {
 api.fetchLearningCourse.mockResolvedValue({ ...snapshot(true), lesson: null, credential: { id: "issued-credential", status: "active" } });
 page("/my-learning/courses/c");
 expect((await screen.findByRole("link", { name: "View Certificate" })).getAttribute("href")).toBe("/my-learning/certificates/issued-credential");
 expect(api.completeLearningLesson).not.toHaveBeenCalled();
});
