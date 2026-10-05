import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../../i18n";
import ContentBlockRenderer from "./ContentBlockRenderer";
import AssessmentBuilder from "./AssessmentBuilder";
import * as api from "../../../services/elearningAssessments";
vi.mock("../../../services/elearningAssessments", () => ({ loadAssessment: vi.fn(), createAssessment: vi.fn(), commandAssessment: vi.fn(), learnerAssessment: vi.fn(), startAssessment: vi.fn(), submitAssessment: vi.fn() }));
vi.mock("../../../services/elearningContent", () => ({ fetchAudioMedia: vi.fn().mockResolvedValue({ media: [{ id: "media", filename: "Sound.wav", url: "/uploads/tenant_1/builder_assets/" + "a".repeat(32) + ".wav" }] }), uploadContentMedia: vi.fn() }));
vi.mock("../../../hooks/useELearningTerminology", () => ({ useELearningTerminology: () => ({ labels: { lesson: "Topic" } }) }));
const assessment = { title: "Practice Check", instructions: "Answer all", passing_score: 70, max_attempts: 3, question_count: 4, required_for_completion: true, revision: 1, status: "draft" };
const block = { id: "b", type: "assessment", assessment };
const questions = [{ id: "q1", type: "multiple_choice", prompt: "Choose", points: 1, config: { options: [{ id: "o1", label: "Hello" }, { id: "o2", label: "Bye" }] } }, { id: "q2", type: "true_false", prompt: "True?", points: 1, config: {} }, ...["matching", "listen_match"].map((type, i) => ({ id: `q${i + 3}`, type, prompt: type, points: 1, config: { prompts: [{ id: "p1", label: "Left", media: { url: "/uploads/tenant_1/builder_assets/" + "a".repeat(32) + ".wav" } }, { id: "p2", label: "Other", media: { url: "/uploads/tenant_1/builder_assets/" + "a".repeat(32) + ".wav" } }], targets: [{ id: "t1", label: "Right" }, { id: "t2", label: "Next" }] } }))];
const initial = { assessment, summary: { attempts: 0, best_score: null, passed: false, remaining_attempts: 3 }, attempt: null };
beforeEach(async () => { await i18n.changeLanguage("en"); api.learnerAssessment.mockResolvedValue(initial); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it("renders an author summary and safe shared preview without creating attempts", async () => {
  const view = render(<ContentBlockRenderer block={block} />); expect(screen.getByText("Practice Check")).toBeTruthy(); expect(api.learnerAssessment).not.toHaveBeenCalled(); view.unmount();
  api.loadAssessment.mockResolvedValue({ assessment, questions }); render(<ContentBlockRenderer block={block} context="preview" courseId="c" lessonId="l" />);
  expect(await screen.findByText("Question 1: Choose")).toBeTruthy(); expect(screen.getAllByRole("combobox")).toHaveLength(4); expect(api.startAssessment).not.toHaveBeenCalled();
});
it("uses a skeleton, typed answers, authoritative result, retry and attempt limit", async () => {
  api.startAssessment.mockResolvedValue({ ...initial, attempt: { id: "attempt", status: "in_progress", questions } });
  api.submitAssessment.mockResolvedValue({ ...initial, attempt: { id: "attempt", status: "submitted", score_percentage: 50, passed: false, attempt_number: 1, passing_score: 70 }, summary: { ...initial.summary, attempts: 1, remaining_attempts: 2 } });
  const changed = vi.fn(); const view = render(<ContentBlockRenderer block={block} context="learner" courseId="c" lessonId="l" onAssessmentChange={changed} />);
  expect(view.container.querySelector(".elearning-skeleton")).toBeTruthy(); fireEvent.click(await screen.findByRole("button", { name: "Start Assessment" }));
  fireEvent.click(await screen.findByLabelText("Hello")); fireEvent.click(screen.getByLabelText("True")); screen.getAllByRole("combobox").forEach((select, i) => fireEvent.change(select, { target: { value: i % 2 ? "t2" : "t1" } }));
  fireEvent.click(screen.getByRole("button", { name: "Submit Assessment" })); await screen.findByText("Score: 50% — Not Passed");
  expect(api.submitAssessment).toHaveBeenCalledWith("c", "l", "b", "attempt", { q1: { option_id: "o1" }, q2: { value: true }, q3: { matches: { p1: "t1", p2: "t2" } }, q4: { matches: { p1: "t1", p2: "t2" } } });
  expect(changed).toHaveBeenCalled(); expect(screen.getByRole("button", { name: "Try Again" })).toBeTruthy(); view.unmount();
  api.learnerAssessment.mockResolvedValue({ ...initial, summary: { remaining_attempts: 0, best_score: 100, passed: true }, attempt: { status: "submitted", score_percentage: 100, passed: true, attempt_number: 3, passing_score: 70 } });
  render(<ContentBlockRenderer block={block} context="learner" courseId="c" lessonId="l" />); await screen.findByText("Attempt limit reached."); expect(screen.getByText("Score: 100% — Passed")).toBeTruthy();
});
it("creates all question types with real forms and tenant completion terminology", async () => {
  render(<AssessmentBuilder courseId="c" lessonId="l" revision={4} onClose={vi.fn()} onSaved={vi.fn()} />);
  await screen.findByText("No questions yet. Add your first question."); expect(screen.getByLabelText("Required for Topic Completion")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Assessment Title"), { target: { value: "Practice" } }); fireEvent.click(screen.getByLabelText("Required for Topic Completion"));
  for (const type of ["Multiple Choice", "True / False", "Matching", "Listen & Match"]) {
    fireEvent.click(screen.getByRole("button", { name: type })); fireEvent.change(screen.getByLabelText("Question"), { target: { value: type } });
    if (type === "Multiple Choice") { for (let i = 1; i <= 2; i++) fireEvent.change(screen.getByLabelText(`Option ${i}`), { target: { value: `Choice ${i}` } }); }
    if (type === "Matching" || type === "Listen & Match") { for (let i = 1; i <= 2; i++) { fireEvent.change(screen.getByLabelText(`Matching Target ${i}`), { target: { value: `Target ${i}` } }); fireEvent.change(screen.getByLabelText(type === "Matching" ? `Left Item ${i}` : `Audio ${i}`), { target: { value: type === "Matching" ? `Left ${i}` : "media" } }); } }
    fireEvent.click(screen.getByRole("button", { name: "Save Question" })); await screen.findByText(`Question ${["Multiple Choice", "True / False", "Matching", "Listen & Match"].indexOf(type) + 1}: ${type}`);
  }
  fireEvent.click(screen.getByRole("button", { name: "Save" })); await waitFor(() => expect(api.createAssessment).toHaveBeenCalled());
  expect(api.createAssessment.mock.calls[0][2]).toMatchObject({ expected_revision: 4, assessment: { title: "Practice", required_for_completion: true }, questions: [{ type: "multiple_choice" }, { type: "true_false" }, { type: "matching" }, { type: "listen_match" }] });
});
it("preserves settings across question actions, confirms deletion and reports publication errors", async () => {
  api.loadAssessment.mockResolvedValue({ block_id: "b", assessment, questions: [{ ...questions[1], config: { correct_answer: true } }] });
  api.commandAssessment.mockResolvedValue({ block_id: "b", assessment: { ...assessment, revision: 2 }, questions: [{ ...questions[1], config: { correct_answer: true } }, { ...questions[1], id: "copy", config: { correct_answer: true } }] });
  render(<AssessmentBuilder courseId="c" lessonId="l" block={block} revision={4} onClose={vi.fn()} onSaved={vi.fn()} />);
  await screen.findByText("Question 1: True?"); fireEvent.change(screen.getByLabelText("Assessment Title"), { target: { value: "Unsaved title" } });
  fireEvent.click(screen.getByRole("button", { name: "Duplicate" })); await screen.findByText("Question 2: True?"); expect(screen.getByLabelText("Assessment Title").value).toBe("Unsaved title");
  fireEvent.click(screen.getAllByRole("button", { name: "Move Up" })[1]); await waitFor(() => expect(api.commandAssessment.mock.calls.some(call => call[3].action === "reorder_question")).toBe(true));
  fireEvent.click(screen.getAllByRole("button", { name: "Delete Permanently" })[0]); expect(screen.getByRole("button", { name: "Confirm" })).toBeTruthy(); expect(api.commandAssessment.mock.calls.some(call => call[3].action === "delete_question")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Confirm" })); await waitFor(() => expect(api.commandAssessment.mock.calls.some(call => call[3].action === "delete_question" && call[3].payload.confirmed)).toBe(true));
  api.commandAssessment.mockRejectedValue({ detail: { message: "Add at least one active question before publishing." } }); fireEvent.change(screen.getByLabelText("Status"), { target: { value: "published" } }); fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("Add at least one active question before publishing."); expect(api.commandAssessment.mock.calls.at(-1)[3].payload.title).toBe("Unsaved title");
});
it("returns to assessment settings and resumes a question draft without saving it", async () => {
  render(<AssessmentBuilder courseId="c" lessonId="l" revision={4} onClose={vi.fn()} onSaved={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Assessment Title"), { target: { value: "Safety check" } });
  fireEvent.click(screen.getByRole("button", { name: "Multiple Choice" }));
  fireEvent.change(screen.getByLabelText("Question", { exact: true }), { target: { value: "Where is the exit?" } });
  fireEvent.change(screen.getByLabelText("Option 1"), { target: { value: "Left" } });
  fireEvent.click(screen.getByRole("button", { name: "Back to Assessment" }));
  expect(screen.getByLabelText("Assessment Title").value).toBe("Safety check");
  expect(api.createAssessment).not.toHaveBeenCalled();
  expect(api.commandAssessment).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Multiple Choice" }));
  expect(screen.getByLabelText("Question", { exact: true }).value).toBe("Where is the exit?");
  expect(screen.getByLabelText("Option 1").value).toBe("Left");
  fireEvent.change(screen.getByLabelText("Option 2"), { target: { value: "Right" } });
  fireEvent.click(screen.getByRole("button", { name: "Save Question" }));
  await screen.findByText("Question 1: Where is the exit?");
  fireEvent.click(screen.getByRole("button", { name: "Multiple Choice" }));
  expect(screen.getByLabelText("Question", { exact: true }).value).toBe("");
});
it.each([
  ["Duplicate", "duplicate_question", {}, 0],
  ["Move Up", "reorder_question", { direction: "up" }, 1],
  ["Move Down", "reorder_question", { direction: "down" }, 0],
  ["Archive", "archive_question", { confirmed: true }, 0],
  ["Delete Permanently", "delete_question", { confirmed: true }, 0],
])("the %s icon sends the revision-checked question command", async (label, action, payload, index) => {
  const savedQuestions = ["first", "second"].map(id => ({ id, type: "true_false", prompt: id, points: 1, config: { correct_answer: true } }));
  const saved = { block_id: "b", assessment, questions: savedQuestions };
  api.loadAssessment.mockResolvedValue(saved);
  api.commandAssessment.mockResolvedValue({ ...saved, assessment: { ...assessment, revision: 2 } });
  render(<AssessmentBuilder courseId="c" block={block} revision={4} onClose={vi.fn()} onSaved={vi.fn()} />);
  await screen.findByText("Question 1: first");
  const button = screen.getAllByRole("button", { name: label, exact: true })[index];
  expect(button.querySelector("svg")).toBeTruthy();
  expect(button.title).toBe(label);
  fireEvent.click(button);
  if (payload.confirmed) {
    expect(api.commandAssessment).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm", exact: true }));
  }
  await waitFor(() => expect(api.commandAssessment).toHaveBeenCalledWith("c", undefined, "b", {
    action, question_id: savedQuestions[index].id, expected_revision: 1, payload,
  }));
});
it("the Edit icon saves changes through the update-question API command", async () => {
  const q = { id: "q", type: "true_false", prompt: "Original", points: 1, config: { correct_answer: true } };
  const saved = { block_id: "b", assessment, questions: [q] };
  api.loadAssessment.mockResolvedValue(saved);
  api.commandAssessment.mockResolvedValue({ ...saved, questions: [{ ...q, prompt: "Updated" }] });
  render(<AssessmentBuilder courseId="c" lessonId="l" block={block} revision={4} onClose={vi.fn()} onSaved={vi.fn()} />);
  await screen.findByText("Question 1: Original");
  const edit = screen.getByRole("button", { name: "Edit", exact: true });
  expect(edit.querySelector("svg")).toBeTruthy();
  fireEvent.click(edit);
  fireEvent.change(screen.getByLabelText("Question", { exact: true }), { target: { value: "Updated" } });
  fireEvent.click(screen.getByRole("button", { name: "Save Question" }));
  await waitFor(() => expect(api.commandAssessment).toHaveBeenCalledWith("c", "l", "b", {
    action: "update_question", question_id: "q", expected_revision: 1,
    payload: { type: "true_false", prompt: "Updated", points: 1, config: { correct_answer: true } },
  }));
});
