import { beforeEach, describe, expect, it } from "vitest";

import { persistBuilderProject } from "./PageBuilder.persistence";
import { getBuilderDraftReadStatus, loadInitialProject } from "./PageBuilder.storage";

const STORAGE_KEY = "madar_app_builder_frontend_v4:user:data-safety-test";

const createFixture = ({
  id = "project-current",
  extra = {},
  forms = [],
  pages = null,
  elementExtra = {},
} = {}) => ({
  id,
  name: "Safety fixture",
  status: "draft",
  directLayoutVersion: 4,
  activePageId: "page-home",
  activeFormId: forms[0]?.id || "",
  activeCollectionId: "",
  activeWorkflowId: "",
  activeRoleId: "",
  siteChrome: { brandName: "Fixture", unknownChromeField: "keep-chrome" },
  theme: { mode: "light", unknownThemeField: "keep-theme" },
  pages: pages || [
    {
      id: "page-home",
      name: "Home",
      slug: "/",
      canvasLayoutVersion: 1,
      unknownPageField: "keep-page",
      sections: [
        {
          id: "section-home",
          name: "Page Canvas",
          isPageCanvas: true,
          mode: "direct",
          unknownSectionField: "keep-section",
          layout: {
            width: "full",
            minHeight: 840,
            minHeightByViewport: { desktop: 840, tablet: 760, mobile: 920 },
            unknownLayoutField: "keep-layout",
          },
          rows: [],
          freeElements: [
            {
              id: "element-text",
              type: "text",
              name: "Text",
              content: "Preserve me",
              mode: "direct",
              position: {
                desktop: { x: 24, y: 40, width: 380, height: 104 },
                tablet: { x: 20, y: 36, width: 320, height: 112 },
                mobile: { x: 12, y: 32, width: 300, height: 128 },
              },
              styles: { color: "#123456", animation: "fade" },
              unknownElementField: "keep-element",
              ...elementExtra,
            },
          ],
        },
      ],
    },
  ],
  forms,
  collections: [],
  workflows: [],
  roles: [],
  users: [],
  publish: { environment: "local", lastSavedAt: "", lastPublishedAt: "" },
  unknownProjectField: "keep-project",
  ...extra,
});

const collectIds = (project) => ({
  projectId: project.id,
  pageIds: project.pages.map((page) => page.id),
  sectionIds: project.pages.flatMap((page) => page.sections.map((section) => section.id)),
  elementIds: project.pages.flatMap((page) =>
    page.sections.flatMap((section) => (section.freeElements || []).map((element) => element.id))
  ),
  formIds: (project.forms || []).map((form) => form.id),
});

const roundTrip = (fixture) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(fixture));
  const loaded = loadInitialProject(STORAGE_KEY);
  const beforeIds = collectIds(loaded);
  const edited = { ...loaded, name: `${loaded.name} edited` };

  persistBuilderProject({
    nextProject: edited,
    demoMode: false,
    storageKey: STORAGE_KEY,
    setProject: () => undefined,
    showToast: () => undefined,
    silent: true,
  });

  const reloaded = loadInitialProject(STORAGE_KEY);
  expect(reloaded).toEqual(edited);
  expect(collectIds(reloaded)).toEqual(beforeIds);
  expect(reloaded.pages.length).toBe(loaded.pages.length);
  expect(reloaded.pages.flatMap((page) => page.sections).length)
    .toBe(loaded.pages.flatMap((page) => page.sections).length);
  expect(reloaded.pages.flatMap((page) => page.sections.flatMap((section) => section.freeElements || [])).length)
    .toBe(loaded.pages.flatMap((page) => page.sections.flatMap((section) => section.freeElements || [])).length);
  expect(reloaded.pages[0].sections[0].layout.minHeightByViewport)
    .toEqual(loaded.pages[0].sections[0].layout.minHeightByViewport);
  expect(reloaded.unknownProjectField).toBe("keep-project");
  expect(reloaded.pages[0].unknownPageField).toBe("keep-page");
  expect(reloaded.pages[0].sections[0].unknownSectionField).toBe("keep-section");
  expect(reloaded.pages[0].sections[0].freeElements[0].unknownElementField).toBe("keep-element");
  return reloaded;
};

describe("builder project data safety", () => {
  beforeEach(() => localStorage.clear());

  it.each([
    ["older project with optional fields absent", createFixture({ extra: { directLayoutVersion: undefined } })],
    ["current project", createFixture()],
    ["unknown extra fields", createFixture({ extra: { futureFeature: { enabled: true } } })],
    ["forms", createFixture({ forms: [{ id: "form-contact", title: "Contact", sections: [], unknownFormField: "keep-form" }] })],
    ["responsive geometry", createFixture()],
    ["multiple pages and sections", createFixture({ pages: [
      createFixture().pages[0],
      { ...createFixture().pages[0], id: "page-two", name: "Page two", slug: "/two", sections: [
        { ...createFixture().pages[0].sections[0], id: "section-two", freeElements: [
          { ...createFixture().pages[0].sections[0].freeElements[0], id: "element-two" },
        ] },
      ] },
    ] })],
    ["animation settings", createFixture({ elementExtra: { autoScroll: true, autoScrollMs: 7000 } })],
    ["local unsaved metadata", createFixture({ extra: { localDraftMetadata: { dirty: true, revision: 12 } } })],
  ])("survives load-edit-save-reload: %s", (_name, fixture) => {
    const reloaded = roundTrip(fixture);
    expect(reloaded.futureFeature).toEqual(fixture.futureFeature);
    if (fixture.forms[0]?.unknownFormField) {
      expect(reloaded.forms[0].unknownFormField).toBe("keep-form");
    }
  });

  it("keeps an unreadable primary draft byte-for-byte and loads a valid backup", () => {
    const rawCorruptDraft = "{not-valid-json";
    const backup = createFixture({ id: "backup-project" });
    localStorage.setItem(STORAGE_KEY, rawCorruptDraft);
    localStorage.setItem(`${STORAGE_KEY}:backup`, JSON.stringify(backup));

    const loaded = loadInitialProject(STORAGE_KEY);

    expect(loaded.id).toBe("backup-project");
    expect(localStorage.getItem(STORAGE_KEY)).toBe(rawCorruptDraft);
    expect(JSON.parse(localStorage.getItem(`${STORAGE_KEY}:backup`)).id).toBe("backup-project");
  });

  it("never overwrites unreadable primary and backup values with defaults", () => {
    const rawPrimary = "{broken-primary";
    const rawBackup = "{broken-backup";
    localStorage.setItem(STORAGE_KEY, rawPrimary);
    localStorage.setItem(`${STORAGE_KEY}:backup`, rawBackup);

    loadInitialProject(STORAGE_KEY);

    expect(localStorage.getItem(STORAGE_KEY)).toBe(rawPrimary);
    expect(localStorage.getItem(`${STORAGE_KEY}:backup`)).toBe(rawBackup);
    expect(getBuilderDraftReadStatus(STORAGE_KEY)).toBe("unrecoverable");
  });
});
