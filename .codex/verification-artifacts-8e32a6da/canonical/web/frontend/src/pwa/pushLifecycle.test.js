import { describe, expect, it } from "vitest";

import {
  clearPushRotationNeeded,
  readPushRotationNeeded,
} from "./pushLifecycle";

function createIndexedDb(initialValue) {
  const state = { "rotation-needed": initialValue };
  const database = {
    objectStoreNames: { contains: () => true },
    close: () => {},
    transaction: () => {
      const transaction = {
        error: null,
        objectStore: () => ({
          get: (key) => {
            const request = { result: state[key], error: null };
            queueMicrotask(() => request.onsuccess?.());
            return request;
          },
          delete: (key) => {
            delete state[key];
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
      queueMicrotask(() => request.onsuccess?.());
      return request;
    },
  };
}

describe("Push rotation lifecycle marker", () => {
  it("reads and clears a persisted rotation marker", async () => {
    const indexedDb = createIndexedDb({ needed: true });
    await expect(readPushRotationNeeded(indexedDb)).resolves.toBe(true);
    await expect(clearPushRotationNeeded(indexedDb)).resolves.toBe(true);
    await expect(readPushRotationNeeded(indexedDb)).resolves.toBe(false);
  });

  it("fails closed and non-fatally when IndexedDB is unavailable", async () => {
    await expect(readPushRotationNeeded(null)).resolves.toBe(false);
    await expect(clearPushRotationNeeded(null)).resolves.toBe(false);
  });
});
