import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../../i18n";
import ListenMatchActivity from "./ListenMatchActivity";
import AssessmentBlockRenderer from "./AssessmentBlockRenderer";
import { LearningExperienceContext } from "../LearningExperienceContext";
import { checkPracticeAnswer, learnerAssessment, submitAssessment } from "../../../services/elearningAssessments";
vi.mock("../../../services/elearningAssessments", () => ({ checkPracticeAnswer: vi.fn(), learnerAssessment: vi.fn(), submitAssessment: vi.fn(), startAssessment: vi.fn(), loadAssessment: vi.fn() }));

const photo = n => ({ id: `o${n}`, alt: `Photo ${n}`, media: { url: `/uploads/tenant_1/builder_assets/${String(n).repeat(32)}.jpg` } });
const question = (id, correct) => ({ id, type: "picture_listen", prompt: "Listen", config: { media: { url: `/uploads/tenant_1/builder_assets/${"a".repeat(32)}.wav` }, options: [photo(1), photo(2), photo(3), photo(4)], correct_option_id: correct } });
const questions = [question("q1", "o2"), question("q2", "o3")];
beforeEach(async () => { await i18n.changeLanguage("en"); vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.resetAllMocks(); });

it("runs one question at a time with the book's feedback, counter and first-try score", async () => {
  const check = vi.fn(async (q, option) => ({ correct: (q === "q1" && option === "o2") || (q === "q2" && option === "o3") }));
  const onFinish = vi.fn();
  render(<ListenMatchActivity questions={questions} check={check} onFinish={onFinish} />);
  expect(screen.getByText("Question 1 of 2")).toBeTruthy();
  expect(screen.getByText("What did you hear?")).toBeTruthy();
  expect(screen.getByRole("button", { name: "LISTEN" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "PLAY AGAIN" })).toBeTruthy();
  const tiles = screen.getAllByRole("button", { name: /^Picture \d/ });
  expect(tiles).toHaveLength(4);
  expect(tiles.map(tile => tile.textContent)).toEqual(["", "", "", ""]);
  fireEvent.click(tiles[0]);
  expect(await screen.findByText("Not quite. Listen again and try again.")).toBeTruthy();
  expect(tiles[0].className).toContain("is-incorrect");
  expect(screen.queryByRole("button", { name: "CONTINUE" })).toBeNull();
  fireEvent.click(tiles[1]);
  expect(await screen.findByText("Excellent! That's correct.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "CONTINUE" }));
  expect(screen.getByText("Question 2 of 2")).toBeTruthy();
  fireEvent.click(screen.getAllByRole("button", { name: /^Picture \d/ })[2]);
  fireEvent.click(await screen.findByRole("button", { name: "CONTINUE" }));
  expect(onFinish).toHaveBeenCalledWith({ answers: { q1: { option_id: "o2" }, q2: { option_id: "o3" } }, correct: 1, total: 2 });
});

it("shows placeholders until the owner uploads the photos and recording", () => {
  const pending = { ...questions[0], config: { ...questions[0].config, media: null, options: questions[0].config.options.map(option => ({ ...option, media: null })) } };
  const { container } = render(<ListenMatchActivity questions={[pending]} check={vi.fn()} onFinish={vi.fn()} />);
  expect(screen.getByRole("status").textContent).toContain("This recording has not been uploaded yet.");
  expect(container.querySelectorAll(".listen-match-photo-pending")).toHaveLength(4);
});

it("uses Listen & Match only for opted-in academies and submits the practice result", async () => {
  const attempt = { id: "a1", status: "in_progress", activity_mode: "practice", questions };
  learnerAssessment.mockResolvedValue({ assessment: { title: "Listen and match", activity_mode: "practice" }, attempt, summary: { attempts: 1 } });
  const block = { id: "b1", assessment: { title: "Listen and match" } };
  const { unmount } = render(<AssessmentBlockRenderer block={block} context="learner" courseId="c" lessonId="l" />);
  expect(await screen.findByRole("button", { name: "Submit Assessment" })).toBeTruthy();
  expect(screen.queryByText("What did you hear?")).toBeNull();
  unmount();
  checkPracticeAnswer.mockResolvedValue({ correct: true });
  submitAssessment.mockResolvedValue({ assessment: { title: "Listen and match", activity_mode: "practice" }, attempt: { ...attempt, status: "submitted" }, summary: { attempts: 1 } });
  render(<LearningExperienceContext.Provider value={{ lessonComponents: true }}><AssessmentBlockRenderer block={block} context="learner" courseId="c" lessonId="l" /></LearningExperienceContext.Provider>);
  fireEvent.click((await screen.findAllByRole("button", { name: /^Picture \d/ }))[1]);
  fireEvent.click(await screen.findByRole("button", { name: "CONTINUE" }));
  fireEvent.click((await screen.findAllByRole("button", { name: /^Picture \d/ }))[2]);
  fireEvent.click(await screen.findByRole("button", { name: "CONTINUE" }));
  await waitFor(() => expect(submitAssessment).toHaveBeenCalledWith("c", "l", "b1", "a1", { q1: { option_id: "o2" }, q2: { option_id: "o3" } }));
  expect(await screen.findByText("2 / 2 Correct")).toBeTruthy();
});
