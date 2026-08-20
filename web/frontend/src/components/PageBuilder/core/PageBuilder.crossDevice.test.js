import { describe, expect, it } from "vitest";

import {
  createBuilderProjectPayload,
  validateBuilderSaveAcknowledgement,
} from "./PageBuilder.persistence";
import { cleanBuilderProject, getDraftProjectFromRecord } from "./PageBuilder.project";
import {
  createBuilderRecoveryEnvelope,
  resolveBackendFirstBuilderHydration,
} from "./PageBuilder.recovery";

const completeProject = {
  name: "Portable project",
  slug: "portable-project",
  directLayoutVersion: 4,
  activePageId: "page-2",
  activeFormId: "form-1",
  defaultPageId: "home",
  theme: { colors: { primary: "#123456" }, customThemeField: true },
  siteChrome: { brand: "Portable", footerShopLinks: "Home\nContact" },
  pages: [
    {
      id: "home",
      name: "Home",
      slug: "/",
      sections: [{
        id: "hero",
        mode: "direct",
        layout: { minHeightByViewport: { desktop: 700, tablet: 560, mobile: 480 } },
        freeElements: [{
          id: "heading",
          type: "heading",
          content: "Home",
          position: {
            desktop: { x: 20, y: 20, width: 500, height: 80 },
            tablet: { x: 16, y: 16, width: 400, height: 70 },
            mobile: { x: 12, y: 12, width: 300, height: 60 },
          },
        }],
      }],
    },
    {
      id: "page-2",
      name: "Book",
      slug: "/book",
      sections: [{
        id: "booking",
        mode: "direct",
        freeElements: [
          { id: "form-block", type: "formBlock", connectedFormId: "form-1" },
          { id: "reservation", type: "reservationBlock", reservation: { exclusive: true } },
          { id: "button", type: "button", action: { type: "goToPage", pageId: "home" } },
        ],
      }],
    },
  ],
  forms: [{ id: "form-1", title: "Contact", sections: [{ id: "fields", fields: [] }] }],
  workflows: [{ id: "workflow-1", name: "Follow up" }],
  roles: [{ id: "role-1", name: "Editor" }],
  customSupportedField: { keep: "yes" },
};

describe("cross-device builder persistence", () => {
  it("round-trips complete project configuration through the backend schema", () => {
    const deviceA = cleanBuilderProject(completeProject);
    const payload = createBuilderProjectPayload({
      project: deviceA,
      builderProjectRecord: { id: "backend-project", draft_revision: 7 },
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });
    expect(payload.expected_revision).toBe(7);
    expect(payload.draft_schema).not.toHaveProperty("activePageId");
    const deviceB = getDraftProjectFromRecord({
      id: "backend-project",
      draft_revision: 8,
      draft_schema: payload.draft_schema,
    });
    expect(deviceB.pages).toEqual(payload.draft_schema.pages);
    expect(deviceB.theme).toMatchObject(completeProject.theme);
    expect(deviceB.siteChrome).toMatchObject(completeProject.siteChrome);
    expect(deviceB.forms).toEqual(deviceA.forms);
    expect(deviceB.customSupportedField).toEqual({ keep: "yes" });
  });

  it("never lets Device A stale recovery replace Device B cloud changes", () => {
    const cloudFromDeviceB = { ...completeProject, name: "Changed on Device B" };
    const recoveryFromDeviceA = createBuilderRecoveryEnvelope({
      userId: "user-1",
      tenantId: "tenant-1",
      projectId: "backend-project",
      baseDraftRevision: 7,
      schema: completeProject,
    });
    const hydration = resolveBackendFirstBuilderHydration({
      serverSchema: cloudFromDeviceB,
      serverRevision: 8,
      recoveryResult: { status: "valid", envelope: recoveryFromDeviceA },
    });
    expect(hydration.schema.name).toBe("Changed on Device B");
    expect(hydration.recoveryDecision).toBe("stale_conflict");
  });

  it("round-trips a one-page cloud draft to three pages using consecutive revisions", () => {
    const projectId = "3023144a-6f48-46ee-90ed-fe712f51283a";
    const revisionFive = {
      id: projectId,
      draft_revision: 5,
      draft_schema: {
        ...completeProject,
        pages: [completeProject.pages[0]],
      },
    };
    const deviceA = getDraftProjectFromRecord(revisionFive);
    const threePageDraft = {
      ...deviceA,
      pages: [
        ...deviceA.pages,
        completeProject.pages[1],
        { id: "page-3", name: "Page 3", slug: "/page-3", sections: [] },
      ],
    };
    const firstPayload = createBuilderProjectPayload({
      project: threePageDraft,
      builderProjectRecord: revisionFive,
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });
    expect(firstPayload.expected_revision).toBe(5);
    expect(firstPayload.draft_schema.pages).toHaveLength(3);

    const revisionSix = {
      ...revisionFive,
      draft_revision: 6,
      draft_schema: firstPayload.draft_schema,
    };
    expect(validateBuilderSaveAcknowledgement({
      projectId,
      previousRevision: 5,
      savedRecord: revisionSix,
    })).toBe(6);
    const cleanDeviceB = getDraftProjectFromRecord(revisionSix);
    expect(cleanDeviceB.pages.map((page) => page.name)).toEqual(["Home", "Book", "Page 3"]);

    const renamedOnDeviceB = {
      ...cleanDeviceB,
      pages: cleanDeviceB.pages.map((page) =>
        page.id === "page-3" ? { ...page, name: "Renamed" } : page
      ),
    };
    const secondPayload = createBuilderProjectPayload({
      project: renamedOnDeviceB,
      builderProjectRecord: revisionSix,
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });
    expect(secondPayload.expected_revision).toBe(6);
    expect(secondPayload.draft_schema.pages[2].name).toBe("Renamed");
  });
});
