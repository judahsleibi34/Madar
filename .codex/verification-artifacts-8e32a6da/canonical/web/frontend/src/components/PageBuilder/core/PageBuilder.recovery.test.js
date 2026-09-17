import { beforeEach, describe, expect, it } from "vitest";

import {
  BUILDER_RECOVERY_MAX_AGE_MS,
  classifyBuilderRecovery,
  clearBuilderRecovery,
  createBuilderRecoveryEnvelope,
  detectLegacyBuilderDraft,
  getBuilderRecoveryStorageKey,
  hashBuilderRecoverySchema,
  parseBuilderRecoveryEnvelope,
  readBuilderRecovery,
  resolveBackendFirstBuilderHydration,
  writeBuilderRecovery,
} from "./PageBuilder.recovery";

const context = {
  userId: "user-1",
  tenantId: "tenant-1",
  projectId: "project-1",
  baseDraftRevision: 12,
  baseSchemaHash: "fnv1a-test",
};

describe("builder recovery storage", () => {
  beforeEach(() => localStorage.clear());

  it("scopes recovery keys by user, tenant, and backend project", () => {
    const key = getBuilderRecoveryStorageKey(context);
    expect(key).toBe(
      "madar_app_builder_frontend_v5:user:user-1:tenant:tenant-1:project:project-1"
    );
    expect(getBuilderRecoveryStorageKey({ ...context, tenantId: "tenant-2" })).not.toBe(key);
    expect(getBuilderRecoveryStorageKey({ ...context, projectId: "project-2" })).not.toBe(key);
  });

  it("round-trips a structured envelope with revision and timestamp", () => {
    const schema = {
      name: "Portable",
      activePageId: "home",
      activeFormId: "form-1",
      activeWorkflowId: "workflow-1",
      activeRoleId: "role-1",
      pages: [{ id: "home", name: "Home", sections: [] }],
    };
    expect(writeBuilderRecovery(context, schema)).toBe(true);
    const result = readBuilderRecovery(context);
    expect(result.status).toBe("valid");
    expect(result.envelope).toMatchObject({
      version: 1,
      user_id: "user-1",
      tenant_id: "tenant-1",
      project_id: "project-1",
      base_draft_revision: 12,
      base_schema_hash: "fnv1a-test",
    });
    expect(result.envelope.schema.pages[0].id).toBe("home");
    expect(result.envelope.schema).not.toHaveProperty("activePageId");
    expect(result.envelope.schema).not.toHaveProperty("activeFormId");
    expect(result.envelope.schema).not.toHaveProperty("activeWorkflowId");
    expect(result.envelope.schema).not.toHaveProperty("activeRoleId");
  });

  it("creates a deterministic base-schema fingerprint", () => {
    const first = hashBuilderRecoverySchema({ pages: [{ id: "home" }], activePageId: "home" });
    const second = hashBuilderRecoverySchema({ pages: [{ id: "home" }], activePageId: "other" });
    expect(first).toBe(second);
    expect(first).toMatch(/^fnv1a64-[0-9a-f]{16}$/);
  });

  it("preserves recovery content exactly without applying routine cleanup", () => {
    const schema = {
      pages: [{
        id: "reports",
        name: "Reports",
        slug: "/reports",
        sections: [],
        unknownPageField: { z: 2, a: 1 },
      }],
      collections: [{ id: "collection-1", records: [{ id: "record-1" }] }],
      unknownProjectField: { keep: true },
    };
    const envelope = createBuilderRecoveryEnvelope({ ...context, schema });
    const parsed = parseBuilderRecoveryEnvelope(JSON.stringify(envelope), context);

    expect(parsed.status).toBe("valid");
    expect(parsed.envelope.schema).toEqual(schema);
  });

  it("gives reordered equivalent recovery the same semantic hash", () => {
    const left = { pages: [{ id: "home", metadata: { b: 2, a: 1 } }], theme: { z: 2, a: 1 } };
    const right = { theme: { a: 1, z: 2 }, pages: [{ metadata: { a: 1, b: 2 }, id: "home" }] };
    expect(hashBuilderRecoverySchema(left)).toBe(hashBuilderRecoverySchema(right));
    expect(hashBuilderRecoverySchema(left)).not.toBe(hashBuilderRecoverySchema({ ...right, theme: { a: 9, z: 2 } }));
  });

  it.each([
    ["userId", "another-user"],
    ["tenantId", "another-tenant"],
    ["projectId", "another-project"],
  ])("rejects recovery with mismatched %s", (field, value) => {
    const envelope = createBuilderRecoveryEnvelope({ ...context, schema: { pages: [] } });
    const result = parseBuilderRecoveryEnvelope(JSON.stringify(envelope), {
      ...context,
      [field]: value,
    });
    expect(result.status).toBe("identity_mismatch");
  });

  it("rejects malformed and expired envelopes", () => {
    expect(parseBuilderRecoveryEnvelope("not-json", context).status).toBe("malformed");
    const expired = createBuilderRecoveryEnvelope({
      ...context,
      schema: { pages: [] },
      savedAt: new Date(Date.now() - BUILDER_RECOVERY_MAX_AGE_MS - 1).toISOString(),
    });
    expect(parseBuilderRecoveryEnvelope(JSON.stringify(expired), context).status).toBe("expired");
  });

  it("classifies same-revision recovery as opt-in and stale recovery as conflict", () => {
    expect(classifyBuilderRecovery({ base_draft_revision: 12 }, 12)).toBe("restorable");
    expect(classifyBuilderRecovery({ base_draft_revision: 11 }, 12)).toBe("stale_conflict");
    expect(classifyBuilderRecovery({ base_draft_revision: 13 }, 12)).toBe("invalid");
  });

  it("always hydrates from the backend and surfaces local recovery separately", () => {
    const serverSchema = { name: "Newest cloud", pages: [] };
    const localSchema = { name: "Older browser", pages: [] };
    const result = resolveBackendFirstBuilderHydration({
      serverSchema,
      serverRevision: 12,
      recoveryResult: {
        status: "valid",
        envelope: createBuilderRecoveryEnvelope({
          ...context,
          baseDraftRevision: 11,
          schema: localSchema,
        }),
      },
    });
    expect(result).toEqual({
      schema: serverSchema,
      source: "backend",
      recoveryDecision: "stale_conflict",
    });
    expect(result.schema).not.toBe(localSchema);
  });

  it("clears a recovery only after an explicit cleanup action", () => {
    writeBuilderRecovery(context, { pages: [] });
    expect(readBuilderRecovery(context).status).toBe("valid");
    clearBuilderRecovery(context);
    expect(readBuilderRecovery(context).status).toBe("missing");
  });

  it("starts the next recovery from the adopted server revision", () => {
    writeBuilderRecovery({ ...context, baseDraftRevision: 59 }, { pages: [{ id: "local" }] });
    clearBuilderRecovery(context);
    expect(readBuilderRecovery(context).status).toBe("missing");

    writeBuilderRecovery({ ...context, baseDraftRevision: 60 }, { pages: [{ id: "server-edited" }] });
    const next = readBuilderRecovery(context);
    expect(next.status).toBe("valid");
    expect(next.envelope.base_draft_revision).toBe(60);
  });

  it("detects legacy drafts but never attaches them to a project", () => {
    localStorage.setItem("madar_app_builder_frontend_v4:user:user-1", JSON.stringify({ name: "Legacy" }));
    const legacy = detectLegacyBuilderDraft("user-1");
    expect(legacy).toMatchObject({ exists: true, key: "madar_app_builder_frontend_v4:user:user-1" });
    expect(readBuilderRecovery(context).status).toBe("missing");
  });
});
