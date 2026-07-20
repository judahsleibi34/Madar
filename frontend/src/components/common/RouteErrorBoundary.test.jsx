import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RouteErrorBoundary from "./RouteErrorBoundary";

let shouldThrow;

function UnstableRoute() {
  if (shouldThrow) throw new Error("private customer detail must not be logged");
  return <p>Recovered route</p>;
}

describe("RouteErrorBoundary", () => {
  let consoleSpy;

  beforeEach(() => {
    shouldThrow = true;
    consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    consoleSpy.mockRestore();
  });

  it("renders an accessible redacted fallback and safe navigation", () => {
    render(
      <RouteErrorBoundary surface="public" homePath="/" homeLabel="Return home">
        <UnstableRoute />
      </RouteErrorBoundary>
    );

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Return home" }).getAttribute("href")).toBe("/");
    expect(screen.queryByText(/private customer detail/i)).toBeNull();
    expect(consoleSpy).toHaveBeenCalledWith(
      "route_render_error",
      expect.objectContaining({ surface: "public", event_id: expect.any(String) })
    );
    expect(JSON.stringify(consoleSpy.mock.calls)).not.toContain("private customer detail");
  });

  it("retries without reloading and preserves builder recovery messaging", () => {
    render(
      <RouteErrorBoundary
        surface="page-builder"
        homePath="/dashboard"
        homeLabel="Return to dashboard"
      >
        <UnstableRoute />
      </RouteErrorBoundary>
    );

    expect(screen.getByText(/recovery drafts are preserved/i)).toBeTruthy();
    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByText("Recovered route")).toBeTruthy();
  });
});
