import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import BuilderRecoveryNotice from "./BuilderRecoveryNotice";

afterEach(() => cleanup());

const actions = () => ({
  onDiscard: vi.fn(),
  onExport: vi.fn(),
  onKeepServer: vi.fn(),
});

describe("BuilderRecoveryNotice", () => {
  it("keeps a current-revision recovery separate from the server project", () => {
    const handlers = actions();
    render(<BuilderRecoveryNotice decision={{ kind: "restorable", envelope: { schema: {} } }} {...handlers} />);
    expect(screen.queryByRole("button", { name: /restore|attach/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /download recovery/i }));
    expect(handlers.onExport).toHaveBeenCalledOnce();
  });

  it("keeps stale recovery separate and defaults to the server version", () => {
    const handlers = actions();
    render(<BuilderRecoveryNotice decision={{ kind: "stale_conflict", envelope: { schema: {} } }} {...handlers} />);
    expect(screen.queryByRole("button", { name: /restore/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /continue with server/i }));
    expect(handlers.onKeepServer).toHaveBeenCalledOnce();
  });

  it("offers export/discard for an unscoped legacy draft without attaching it", () => {
    const handlers = actions();
    render(<BuilderRecoveryNotice decision={{ kind: "legacy", legacy: { raw: "{}" } }} {...handlers} />);
    fireEvent.click(screen.getByRole("button", { name: /download recovery/i }));
    fireEvent.click(screen.getByRole("button", { name: /discard recovery/i }));
    expect(handlers.onExport).toHaveBeenCalledOnce();
    expect(handlers.onDiscard).toHaveBeenCalledOnce();
  });

  it("never offers to attach a legacy copy to the routed project", () => {
    const handlers = actions();
    render(<BuilderRecoveryNotice decision={{ kind: "legacy", legacy: { raw: "{}" } }} {...handlers} />);
    expect(screen.queryByRole("button", { name: /attach|restore/i })).toBeNull();
  });
});
