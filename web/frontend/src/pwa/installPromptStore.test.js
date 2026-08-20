import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getInstallPromptState,
  initializeInstallPromptCapture,
  promptForInstall,
  resetInstallPromptCaptureForTests,
  subscribeAppInstalled,
} from "./installPromptStore";

function browserWindow({ userAgent = "Mozilla/5.0 Chrome/140.0", standalone = false } = {}) {
  const target = new EventTarget();
  target.location = { hostname: "madarportal.com" };
  target.navigator = { userAgent, platform: "Linux", standalone: false };
  target.matchMedia = vi.fn(() => ({ matches: standalone }));
  return target;
}

function promptEvent({ outcome = "accepted", throws = false } = {}) {
  const event = new Event("beforeinstallprompt");
  event.preventDefault = vi.fn();
  event.prompt = throws
    ? vi.fn().mockRejectedValue(new Error("prompt failed"))
    : vi.fn().mockResolvedValue(undefined);
  event.userChoice = Promise.resolve({ outcome });
  return event;
}

afterEach(() => resetInstallPromptCaptureForTests());

describe("global PWA install prompt store", () => {
  it("captures the prompt before Settings mounts and retains it across SPA navigation", () => {
    const windowLike = browserWindow();
    initializeInstallPromptCapture(windowLike);
    const event = promptEvent();
    windowLike.dispatchEvent(event);

    expect(event.preventDefault).toHaveBeenCalledTimes(1);
    expect(getInstallPromptState(windowLike).status).toBe("prompt_available");
    windowLike.dispatchEvent(new Event("popstate"));
    expect(getInstallPromptState(windowLike).status).toBe("prompt_available");
    expect(event.prompt).not.toHaveBeenCalled();
  });

  it("prompts only when explicitly invoked and clears accepted or dismissed events", async () => {
    const windowLike = browserWindow();
    initializeInstallPromptCapture(windowLike);
    const accepted = promptEvent();
    windowLike.dispatchEvent(accepted);
    expect(accepted.prompt).not.toHaveBeenCalled();
    expect((await promptForInstall()).outcome).toBe("accepted");
    expect(accepted.prompt).toHaveBeenCalledTimes(1);
    expect(getInstallPromptState(windowLike).status).toBe("manual_install_available");

    const dismissed = promptEvent({ outcome: "dismissed" });
    windowLike.dispatchEvent(dismissed);
    expect((await promptForInstall()).outcome).toBe("dismissed");
    expect(getInstallPromptState(windowLike).lastOutcome).toBe("dismissed");
  });

  it("handles prompt failures without marking the app installed", async () => {
    const windowLike = browserWindow();
    initializeInstallPromptCapture(windowLike);
    windowLike.dispatchEvent(promptEvent({ throws: true }));
    expect((await promptForInstall()).outcome).toBe("error");
    expect(getInstallPromptState(windowLike).installed).toBe(false);
    expect(getInstallPromptState(windowLike).error).toBeTruthy();
  });

  it("globally handles appinstalled and notifies installation lifecycle consumers", () => {
    const windowLike = browserWindow();
    const installed = vi.fn();
    initializeInstallPromptCapture(windowLike);
    subscribeAppInstalled(installed);
    windowLike.dispatchEvent(promptEvent());
    windowLike.dispatchEvent(new Event("appinstalled"));
    expect(getInstallPromptState(windowLike).status).toBe("installed");
    expect(installed).toHaveBeenCalledTimes(1);
  });

  it("uses standalone, iOS manual, Chromium manual, and unsupported states", () => {
    expect(getInstallPromptState(browserWindow({ standalone: true })).status).toBe("installed");
    expect(getInstallPromptState(browserWindow({ userAgent: "Mozilla/5.0 (iPhone)" })).status).toBe("ios_manual");
    expect(getInstallPromptState(browserWindow()).status).toBe("manual_install_available");
    expect(getInstallPromptState(browserWindow({ userAgent: "Mozilla/5.0 Firefox/140.0" })).status).toBe("unsupported");
  });
});
