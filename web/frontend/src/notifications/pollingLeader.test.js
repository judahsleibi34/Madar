import { describe, expect, it, vi } from "vitest";

import { createNotificationPollingLeader } from "./pollingLeader";

describe("notification polling leader", () => {
  it("falls back safely when browser coordination is unavailable", () => {
    const leader = createNotificationPollingLeader({
      identity: "tenant:user",
      windowLike: { localStorage: new Map() },
    });
    expect(leader.supported).toBe(false);
  });

  it("elects one local-storage leader and forwards follower refresh requests", () => {
    const values = new Map();
    const channels = [];
    class Channel {
      constructor() { channels.push(this); }
      postMessage(message) { channels.forEach((item) => item !== this && item.onmessage?.({ data: message })); }
      close() {}
    }
    const windowLike = {
      BroadcastChannel: Channel,
      localStorage: { getItem: (key) => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) },
      setInterval: vi.fn(() => 1), clearInterval: vi.fn(),
    };
    const first = vi.fn();
    const second = vi.fn();
    const one = createNotificationPollingLeader({ identity: "tenant:user", windowLike, onRefreshRequested: first });
    const two = createNotificationPollingLeader({ identity: "tenant:user", windowLike, onRefreshRequested: second });
    one.start(); two.start();
    two.requestRefresh();
    expect(first.mock.calls.length + second.mock.calls.length).toBe(1);
    one.stop(); two.stop();
  });

  it("relinquishes a hidden leader so a visible sibling can take over", () => {
    const values = new Map();
    const listeners = new Map();
    class Channel { postMessage() {} close() {} }
    const visibleDocument = {
      visibilityState: "visible",
      addEventListener: (type, listener) => listeners.set(type, listener),
      removeEventListener: (type) => listeners.delete(type),
    };
    const hiddenListeners = new Map();
    const hiddenDocument = {
      visibilityState: "visible",
      addEventListener: (type, listener) => hiddenListeners.set(type, listener),
      removeEventListener: (type) => hiddenListeners.delete(type),
    };
    const windowLike = {
      BroadcastChannel: Channel,
      localStorage: { getItem: (key) => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) },
      setInterval: vi.fn(() => 1), clearInterval: vi.fn(),
    };
    const firstState = vi.fn();
    const secondState = vi.fn();
    const first = createNotificationPollingLeader({ identity: "tenant:user", windowLike, documentLike: hiddenDocument, onLeadershipChange: firstState });
    const second = createNotificationPollingLeader({ identity: "tenant:user", windowLike, documentLike: visibleDocument, onLeadershipChange: secondState });
    first.start();
    hiddenDocument.visibilityState = "hidden";
    hiddenListeners.get("visibilitychange")();
    second.start();
    expect(secondState).toHaveBeenCalledWith(true);
    first.stop(); second.stop();
  });
});
