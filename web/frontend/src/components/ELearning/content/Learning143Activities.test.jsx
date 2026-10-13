import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import SpeakingRecorder from "./SpeakingRecorder";
import MediaBlockRenderer from "./MediaBlockRenderer";
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: key => key, i18n: { language: "en" } }) }));
vi.mock("../../../utils/apiClient", () => ({ getApiUrl: value => value }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("learning media controls", () => {
  it("keeps an optional transcript hidden until the learner opens it", () => {
    render(<MediaBlockRenderer kind="audio" block={{ title: "Listen", media: { url: "/uploads/tenant_1/builder_assets/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav" }, content: { transcript: "Original testing transcript" } }} />);
    const transcript = screen.getByText("Original testing transcript").closest(".lesson-transcript");
    expect(transcript.hidden).toBe(true);
    const button = screen.getByRole("button", { name: "elearning.content.showTranscript" });
    fireEvent.click(button); expect(transcript.hidden).toBe(false);
    expect(screen.getByRole("button", { name: "elearning.content.hideTranscript" }).getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "elearning.content.hideTranscript" })); expect(transcript.hidden).toBe(true);
  });
  it("reports unsupported recording without manufacturing a score or answer", async () => {
    vi.stubGlobal("navigator", {});
    const onChange = vi.fn(); render(<SpeakingRecorder onChange={onChange} practice />);
    fireEvent.click(screen.getByRole("button", { name: "elearning.assessment.startRecording" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "elearning.assessment.unsupported");
    expect(screen.getByRole("button", { name: "elearning.assessment.finishPractice" }).disabled).toBe(true);
    expect(onChange).toHaveBeenCalledWith(null);
  });
  it("handles microphone denial with an actionable state", async () => {
    vi.stubGlobal("MediaRecorder", class {});
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: vi.fn().mockRejectedValue(Object.assign(new Error("denied"), { name: "NotAllowedError" })) } });
    render(<SpeakingRecorder onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "elearning.assessment.startRecording" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "elearning.assessment.microphoneDenied");
  });
  it("stops tracks granted after a recorder has unmounted", async () => {
    let grant; const stop = vi.fn();
    vi.stubGlobal("MediaRecorder", class {});
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: () => new Promise(resolve => { grant = resolve; }) } });
    const view = render(<SpeakingRecorder onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "elearning.assessment.startRecording" })); view.unmount();
    grant({ getTracks: () => [{ stop }] }); await waitFor(() => expect(stop).toHaveBeenCalledOnce());
  });
});
