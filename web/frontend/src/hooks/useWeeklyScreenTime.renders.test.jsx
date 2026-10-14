import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(() => Promise.resolve({ ok: true })) }));
vi.mock("../utils/apiClient", () => ({ apiFetch: mocks.apiFetch, getApiUrl: (path) => path }));

const { default: useWeeklyScreenTime } = await import("./useWeeklyScreenTime");

const user = { id: 7 };

function Tracked({ options, onRender }) {
  onRender();
  useWeeklyScreenTime(user, options);
  return null;
}

const runFocused = (options, seconds) => {
  let renders = 0;
  render(<Tracked options={options} onRender={() => { renders += 1; }} />);
  for (let second = 0; second < seconds; second += 1) act(() => { vi.advanceTimersByTime(1000); });
  return renders;
};

describe("weekly screen time renders", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
    mocks.apiFetch.mockClear();
    vi.spyOn(document, "hasFocus").mockReturnValue(true);
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("re-renders its host every second only when the total is reported", () => {
    // Measured before the opt-out: one host render per active second.
    expect(runFocused({ scope: "site:a", endpoint: "/public/sites/a/screen-time/heartbeat" }, 12)).toBeGreaterThanOrEqual(12);
    cleanup();
    expect(runFocused({ scope: "site:b", endpoint: "/public/sites/b/screen-time/heartbeat", reportSeconds: false }, 12)).toBe(1);
  });

  it("keeps tracking, storage and heartbeats when the total is not reported", () => {
    runFocused({ scope: "site:a", endpoint: "/public/sites/a/screen-time/heartbeat", reportSeconds: false }, 12);
    expect(mocks.apiFetch).toHaveBeenCalledTimes(1);
    expect(mocks.apiFetch.mock.calls[0][0]).toBe("/public/sites/a/screen-time/heartbeat");
    expect(JSON.parse(mocks.apiFetch.mock.calls[0][1].body).active_seconds).toBeGreaterThanOrEqual(9);
    const stored = JSON.parse(window.localStorage.getItem("madar:weekly-screen-time:v1:site:a:7"));
    expect(stored.seconds).toBeGreaterThanOrEqual(9);
  });
});
