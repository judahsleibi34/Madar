import { describe, expect, it, vi } from "vitest";

import {
  adoptBuilderServerRuntime,
  prepareBuilderServerAdoption,
  runBuilderAutomaticRebase,
} from "./PageBuilder.conflict";
import { createBuilderProjectPayload } from "./PageBuilder.persistence";

const ref = (current) => ({ current });

describe("atomic builder server adoption", () => {
  it("rejects the wrong project and invalid revisions", () => {
    expect(() => prepareBuilderServerAdoption({
      serverRecord: { id: "other", draft_revision: 60 },
      routedProjectId: "project-1",
      normalizeProject: () => ({}),
      createSnapshot: JSON.stringify,
    })).toThrow(/routed project/);
    expect(() => prepareBuilderServerAdoption({
      serverRecord: { id: "project-1", draft_revision: "bad" },
      routedProjectId: "project-1",
      normalizeProject: () => ({}),
      createSnapshot: JSON.stringify,
    })).toThrow(/revision/);
  });

  it("adopts revision 60 only after clearing every revision-59 write path", () => {
    const adoption = prepareBuilderServerAdoption({
      serverRecord: {
        id: "project-1",
        draft_revision: 60,
        draft_schema: { pages: [{ id: "home" }], activePageId: "home" },
      },
      routedProjectId: "project-1",
      normalizeProject: (record) => ({ ...record.draft_schema, activePageId: "home" }),
      createSnapshot: JSON.stringify,
    });
    const refs = {
      builderProjectRecord: ref({ id: "project-1", draft_revision: 59 }),
      backendDraftRevision: ref(59),
      requestGeneration: ref(4),
      project: ref({ pages: [{ id: "local" }] }),
      baseSchema: ref({ pages: [{ id: "old" }] }),
      acknowledgedSnapshot: ref("revision-59"),
      pendingSnapshot: ref("stale"),
      pendingRequest: ref({ expected_revision: 59 }),
      activeSnapshot: ref("stale"),
      savePromise: ref(Promise.resolve()),
      saveInFlight: ref(true),
      pendingExternalDraft: ref({ baseDraftRevision: 59 }),
      externalDraftRevisions: ref(new Map([["old-tab", 4]])),
      hydrationComplete: ref(false),
      conflict: ref(true),
    };
    const stopScheduling = vi.fn(() => expect(refs.conflict.current).toBe(true));

    adoptBuilderServerRuntime({ adoption, refs, stopScheduling });

    expect(stopScheduling).toHaveBeenCalledOnce();
    expect(refs.builderProjectRecord.current.draft_revision).toBe(60);
    expect(refs.backendDraftRevision.current).toBe(60);
    expect(refs.requestGeneration.current).toBe(5);
    expect(refs.acknowledgedSnapshot.current).toBe(adoption.snapshot);
    expect(refs.baseSchema.current).toEqual(adoption.persistableProject);
    expect(refs.pendingRequest.current).toBeNull();
    expect(refs.saveInFlight.current).toBe(false);
    expect(refs.externalDraftRevisions.current.size).toBe(0);
    expect(refs.hydrationComplete.current).toBe(true);
    expect(refs.conflict.current).toBe(false);

    const edited = {
      ...refs.project.current,
      pages: refs.project.current.pages.map((page) => ({ ...page, label: "New edit" })),
    };
    const payload = createBuilderProjectPayload({
      project: edited,
      builderProjectRecord: {
        ...refs.builderProjectRecord.current,
        draft_revision: refs.backendDraftRevision.current,
      },
      getBuilderProjectName: () => "Project",
      getBuilderProjectSlug: () => "project",
    });
    expect(payload.expected_revision).toBe(60);
  });

  it("sends one revision-60 save after a revision-59 conflict is resolved", async () => {
    const put = vi.fn()
      .mockRejectedValueOnce(Object.assign(new Error("conflict"), {
        code: "project_revision_conflict",
        context: { current_revision: 60 },
      }))
      .mockResolvedValueOnce({ id: "project-1", draft_revision: 61 });
    let terminalConflict = false;

    await put({ expected_revision: 59 }).catch(() => { terminalConflict = true; });
    if (!terminalConflict) await put({ expected_revision: 59 });
    expect(put).toHaveBeenCalledTimes(1);

    const adoption = prepareBuilderServerAdoption({
      serverRecord: {
        id: "project-1",
        draft_revision: 60,
        draft_schema: { pages: [{ id: "home", buttonLabel: "Before" }] },
      },
      routedProjectId: "project-1",
      normalizeProject: (record) => record.draft_schema,
      createSnapshot: JSON.stringify,
    });
    const refs = {
      builderProjectRecord: ref({ id: "project-1", draft_revision: 59 }),
      backendDraftRevision: ref(59),
      requestGeneration: ref(9),
      project: ref({}),
      baseSchema: ref({ pages: [] }),
      acknowledgedSnapshot: ref("old"),
      pendingSnapshot: ref("stale"),
      pendingRequest: ref({ expected_revision: 59 }),
      activeSnapshot: ref("stale"),
      savePromise: ref(null),
      saveInFlight: ref(false),
      pendingExternalDraft: ref(null),
      externalDraftRevisions: ref(new Map()),
      hydrationComplete: ref(false),
      conflict: ref(true),
    };
    adoptBuilderServerRuntime({ adoption, refs });
    expect(refs.requestGeneration.current).toBe(10);
    expect(put).toHaveBeenCalledTimes(1); // adoption itself is read-only

    const edited = {
      ...refs.project.current,
      pages: [{ ...refs.project.current.pages[0], buttonLabel: "After" }],
    };
    const payload = createBuilderProjectPayload({
      project: edited,
      builderProjectRecord: {
        ...refs.builderProjectRecord.current,
        draft_revision: refs.backendDraftRevision.current,
      },
      getBuilderProjectName: () => "Project",
      getBuilderProjectSlug: () => "project",
    });
    const acknowledgement = await put(payload);
    expect(payload.expected_revision).toBe(60);
    expect(acknowledgement.draft_revision).toBe(61);
    expect(put).toHaveBeenCalledTimes(2);
  });
});

