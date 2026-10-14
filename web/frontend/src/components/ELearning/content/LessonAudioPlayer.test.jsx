import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../../i18n";
import LessonAudioPlayer from "./LessonAudioPlayer";
import { parseDialogue } from "../../../utils/lessonDialogue";

beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function play() { this.dispatchEvent(new Event("play")); return Promise.resolve(); });
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(function pause() { this.dispatchEvent(new Event("pause")); });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("plays, pauses, restarts and changes speed with large labelled controls", async () => {
  const { container } = render(<LessonAudioPlayer src="/a.mp3" title="Dialogue" />);
  const audio = container.querySelector("audio");
  expect(audio.hasAttribute("controls")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "LISTEN" }));
  expect(await screen.findByRole("button", { name: "PAUSE" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "PAUSE" }));
  expect(await screen.findByRole("button", { name: "LISTEN" })).toBeTruthy();
  audio.currentTime = 12;
  fireEvent.click(screen.getByRole("button", { name: "PLAY AGAIN" }));
  expect(audio.currentTime).toBe(0);
  fireEvent.click(screen.getByRole("button", { name: "0.75x" }));
  expect(audio.playbackRate).toBe(0.75);
  expect(screen.getByRole("button", { name: "0.75x" }).getAttribute("aria-pressed")).toBe("true");
});

it("shows the transcript as dialogue bubbles on demand", () => {
  render(<LessonAudioPlayer src="/a.mp3" transcript={"Omar: Hi, I'm Omar.\nLina: Nice to meet you."} />);
  const toggle = screen.getByRole("button", { name: "Show transcript" });
  expect(document.querySelector(".lesson-transcript").hidden).toBe(true);
  fireEvent.click(toggle);
  expect(document.querySelector(".lesson-transcript").hidden).toBe(false);
  expect([...document.querySelectorAll(".lesson-transcript-turn")].map(turn => turn.className)).toEqual(["lesson-transcript-turn is-start", "lesson-transcript-turn is-end"]);
  expect(parseDialogue("Plain narration without speakers")).toBeNull();
});

it("shows a clear placeholder until the recording is uploaded", () => {
  render(<LessonAudioPlayer title="Listen to the conversation" />);
  expect(screen.getByRole("status").textContent).toContain("This recording has not been uploaded yet.");
  expect(screen.queryByRole("button", { name: "LISTEN" })).toBeNull();
});

it("keeps the existing native player unless the academy opts in", async () => {
  const { default: MediaBlockRenderer } = await import("./MediaBlockRenderer");
  const { LearningExperienceContext } = await import("../LearningExperienceContext");
  const block = { title: "Listen", media: { url: "/uploads/tenant_1/builder_assets/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav" }, content: {} };
  const { container, unmount } = render(<MediaBlockRenderer kind="audio" block={block} />);
  expect(container.querySelector("audio").hasAttribute("controls")).toBe(true);
  expect(screen.queryByRole("button", { name: "LISTEN" })).toBeNull();
  unmount();
  render(<LearningExperienceContext.Provider value={{ lessonComponents: true }}><MediaBlockRenderer kind="audio" block={block} /></LearningExperienceContext.Provider>);
  expect(screen.getByRole("button", { name: "LISTEN" })).toBeTruthy();
});
