import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEffect } from "react";

import useDebouncedProjectStorage from "./useDebouncedProjectStorage";

const STORAGE_KEY = "madar-builder-test-draft";

function ProjectStorageProbe({
  delay = 600,
  disabled = false,
  onFlushReady,
  project,
  storageKey = STORAGE_KEY,
}) {
  const flush = useDebouncedProjectStorage({
    delay,
    disabled,
    project,
    storageKey,
  });

  useEffect(() => {
    onFlushReady?.(flush);
  }, [flush, onFlushReady]);

  return null;
}

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("useDebouncedProjectStorage", () => {
  it("debounces rapid project changes and writes the latest project", () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    const { rerender } = render(<ProjectStorageProbe project={{ id: "first" }} />);

    expect(setItemSpy).not.toHaveBeenCalled();

    rerender(<ProjectStorageProbe project={{ id: "second" }} />);
    rerender(<ProjectStorageProbe project={{ id: "latest", title: "Draft" }} />);

    act(() => {
      vi.advanceTimersByTime(599);
    });

    expect(setItemSpy).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(setItemSpy).toHaveBeenCalledTimes(1);
    expect(setItemSpy).toHaveBeenCalledWith(
      STORAGE_KEY,
      JSON.stringify({ id: "latest", title: "Draft" })
    );
    expect(localStorage.getItem(STORAGE_KEY)).toBe(
      JSON.stringify({ id: "latest", title: "Draft" })
    );
  });

  it("flushes the latest pending project immediately", () => {
    let flushProjectStorage = null;
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    const { rerender } = render(
      <ProjectStorageProbe
        onFlushReady={(flush) => {
          flushProjectStorage = flush;
        }}
        project={{ id: "first" }}
      />
    );

    rerender(
      <ProjectStorageProbe
        onFlushReady={(flush) => {
          flushProjectStorage = flush;
        }}
        project={{ id: "latest" }}
      />
    );

    act(() => {
      flushProjectStorage();
    });

    expect(setItemSpy).toHaveBeenCalledTimes(1);
    expect(setItemSpy).toHaveBeenCalledWith(STORAGE_KEY, JSON.stringify({ id: "latest" }));

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(setItemSpy).toHaveBeenCalledTimes(1);
  });

  it("flush is safe when no project is pending", () => {
    let flushProjectStorage = null;
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    render(
      <ProjectStorageProbe
        onFlushReady={(flush) => {
          flushProjectStorage = flush;
        }}
        project={null}
      />
    );

    expect(() => {
      act(() => {
        flushProjectStorage();
      });
    }).not.toThrow();
    expect(setItemSpy).not.toHaveBeenCalled();
  });

  it("clears pending timers on unmount without writing stale data", () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    const { unmount } = render(<ProjectStorageProbe project={{ id: "stale" }} />);

    unmount();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(setItemSpy).not.toHaveBeenCalled();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("catches localStorage write errors", () => {
    const storageError = new Error("storage denied");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw storageError;
    });

    render(<ProjectStorageProbe project={{ id: "draft" }} />);

    expect(() => {
      act(() => {
        vi.advanceTimersByTime(600);
      });
    }).not.toThrow();

    expect(warnSpy).toHaveBeenCalledWith("Could not persist builder draft.");
  });
});
