import { describe, expect, it, vi } from "vitest";

import { createToastCoordinator } from "./toastCoordinator";

function createWindowPair() {
  const listeners = new Set();
  const storageValues = new Map();
  class Channel {
    constructor() {
      listeners.add(this);
    }
    postMessage(message) {
      for (const listener of listeners) {
        if (listener !== this) queueMicrotask(() => listener.onmessage?.({ data: message }));
      }
    }
    close() {
      listeners.delete(this);
    }
  }
  const storage = {
    getItem: (key) => storageValues.get(key) || null,
    setItem: (key, value) => storageValues.set(key, value),
  };
  const create = () => ({
    BroadcastChannel: Channel,
    localStorage: storage,
    navigator: {},
    setTimeout,
  });
  return [create(), create()];
}

describe("toast cross-tab coordination", () => {
  it("allows only one coordinated tab to claim the same notification", async () => {
    const [windowA, windowB] = createWindowPair();
    const coordinatorA = createToastCoordinator({ windowLike: windowA, arbitrationMs: 5 });
    const coordinatorB = createToastCoordinator({ windowLike: windowB, arbitrationMs: 5 });

    const results = await Promise.all([
      coordinatorA.claim("tenant-a:user-1:notification-1"),
      coordinatorB.claim("tenant-a:user-1:notification-1"),
    ]);

    expect(results.filter(Boolean)).toHaveLength(1);
    coordinatorA.close();
    coordinatorB.close();
  });

  it("keeps notifications functional when coordination APIs are unavailable", async () => {
    const storage = { getItem: vi.fn(() => null), setItem: vi.fn() };
    const coordinator = createToastCoordinator({
      windowLike: { localStorage: storage, navigator: {}, setTimeout },
    });

    await expect(coordinator.claim("tenant-a:user-1:notification-1")).resolves.toBe(true);
    expect(coordinator.supported).toBe(false);
    coordinator.close();
  });
});