describe("automatic builder conflict rebase", () => {
  const baseSchema = {
    pages: [{
      id: "home",
      navigationLabel: "Home",
      sections: [{ id: "hero", freeElements: [{ id: "button", content: "Start" }] }],
    }],
  };
  const localSchema = {
    ...baseSchema,
    pages: baseSchema.pages.map((page) => ({
      ...page,
      sections: page.sections.map((section) => ({
        ...section,
        freeElements: section.freeElements.map((block) => ({ ...block, content: "Final Test??" })),
      })),
    })),
  };
  const serverSchema = {
    ...baseSchema,
    pages: baseSchema.pages.map((page) => ({ ...page, navigationLabel: "Welcome" })),
  };

  const run = ({
    updateServerProject = vi.fn(),
    local = localSchema,
    server = serverSchema,
    isCurrent = () => true,
  } = {}) =>
    runBuilderAutomaticRebase({
      baseSchema,
      localSchema: local,
      routedProjectId: "project-1",
      fetchServerProject: vi.fn().mockResolvedValue({
        id: "project-1",
        draft_revision: 71,
        draft_schema: server,
      }),
      normalizeServerSchema: (record) => record.draft_schema,
      prepareMergedProject: (schema) => schema,
      createRetryPayload: ({ mergedProject, serverRevision }) => ({
        expected_revision: serverRevision,
        draft_schema: mergedProject,
      }),
      updateServerProject,
      isCurrent,
      validateAcknowledgement: ({ previousRevision, savedRecord }) => {
        expect(savedRecord.draft_revision).toBe(previousRevision + 1);
        return savedRecord.draft_revision;
      },
    });

  it("rebases revision-70 local edits onto revision 71 and retries exactly once", async () => {
    const updateServerProject = vi.fn().mockImplementation(async (_projectId, payload) => ({
      id: "project-1",
      draft_revision: 72,
      draft_schema: payload.draft_schema,
    }));
    const result = await run({ updateServerProject });

    expect(result.status).toBe("saved");
    expect(updateServerProject).toHaveBeenCalledTimes(1);
    const payload = updateServerProject.mock.calls[0][1];
    expect(payload.expected_revision).toBe(71);
    expect(payload.draft_schema.pages[0].navigationLabel).toBe("Welcome");
    expect(payload.draft_schema.pages[0].sections[0].freeElements[0].content).toBe("Final Test??");
    expect(result.savedRevision).toBe(72);
  });

  it("does not retry when both sessions changed the same field", async () => {
    const updateServerProject = vi.fn();
    const local = {
      ...baseSchema,
      pages: baseSchema.pages.map((page) => ({ ...page, navigationLabel: "Local" })),
    };
    const server = {
      ...baseSchema,
      pages: baseSchema.pages.map((page) => ({ ...page, navigationLabel: "Server" })),
    };
    const result = await run({ updateServerProject, local, server });
    expect(result.status).toBe("conflict");
    expect(result.mergeResult.conflicts[0].path).toBe("pages[id=home].navigationLabel");
    expect(updateServerProject).not.toHaveBeenCalled();
  });

  it("stops after one merged retry if the server advances again", async () => {
    const secondConflict = Object.assign(new Error("conflict again"), {
      code: "project_revision_conflict",
      context: { current_revision: 72 },
    });
    const updateServerProject = vi.fn().mockRejectedValue(secondConflict);
    await expect(run({ updateServerProject })).rejects.toBe(secondConflict);
    expect(updateServerProject).toHaveBeenCalledTimes(1);
    expect(secondConflict.builderMergeState.serverRecord.draft_revision).toBe(71);
  });

  it("does not dispatch a merged PUT when the rebase GET becomes obsolete", async () => {
    const updateServerProject = vi.fn();
    const result = await run({ updateServerProject, isCurrent: () => false });
    expect(result).toEqual({ status: "obsolete" });
    expect(updateServerProject).not.toHaveBeenCalled();
  });
});
