import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BUILDER_SAVE_STATES } from "../core/PageBuilder.saveState";
import { BuilderSidebarActions } from "./PageBuilder";

afterEach(cleanup);

describe("BuilderSidebarActions", () => {
  it("places the save action and cloud status together in the sidebar", () => {
    const onSave = vi.fn();

    render(
      <BuilderSidebarActions
        isSavingProject={false}
        lastCloudSavedAt={new Date("2026-07-17T10:30:00")}
        onSave={onSave}
        onGoLive={vi.fn()}
        publicationState="draft"
        saveState={BUILDER_SAVE_STATES.savedCloud}
      />
    );

    expect(screen.getByRole("status").textContent).toMatch(/Saved at/i);
    fireEvent.click(screen.getByRole("button", { name: /^Save$/i }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("uses the same sidebar button for retry and respects disabled states", () => {
    const { rerender } = render(
      <BuilderSidebarActions
        isSavingProject={false}
        onSave={vi.fn()}
        onGoLive={vi.fn()}
        publicationState="draft"
        saveState={BUILDER_SAVE_STATES.saveFailed}
      />
    );

    expect(screen.getByRole("button", { name: /Retry save/i })).toBeTruthy();

    rerender(
      <BuilderSidebarActions
        isSavingProject={false}
        onSave={vi.fn()}
        onGoLive={vi.fn()}
        publicationState="draft"
        saveDisabled
        saveState={BUILDER_SAVE_STATES.conflict}
      />
    );

    expect(screen.getByRole("button", { name: /^Save$/i }).disabled).toBe(true);
  });
});
