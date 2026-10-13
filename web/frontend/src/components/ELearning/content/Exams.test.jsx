import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../../i18n";
import ExamCard from "./ExamCard";
import ExamRunner from "./ExamRunner";
import CertificateShare from "../CertificateShare";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows Locked, Available, Passed with score and Not passed with Retake", () => {
  const cards = [{ title: "A1 Final Exam", locked: true }, { title: "A2 Final Exam", attempts: 0, passing_score: 70 }, { title: "B1 Final Exam", passed: true, attempts: 1, best_score: 88 }, { title: "B2 Final Exam", attempts: 2, best_score: 55 }];
  render(<MemoryRouter>{cards.map(exam => <ExamCard key={exam.title} exam={exam} href="/x" />)}</MemoryRouter>);
  const [locked, available, passed, failed] = screen.getAllByRole("article");
  expect(within(locked).getByText("Locked")).toBeTruthy(); expect(within(locked).queryByRole("link")).toBeNull();
  expect(within(available).getByText("Pass mark: 70%")).toBeTruthy(); expect(within(available).getByRole("link", { name: "Start exam" })).toBeTruthy();
  expect(within(passed).getByText("Passed — 88%")).toBeTruthy();
  expect(within(failed).getByText("Not passed — 55%")).toBeTruthy(); expect(within(failed).getByRole("link", { name: "Retake" })).toBeTruthy();
  for (const card of [locked, available, passed, failed]) expect(card.querySelector(".exam-card-status svg")).toBeTruthy();
});

it("shows one question at a time and submits only after review with every answer", () => {
  const attempt = { id: "t1", status: "in_progress", started_at: new Date().toISOString(), questions: [
    { id: "q1", type: "true_false", prompt: "Omar studies engineering.", points: 1, config: {} },
    { id: "q2", type: "multiple_choice", prompt: "Choose the natural answer.", points: 1, config: { options: [{ id: "a", label: "I am 20 years old." }, { id: "b", label: "I have 20 years." }] } }] };
  let answers = {}; const onSubmit = vi.fn();
  const view = render(<ExamRunner attempt={attempt} answers={answers} onChange={(id, value) => { answers = { ...answers, [id]: value }; view.rerender(<ExamRunner attempt={attempt} answers={answers} onChange={() => {}} onSubmit={onSubmit} />); }} onSubmit={onSubmit} />);
  expect(screen.getByText("Question 1 of 2")).toBeTruthy();
  expect(screen.getByRole("timer").textContent).toContain("Time spent");
  const [first, second] = document.querySelectorAll("fieldset.assessment-question");
  expect(first.hidden).toBe(false); expect(second.hidden).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText("Question 2 of 2")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Review answers" }));
  expect(screen.getByRole("button", { name: "Submit Assessment" }).disabled).toBe(true);
  expect(onSubmit).not.toHaveBeenCalled();
  expect(document.body.textContent).not.toMatch(/Correct|Incorrect/);
});

it("shares the public verification link or copies it", async () => {
  const writeText = vi.fn().mockResolvedValue(); Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
  render(<CertificateShare title="A1 English Speaking Certificate" url="https://madarportal.com/verify/credential/abc" />);
  fireEvent.click(screen.getByRole("button", { name: "Share" }));
  expect(await screen.findByRole("button", { name: "Link copied" })).toBeTruthy();
  expect(writeText).toHaveBeenCalledWith("https://madarportal.com/verify/credential/abc");
});
