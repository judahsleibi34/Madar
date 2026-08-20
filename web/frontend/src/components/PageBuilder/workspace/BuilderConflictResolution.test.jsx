import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import BuilderConflictResolution from "./BuilderConflictResolution";

const conflict = {
  localSavedAt: "2026-07-15T08:00:00Z",
  serverUpdatedAt: "2026-07-15T08:01:00Z",
  localBaseRevision: 59,
  serverRevision: 60,
};

afterEach(cleanup);

describe("builder conflict resolution UX", () => {
  it("downloads without changing conflict state", () => {
    const onDownload = vi.fn();
    render(<BuilderConflictResolution conflict={conflict} onDownload={onDownload} />);
    fireEvent.click(screen.getByRole("button", { name: /download local copy/i }));
    expect(onDownload).toHaveBeenCalledOnce();
    expect(screen.getByText("This project changed elsewhere")).toBeTruthy();
  });

  it("requires a second explicit destructive confirmation", async () => {
    const onLoadCandidate = vi.fn().mockResolvedValue(undefined);
    const onUseServer = vi.fn().mockResolvedValue(undefined);
    render(
      <BuilderConflictResolution
        conflict={conflict}
        onDownload={vi.fn()}
        onLoadCandidate={onLoadCandidate}
        onUseServer={onUseServer}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Resolve conflict" }));
    await waitFor(() => expect(onLoadCandidate).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole("button", { name: "Replace my local edits with the latest saved version" }));
    expect(onUseServer).not.toHaveBeenCalled();
    expect(screen.getByText(/discard local changes\?/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /discard my edits and use server version/i }));
    await waitFor(() => expect(onUseServer).toHaveBeenCalledOnce());
  });

  it("keeps the local copy and conflict latch when dismissed", async () => {
    const onUseServer = vi.fn();
    render(<BuilderConflictResolution conflict={conflict} onUseServer={onUseServer} />);
    fireEvent.click(screen.getByRole("button", { name: "Resolve conflict" }));
    fireEvent.click(await screen.findByRole("button", { name: "Keep viewing local copy" }));
    expect(onUseServer).not.toHaveBeenCalled();
    expect(screen.getByText("This project changed elsewhere")).toBeTruthy();
  });

  it("requires an explicit choice for every overlapping edit", async () => {
    const onResolveConflicts = vi.fn().mockResolvedValue(true);
    const overlapping = {
      ...conflict,
      conflicts: [{
        path: "pages[id=page-2].sections[id=hero].freeElements[id=button].content",
        entity: { name: "Button" },
        localValue: "Final Test??",
        serverValue: "Remote label",
      }],
    };
    render(
      <BuilderConflictResolution
        conflict={overlapping}
        onDownload={vi.fn()}
        onLoadCandidate={vi.fn()}
        onResolveConflicts={onResolveConflicts}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Review conflicts" }));
    const save = await screen.findByRole("button", { name: "Save resolved changes" });
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: /keep my change/i }));
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    await waitFor(() => expect(onResolveConflicts).toHaveBeenCalledWith({ 0: "local" }));
  });
});
