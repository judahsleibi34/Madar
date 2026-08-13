import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";

const workerPath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../public/madar-push-sw.js"
);

function createIndexedDb(state) {
  const database = {
    objectStoreNames: { contains: () => false },
    createObjectStore: () => {},
    close: vi.fn(),
    transaction: () => {
      const transaction = {
        error: null,
        objectStore: () => ({
          put: (value, key) => {
            state[key] = value;
            queueMicrotask(() => transaction.oncomplete?.());
          },
        }),
      };
      return transaction;
    },
  };
  return {
    open: () => {
      const request = { result: database, error: null };
      queueMicrotask(() => {
        request.onupgradeneeded?.();
        request.onsuccess?.();
      });
      return request;
    },
  };
}

function loadWorker({ clients = [], indexedDbState = {} } = {}) {
  const listeners = {};
  const openWindow = vi.fn().mockResolvedValue(null);
  const showNotification = vi.fn().mockResolvedValue(undefined);
  const self = {
    location: { origin: "https://app.example.test" },
    registration: { showNotification },
    clients: {
      claim: vi.fn().mockResolvedValue(undefined),
      matchAll: vi.fn().mockResolvedValue(clients),
      openWindow,
    },
    skipWaiting: vi.fn().mockResolvedValue(undefined),
    addEventListener: (name, handler) => {
      listeners[name] = handler;
    },
  };
  const fetch = vi.fn();
  vm.runInNewContext(fs.readFileSync(workerPath, "utf8"), {
    self,
    indexedDB: createIndexedDb(indexedDbState),
    URL,
    Set,
    Date,
    Promise,
    fetch,
    queueMicrotask,
  });
  return { listeners, self, openWindow, showNotification, fetch, indexedDbState };
}

async function dispatch(handler, event) {
  let work;
  handler({ ...event, waitUntil: (promise) => { work = promise; } });
  await work;
}

describe("Madar Push service worker", () => {
  it("shows only the canonical action and never carries arbitrary Push data", async () => {
    const harness = loadWorker();
    await dispatch(harness.listeners.push, {
      data: {
        json: () => ({
          title: "New form submission",
          body: "Open Madar to view details.",
          tag: "madar-event:event-1",
          data: {
            action: { kind: "form_submission", object_id: "form-1", path: "/notifications" },
            answers: { secret: "must-not-survive" },
          },
        }),
      },
    });
    expect(harness.showNotification).toHaveBeenCalledWith(
      "New form submission",
      expect.objectContaining({
        data: {
          action: { kind: "form_submission", object_id: "form-1", path: "/notifications" },
        },
        tag: "madar-event:event-1",
      })
    );
    expect(JSON.stringify(harness.showNotification.mock.calls[0])).not.toContain("must-not-survive");
  });

  it("focuses and navigates an existing same-origin app client", async () => {
    const external = { url: "https://customer.example.test/", focus: vi.fn(), navigate: vi.fn() };
    const appClient = {
      url: "https://app.example.test/dashboard",
      navigate: vi.fn().mockResolvedValue(undefined),
      focus: vi.fn().mockResolvedValue(undefined),
    };
    const harness = loadWorker({ clients: [external, appClient] });
    const close = vi.fn();
    await dispatch(harness.listeners.notificationclick, {
      notification: {
        close,
        data: { action: { kind: "reservation", object_id: "r-1", path: "/notifications" } },
      },
    });
    expect(close).toHaveBeenCalledTimes(1);
    expect(external.navigate).not.toHaveBeenCalled();
    expect(external.focus).not.toHaveBeenCalled();
    expect(appClient.navigate).toHaveBeenCalledWith("https://app.example.test/notifications");
    expect(appClient.focus).toHaveBeenCalledTimes(1);
    expect(harness.openWindow).not.toHaveBeenCalled();
  });

  it("falls back to the same-origin notification center for unsafe actions", async () => {
    const harness = loadWorker();
    await dispatch(harness.listeners.notificationclick, {
      notification: {
        close: vi.fn(),
        data: { action: { kind: "reservation", path: "https://evil.example/steal" } },
      },
    });
    expect(harness.openWindow).toHaveBeenCalledWith(
      "https://app.example.test/notifications"
    );
  });

  it("opens calendar notifications directly in the mobile-safe calendar route", async () => {
    const harness = loadWorker();
    await dispatch(harness.listeners.notificationclick, {
      notification: {
        close: vi.fn(),
        data: {
          action: { kind: "calendar_task", object_id: "task-1", path: "/calendar" },
        },
      },
    });
    expect(harness.openWindow).toHaveBeenCalledWith("https://app.example.test/calendar");
  });

  it("records rotation locally and asks only same-origin pages to reconcile", async () => {
    const sameOrigin = { url: "https://app.example.test/dashboard", postMessage: vi.fn() };
    const otherOrigin = { url: "https://customer.example.test/", postMessage: vi.fn() };
    const harness = loadWorker({ clients: [sameOrigin, otherOrigin] });
    await dispatch(harness.listeners.pushsubscriptionchange, {});
    expect(harness.indexedDbState["rotation-needed"]).toMatchObject({ needed: true });
    expect(sameOrigin.postMessage).toHaveBeenCalledWith({
      type: "MADAR_PUSH_RECONCILE_REQUIRED",
    });
    expect(otherOrigin.postMessage).not.toHaveBeenCalled();
    expect(harness.fetch).not.toHaveBeenCalled();
  });

  it("does not crash on malformed Push JSON", async () => {
    const harness = loadWorker();
    await dispatch(harness.listeners.push, {
      data: { json: () => { throw new Error("malformed"); } },
    });
    expect(harness.showNotification).toHaveBeenCalledWith(
      "Madar notification",
      expect.objectContaining({
        data: { action: { kind: "notification_center", path: "/notifications" } },
      })
    );
  });
});
