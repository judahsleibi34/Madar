import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../../i18n";
import ContentBlockRenderer from "./ContentBlockRenderer";
import TextBlockEditor from "./TextBlockEditor";
import { ChooseBestResponse, SpeakNow } from "./PracticeActivities";
import { LearningExperienceContext } from "../LearningExperienceContext";
import { componentBody } from "../../../utils/lessonComponentBody";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const on = node => <LearningExperienceContext.Provider value={{ lessonComponents: true }}>{node}</LearningExperienceContext.Provider>;
const vocabulary = { kind: "vocabulary", items: [{ word: "seat", meaning: "A place for one person to sit.", arabic: "مقعد", example: "Is this seat free?", pronunciation: "/siːt/", stress: "" }] };
const block = { id: "b", type: "text", title: "Words and meanings", content: { version: 1, body: componentBody(vocabulary), component: vocabulary } };

it("shows structured cards only for opted-in academies and keeps the readable text for everyone else", () => {
  const { container, unmount } = render(<ContentBlockRenderer block={block} context="learner" />);
  expect(container.querySelector(".lesson-vocabulary")).toBeNull();
  expect(container.textContent).toContain("seat — A place for one person to sit.");
  unmount();
  const view = render(on(<ContentBlockRenderer block={block} context="learner" />));
  const card = view.container.querySelector(".lesson-vocabulary");
  expect(card.querySelector("h3").textContent).toBe("Words and meanings");
  expect(view.container.querySelectorAll("h3")).toHaveLength(1);
  expect(card.querySelector(".lesson-vocabulary-word").getAttribute("lang")).toBe("en");
  expect(screen.getByText("مقعد").getAttribute("dir")).toBe("rtl");
});

it("lets the owner build a card and stores a generated plain-text body", () => {
  const onChange = vi.fn();
  render(on(<TextBlockEditor value={{ version: 1, body: "", formats: [], ranges: [] }} onChange={onChange} />));
  fireEvent.change(screen.getByLabelText("Content type"), { target: { value: "speaker_tip" } });
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ component: { kind: "speaker_tip", tip: "", arabic: "", avoid: "", say: "" } }));
  expect(componentBody({ kind: "speaker_tip", tip: "Say your age with 'be'.", avoid: "I have 20 years.", say: "I am 20 years old." })).toBe("Say your age with 'be'.\nAvoid: I have 20 years.\nSay: I am 20 years old.");
});

it("checks each response and moves on with CONTINUE", async () => {
  const questions = [{ id: "q1", type: "multiple_choice", prompt: "A classmate says: Is this seat free?", config: { options: [{ id: "a", label: "Yes, please sit here." }, { id: "b", label: "I am twenty." }] } }];
  const check = vi.fn(async (q, option) => ({ correct: option === "a" })), onFinish = vi.fn();
  render(<ChooseBestResponse title="Choose the best response" questions={questions} check={check} onFinish={onFinish} />);
  fireEvent.click(screen.getByRole("button", { name: "I am twenty." }));
  expect(await screen.findByText("Not quite. Read the situation again and try another response.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Yes, please sit here." }));
  fireEvent.click(await screen.findByRole("button", { name: "CONTINUE" }));
  expect(onFinish).toHaveBeenCalledWith({ answers: { q1: { option_id: "a" } }, correct: 0, total: 1 });
});

it("keeps CONTINUE disabled in Speak Now until the learner has recorded", () => {
  render(<SpeakNow questions={[{ id: "s1", type: "speaking_practice", prompt: "Introduce yourself.", config: { max_duration_seconds: 60, max_size_bytes: 1048576 } }]} onFinish={vi.fn()} />);
  expect(screen.getByRole("heading", { name: "Speak Now" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "CONTINUE" }).disabled).toBe(true);
  expect(screen.getByRole("button", { name: "Start recording" })).toBeTruthy();
});
