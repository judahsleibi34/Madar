import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { assertIsolatedE2EEnvironment } from "./safety.mjs";

function safeEnvironment(overrides = {}) {
  return {
    MADAR_E2E_CONFIRM_ISOLATED: "YES",
    MADAR_E2E_BASE_URL: "http://127.0.0.1:5173",
    MADAR_E2E_DATABASE_ID: "madar_e2e_local_20260720",
    MADAR_E2E_RUN_ID: "run_20260720_001",
    MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN: "YES",
    MADAR_E2E_EXTERNAL_DELIVERY_DISABLED: "YES",
    ...overrides,
  };
}

describe("isolated E2E safety contract", () => {
  it("accepts an explicitly isolated local target", () => {
    assert.deepEqual(assertIsolatedE2EEnvironment(safeEnvironment()), {
      baseUrl: "http://127.0.0.1:5173",
      databaseId: "madar_e2e_local_20260720",
      runId: "run_20260720_001",
    });
  });

  for (const baseUrl of [
    "https://madar.com",
    "https://app.madar.com",
    "https://production.example.test",
  ]) {
    it(`rejects forbidden target ${baseUrl}`, () => {
      assert.throws(
        () =>
          assertIsolatedE2EEnvironment(
            safeEnvironment({
              MADAR_E2E_BASE_URL: baseUrl,
              MADAR_E2E_PRODUCTION_HOSTS: "production.example.test",
            })
          ),
        /forbidden production host/
      );
    });
  }

  it("rejects missing isolation confirmation", () => {
    assert.throws(
      () => assertIsolatedE2EEnvironment(safeEnvironment({ MADAR_E2E_CONFIRM_ISOLATED: "no" })),
      /must be exactly YES/
    );
  });

  it("rejects shared database labels", () => {
    assert.throws(
      () =>
        assertIsolatedE2EEnvironment(
          safeEnvironment({ MADAR_E2E_DATABASE_ID: "madar_e2e_shared_database" })
        ),
      /forbidden shared\/production label/
    );
  });

  it("requires clean migrations and disabled external delivery attestations", () => {
    assert.throws(
      () =>
        assertIsolatedE2EEnvironment(
          safeEnvironment({ MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN: "NO" })
        ),
      /MIGRATIONS_APPLIED_FROM_CLEAN/
    );
    assert.throws(
      () =>
        assertIsolatedE2EEnvironment(
          safeEnvironment({ MADAR_E2E_EXTERNAL_DELIVERY_DISABLED: "NO" })
        ),
      /EXTERNAL_DELIVERY_DISABLED/
    );
  });
});
