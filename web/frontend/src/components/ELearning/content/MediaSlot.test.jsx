import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../../i18n";
import MediaSlot from "./MediaSlot";
import MediaBlockEditor from "./MediaBlockEditor";
import { LearningExperienceContext } from "../LearningExperienceContext";
import { LessonMediaNamingContext } from "./LessonMediaNaming";
import { checkMediaFile } from "../../../utils/mediaRules";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const file = (name, type, size = 1000) => new File([new Uint8Array(size)], name, { type });

it("checks type and size before uploading", () => {
  expect(checkMediaFile("image", file("a.gif", "image/gif"))).toBe("type");
  expect(checkMediaFile("image", file("a.jpg", "image/jpeg", 6 * 1024 * 1024))).toBe("size");
  expect(checkMediaFile("audio", file("a.wav", "audio/wav"))).toBe("");
  expect(checkMediaFile("audio", file("a.wav", "audio/wav", 0))).toBe("empty");
});

it("shows the expected media-list name, uploads with progress, then replaces or removes", async () => {
  let finish, progress;
  const upload = vi.fn((source, onProgress) => { progress = onProgress; return new Promise(resolve => { finish = resolve; }); });
  const onChange = vi.fn();
  const { container, rerender } = render(<MediaSlot kind="audio" label="Dialogue recording" expectedName="L03-T02-dialogue.wav" value={null} upload={upload} onChange={onChange} />);
  expect(screen.getByText("L03-T02-dialogue.wav")).toBeTruthy();
  expect(screen.getByText("Not uploaded")).toBeTruthy();
  const input = container.querySelector('input[type="file"]');
  fireEvent.change(input, { target: { files: [file("bad.txt", "text/plain")] } });
  expect((await screen.findByRole("alert")).textContent).toContain("This file type is not accepted.");
  expect(upload).not.toHaveBeenCalled();
  await act(async () => { fireEvent.change(input, { target: { files: [file("L03-T02-dialogue.wav", "audio/wav")] } }); });
  act(() => progress(40));
  expect(screen.getByRole("progressbar", { name: "Uploading" }).getAttribute("aria-valuenow")).toBe("40");
  await act(async () => finish({ asset_id: "m1", asset_url: "/uploads/tenant_1/builder_assets/x.wav" }));
  expect(onChange).toHaveBeenCalledWith({ id: "m1", url: "/uploads/tenant_1/builder_assets/x.wav", filename: "L03-T02-dialogue.wav" });
  rerender(<MediaSlot kind="audio" label="Dialogue recording" expectedName="L03-T02-dialogue.wav" value={{ id: "m1", url: "/uploads/tenant_1/builder_assets/x.wav", filename: "L03-T02-dialogue.wav" }} upload={upload} onChange={onChange} />);
  expect(screen.getByText("Uploaded")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Replace" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(onChange).toHaveBeenLastCalledWith(null);
});

it("keeps the existing upload control for academies that have not opted in", () => {
  const value = { type: "audio", media_id: null, media: null, content: { caption: "" } };
  const { container, unmount } = render(<MediaBlockEditor type="audio" value={value} onChange={() => {}} upload={vi.fn()} onBusy={() => {}} />);
  expect(container.querySelector(".media-slot")).toBeNull();
  unmount();
  render(<LearningExperienceContext.Provider value={{ lessonComponents: true }}><LessonMediaNamingContext.Provider value="L01-T01"><MediaBlockEditor type="audio" value={value} onChange={() => {}} upload={vi.fn()} onBusy={() => {}} /></LessonMediaNamingContext.Provider></LearningExperienceContext.Provider>);
  expect(screen.getByText("L01-T01-dialogue.wav")).toBeTruthy();
});
