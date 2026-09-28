import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WeeklyScreenTimePanel from "./WeeklyScreenTimePanel";
import { fetchWeeklyScreenTime } from "../PageBuilder/services/PageBuilder.api";

vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  fetchWeeklyScreenTime: vi.fn(),
}));

describe("WeeklyScreenTimePanel", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  beforeEach(() => {
    fetchWeeklyScreenTime.mockReset();
    fetchWeeklyScreenTime.mockResolvedValue({
      total_seconds: 5400,
      users: [
        {
          user_id: 1,
          name: "Sulaima",
          role: "owner",
          active_seconds: 3600,
          is_current_user: true,
        },
        {
          user_id: 2,
          name: "Ahmad",
          role: "reviewer",
          active_seconds: 1800,
          is_current_user: false,
        },
      ],
    });
  });

  it("renders a horizontal bar for every named user", async () => {
    render(
      <WeeklyScreenTimePanel
        currentUser={{ id: 1, name: "Sulaima" }}
        currentSeconds={3600}
        projectId="project-1"
      />
    );

    await waitFor(() => expect(screen.getByText("Sulaima")).toBeTruthy());
    expect(screen.getByText("Ahmad")).toBeTruthy();
    expect(screen.getByText("1h 30m")).toBeTruthy();
    const sulaimaBar = screen.getByLabelText("Sulaima week screen time");
    expect(sulaimaBar.querySelector("span").style.width).toBe("100%");
    expect(fetchWeeklyScreenTime).toHaveBeenCalledWith("project-1", "week");
  });

  it("loads the current calendar month when This month is selected", async () => {
    render(
      <WeeklyScreenTimePanel
        currentUser={{ id: 1, name: "Sulaima" }}
        projectId="project-1"
      />
    );

    fireEvent.click(screen.getByRole("tab", { name: "This month" }));

    await waitFor(() =>
      expect(fetchWeeklyScreenTime).toHaveBeenLastCalledWith("project-1", "month")
    );
    expect(screen.getByText("Monthly activity")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "This month" }).getAttribute("aria-selected")).toBe(
      "true"
    );
  });

  it("waits for project discovery and does not poll the weekly summary every 30 seconds", async () => {
    vi.useFakeTimers();
    const view = render(
      <WeeklyScreenTimePanel
        currentUser={{ id: 1, name: "Sulaima" }}
        enabled={false}
        projectId=""
      />
    );
    expect(fetchWeeklyScreenTime).not.toHaveBeenCalled();

    view.rerender(
      <WeeklyScreenTimePanel
        currentUser={{ id: 1, name: "Sulaima" }}
        enabled
        projectId="project-1"
      />
    );
    await vi.waitFor(() => expect(fetchWeeklyScreenTime).toHaveBeenCalledTimes(1));
    expect(fetchWeeklyScreenTime).toHaveBeenLastCalledWith("project-1", "week");

    await vi.advanceTimersByTimeAsync(90_000);
    expect(fetchWeeklyScreenTime).toHaveBeenCalledTimes(1);

    fireEvent.focus(window);
    fireEvent(document, new Event("visibilitychange"));
    await vi.waitFor(() => expect(fetchWeeklyScreenTime).toHaveBeenCalledTimes(2));
  });
});
