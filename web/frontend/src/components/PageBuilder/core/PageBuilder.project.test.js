import { describe, expect, it } from "vitest";
import { createElement, createPage, createSection } from "./PageBuilder.factories";
import { getSectionElements } from "./PageBuilder.layout";
import {
  buildFormConnectionUpdate,
  cleanBuilderProject,
  getDraftProjectFromRecord,
  normalizeBuilderProjectShape,
  repairDuplicateProjectIds,
} from "./PageBuilder.project";

describe("cleanBuilderProject", () => {
  it("ignores legacy server editor selection and hydrates the persisted default locally", () => {
    const loaded = getDraftProjectFromRecord({
      status: "draft",
      draft_schema: {
        activePageId: "page-2",
        activeFormId: "form-2",
        activeWorkflowId: "workflow-2",
        activeRoleId: "role-2",
        defaultPageId: "home",
        pages: [
          { id: "home", name: "Home", isDefault: true, sections: [] },
          { id: "page-2", name: "Page 2", sections: [] },
        ],
        forms: [{ id: "form-1" }, { id: "form-2" }],
        workflows: [{ id: "workflow-1" }, { id: "workflow-2" }],
        roles: [{ id: "role-1" }, { id: "role-2" }],
      },
    });

    expect(loaded.activePageId).toBe("home");
    expect(loaded.activeFormId).toBe("form-1");
    expect(loaded.activeWorkflowId).toBe("workflow-1");
    expect(loaded.activeRoleId).toBe("role-1");
    expect(loaded.defaultPageId).toBe("home");
  });

  it("normalizes legacy button actions without moving page-owned blocks", () => {
    const normalized = normalizeBuilderProjectShape({
      pages: [
        { id: "home", name: "Home", sections: [{ freeElements: [{ id: "heading", type: "heading" }] }] },
        { id: "buttons", name: "Buttons", sections: [{ freeElements: [{
          id: "button",
          type: "button",
          action: { actionType: "page", targetPageId: "home" },
        }] }] },
      ],
      forms: [],
    });

    expect(normalized.pages[0].sections[0].freeElements.map((item) => item.id)).toEqual(["heading"]);
    expect(normalized.pages[1].sections[0].freeElements[0].action).toMatchObject({
      type: "goToPage",
      pageId: "home",
    });
  });

  it("keeps the public homepage out of members-only role access", () => {
    const normalized = normalizeBuilderProjectShape({
      defaultPageId: "home",
      pages: [
        { id: "home", name: "Home", isDefault: true, sections: [] },
        { id: "members", name: "Members", sections: [] },
      ],
      roles: [{
        id: "member",
        resourceAccess: { pageIds: ["home", "members"], formIds: [] },
      }],
    });

    expect(normalized.roles[0].resourceAccess.pageIds).toEqual(["members"]);
  });

  it("normalizes explicit button colors on draft reload without adding defaults", () => {
    const normalized = normalizeBuilderProjectShape({
      pages: [{
        id: "home",
        sections: [{ freeElements: [
          { id: "custom", type: "button", backgroundColor: "#aabbcc", textColor: "#ffffff" },
          { id: "legacy", type: "button" },
        ] }],
      }],
      forms: [],
    });
    const [custom, legacy] = normalized.pages[0].sections[0].freeElements;
    expect(custom).toMatchObject({ backgroundColor: "#AABBCC", textColor: "#FFFFFF" });
    expect(legacy).not.toHaveProperty("backgroundColor");
    expect(legacy).not.toHaveProperty("textColor");
  });

  it("repairs duplicate font-size history and the Enter-saved all-H1 pattern", () => {
    const normalized = normalizeBuilderProjectShape({
      pages: [{
        id: "home",
        name: "Home",
        sections: [{ freeElements: [{
          id: "mixed-copy",
          type: "text",
          headingLevel: 1,
          content: "Build. Engage. Understand.\ndad",
          textBlockFormats: ["h1", "h1"],
          richTextSizes: [
            { field: "content", itemIndex: null, start: 0, end: 30, fontSize: "17px" },
            { field: "content", itemIndex: null, start: 0, end: 30, fontSize: "32px" },
            { field: "content", itemIndex: null, start: 0, end: 30, fontSize: "11px" },
          ],
        }] }],
      }],
    });
    const element = normalized.pages[0].sections[0].freeElements[0];

    expect(element.textBlockFormats).toEqual(["h1", "text"]);
    expect(element.richTextSizes).toEqual([
      { field: "content", itemIndex: null, start: 0, end: 30, fontSize: "11px" },
    ]);
  });

  it("removes persisted text sizes outside the supported builder range", () => {
    const normalized = normalizeBuilderProjectShape({
      pages: [{
        id: "home",
        sections: [{ freeElements: [{
          id: "copy",
          type: "text",
          styles: { fontSize: "257px" },
          richTextSizes: [
            { field: "content", start: 0, end: 4, fontSize: "256px" },
            { field: "content", start: 4, end: 8, fontSize: "999px" },
          ],
        }] }],
      }],
    });
    const element = normalized.pages[0].sections[0].freeElements[0];

    expect(element.styles).not.toHaveProperty("fontSize");
    expect(element.richTextSizes).toEqual([
      { field: "content", start: 0, end: 4, fontSize: "256px" },
      { field: "content", start: 4, end: 8 },
    ]);
  });

  it("repairs the doubled newline produced by an empty editable paragraph", () => {
    const normalized = normalizeBuilderProjectShape({
      pages: [{
        id: "home",
        sections: [{ freeElements: [{
          id: "copy",
          type: "text",
          content: "Title\n\n\nBody",
          textBlockFormats: ["h2", "text", "text"],
        }] }],
      }],
    });

    expect(normalized.pages[0].sections[0].freeElements[0].content).toBe("Title\n\nBody");
  });

  it("stores one canonical string form reference from the editor selector", () => {
    expect(buildFormConnectionUpdate(42)).toEqual({ connectedFormId: "42" });
  });

  it.each(["formId", "form_id"])(
    "normalizes legacy %s without retaining the legacy field",
    (legacyField) => {
      const normalized = normalizeBuilderProjectShape({
        forms: [{ id: 42, title: "Form 1" }],
        pages: [{
          id: 7,
          name: "Home",
          sections: [{
            rows: [{ columns: [{ elements: [{
              id: 9,
              type: "formBlock",
              [legacyField]: 42,
            }] }] }],
          }],
        }],
      });
      const block = normalized.pages[0].sections[0].rows[0].columns[0].elements[0];

      expect(normalized.forms[0].id).toBe("42");
      expect(normalized.pages[0].id).toBe("7");
      expect(block.id).toBe("9");
      expect(block.connectedFormId).toBe("42");
      expect(block).not.toHaveProperty("formId");
      expect(block).not.toHaveProperty("form_id");
    }
  );

  it("keeps an explicit disconnection and never fabricates a replacement form", () => {
    const normalized = normalizeBuilderProjectShape({
      forms: [],
      pages: [{
        id: "home",
        sections: [{ elements: [{
          id: "block-1",
          type: "formBlock",
          connectedFormId: "",
          formId: "deleted-form",
        }] }],
      }],
    });
    const block = normalized.pages[0].sections[0].rows[0].columns[0].elements[0];

    expect(normalized.forms).toEqual([]);
    expect(block.connectedFormId).toBe("");
    expect(block).not.toHaveProperty("formId");
  });

  it("never copies a later page form block onto Home during cleanup", () => {
    const project = {
      directLayoutVersion: 3,
      forms: [{ id: "form-1", title: "Form 1" }],
      pages: [
        { id: "home", name: "Home", sections: [] },
        {
          id: "contact",
          name: "Contact",
          sections: [{ elements: [{
            id: "contact-block",
            type: "formBlock",
            connectedFormId: "form-1",
          }] }],
        },
      ],
    };

    const cleanedOnce = cleanBuilderProject(project);
    const cleanedTwice = cleanBuilderProject(cleanedOnce);
    const countBlocks = (value, pageId) => value.pages
      .find((page) => page.id === pageId)
      .sections.flatMap(getSectionElements)
      .filter((element) => element.type === "formBlock").length;

    expect(countBlocks(cleanedOnce, "home")).toBe(0);
    expect(countBlocks(cleanedOnce, "contact")).toBe(1);
    expect(countBlocks(cleanedTwice, "home")).toBe(0);
    expect(countBlocks(cleanedTwice, "contact")).toBe(1);
  });

  it("repairs duplicate and missing block ids globally without changing block data or order", () => {
    const source = {
      pages: [
        { id: "home", name: "Home", sections: [{ freeElements: [
          { id: "shared", type: "heading", content: "First" },
          { id: "", type: "text", content: "Missing" },
        ] }] },
        { id: "second", name: "Page 2", sections: [{ rows: [{ columns: [{ elements: [
          { id: "shared", type: "formBlock", content: "Second", connectedFormId: "form-1" },
        ] }] }] }] },
      ],
      forms: [{ id: "form-1", title: "Form 1" }],
    };
    const before = structuredClone(source);
    const generated = ["element_missing", "element_duplicate"];
    const repaired = repairDuplicateProjectIds(source, {
      idFactory: () => generated.shift(),
    });
    const blocks = repaired.project.pages.flatMap((page) =>
      page.sections.flatMap(getSectionElements)
    );

    expect(source).toEqual(before);
    expect(blocks.map((block) => block.id)).toEqual([
      "shared",
      "element_missing",
      "element_duplicate",
    ]);
    expect(blocks.map((block) => block.content)).toEqual(["First", "Missing", "Second"]);
    expect(blocks[2].connectedFormId).toBe("form-1");
    expect(repaired.repairs).toEqual([
      expect.objectContaining({ kind: "block", oldId: "", newId: "element_missing", pageId: "home" }),
      expect.objectContaining({ kind: "block", oldId: "shared", newId: "element_duplicate", pageId: "second" }),
    ]);
  });

  it("is idempotent and preserves the first duplicate occurrence", () => {
    const source = {
      pages: [{ id: "home", sections: [{ freeElements: [
        { id: "same", type: "text", content: "First" },
        { id: "same", type: "text", content: "Second" },
      ] }] }],
      forms: [],
    };
    const once = repairDuplicateProjectIds(source, { idFactory: () => "element_repaired" });
    const twice = repairDuplicateProjectIds(once.project, {
      idFactory: () => { throw new Error("idempotent repair must not generate another id"); },
    });

    expect(once.project.pages[0].sections[0].freeElements[0].id).toBe("same");
    expect(twice.project).toEqual(once.project);
    expect(twice.repairs).toEqual([]);
  });

  it("repairs duplicate page and form ids without rewriting ambiguous references", () => {
    const ids = ["page_repaired", "form_repaired"];
    const { project, repairs } = repairDuplicateProjectIds({
      activePageId: "page-1",
      activeFormId: "form-1",
      pages: [
        { id: "page-1", name: "Home", sections: [] },
        { id: "page-1", name: "Copy", sections: [{ freeElements: [
          { id: "block-1", type: "formBlock", connectedFormId: "form-1" },
        ] }] },
      ],
      forms: [{ id: "form-1", title: "First" }, { id: "form-1", title: "Second" }],
    }, { idFactory: () => ids.shift() });

    expect(project.pages.map((page) => page.id)).toEqual(["page-1", "page_repaired"]);
    expect(project.forms.map((form) => form.id)).toEqual(["form-1", "form_repaired"]);
    expect(project.pages[1].sections[0].freeElements[0].connectedFormId).toBe("form-1");
    expect(project.activePageId).toBe("page-1");
    expect(project.activeFormId).toBe("form-1");
    expect(repairs.map((repair) => repair.kind)).toEqual(["page", "form"]);
  });

  it("deduplicates legacy elements already represented in canonical freeElements before id repair", () => {
    const project = {
      pages: [{ id: "home", sections: [{
        mode: "direct",
        elements: [{ id: "same-block", type: "text", content: "Legacy" }],
        freeElements: [{ id: "same-block", type: "text", content: "Canonical" }],
      }] }],
      forms: [],
    };

    const cleaned = cleanBuilderProject(project);
    const blocks = cleaned.pages[0].sections.flatMap(getSectionElements);
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ id: "same-block", content: "Canonical" });
  });

  it("keeps the full page canvas when it contains a Metrics component", () => {
    const heading = createElement("heading", { content: "Keep this heading" });
    const metric = createElement("metric");
    const section = createSection({
      name: "Page Canvas",
      isPageCanvas: true,
      mode: "direct",
      rows: [],
      freeElements: [heading, metric],
    });
    const page = createPage("Home", [section], { canvasLayoutVersion: 1 });

    const cleaned = cleanBuilderProject({
      name: "Metrics site",
      pages: [page],
      activePageId: page.id,
    });

    const elements = getSectionElements(cleaned.pages[0].sections[0]);

    expect(elements.map((element) => element.id)).toEqual(
      expect.arrayContaining([heading.id, metric.id])
    );
    expect(elements).toHaveLength(2);
  });

  it("keeps existing canvas elements when a new Metrics component is added", () => {
    const existing = [
      createElement("heading"),
      createElement("text"),
      createElement("image"),
    ];
    const section = createSection({
      name: "Page Canvas",
      isPageCanvas: true,
      mode: "direct",
      rows: [],
      freeElements: existing,
    });
    const page = createPage("Home", [section], { canvasLayoutVersion: 1 });
    const metric = createElement("metric");
    const projectAfterAdd = {
      name: "Metrics site",
      pages: [{
        ...page,
        sections: [{ ...section, freeElements: [...existing, metric] }],
      }],
      activePageId: page.id,
    };

    const cleaned = cleanBuilderProject(projectAfterAdd);
    const elements = getSectionElements(cleaned.pages[0].sections[0]);

    expect(elements.map((element) => element.id)).toEqual(
      expect.arrayContaining([...existing.map((element) => element.id), metric.id])
    );
    expect(elements).toHaveLength(4);
  });

  it("preserves every form page and field through save/reload normalization", () => {
    const form = {
      id: "form_full_regression",
      name: "Order intake",
      title: "Order intake",
      description: "Complete order form",
      successMessage: "Order received",
      languageMode: "bilingual",
      defaultLanguage: "en",
      pageMode: "paged",
      mode: "form",
      connectedCollectionId: "orders",
      customFormSetting: { retain: true },
      sections: [
        {
          id: "page_one",
          title: "Buyer details",
          description: "First page",
          titleStyle: { color: "#123456", fontWeight: "700" },
          fields: [
            {
              id: "buyer_name",
              type: "shortText",
              label: "Buyer name",
              required: true,
              helpText: "Legal name",
              placeholder: "Jane Doe",
              translations: { ar: { label: "اسم المشتري" } },
            },
          ],
        },
        {
          id: "page_two",
          title: "Order details",
          description: "Second page",
          fields: [
            {
              id: "currency",
              type: "radio",
              label: "Currency",
              required: true,
              options: ["EUR", "USD", "ILS"],
              translations: { ar: { options: ["يورو", "دولار", "شيكل"] } },
              visibilityRules: [{ id: "rule_1", action: "show" }],
            },
          ],
        },
      ],
      responses: [{ id: "legacy-response" }],
    };

    const cleaned = cleanBuilderProject({
      name: "Form regression project",
      forms: [form],
      activeFormId: form.id,
    });

    const savedForm = cleaned.forms[0];
    expect(savedForm.id).toBe(form.id);
    expect(savedForm.sections).toEqual(form.sections);
    expect(savedForm.sections).toHaveLength(2);
    expect(savedForm.sections.flatMap((section) => section.fields)).toHaveLength(2);
    expect(savedForm.customFormSetting).toEqual({ retain: true });
    expect(savedForm.responses).toEqual([{ id: "legacy-response" }]);
  });

  it.each(["Reports", "Orders", "Responses", "Submit Request", "Submit Report", "Place Order"])(
    "preserves a legitimate %s page and matching footer link",
    (name) => {
      const project = cleanBuilderProject({
        pages: [
          { id: "home", name: "Home", slug: "/", sections: [] },
          { id: `page-${name}`, name, slug: `/${name.toLowerCase().replaceAll(" ", "-")}`, sections: [] },
        ],
        forms: [],
        collections: [{ id: "collection-1", records: [{ id: "record-1" }] }],
        siteChrome: { footerShopLinks: name },
      });

      expect(project.pages.map((page) => page.name)).toContain(name);
      expect(project.siteChrome.footerShopLinks).toBe(name);
      expect(project.collections[0].records).toEqual([{ id: "record-1" }]);
    }
  );

  it("preserves an explicit empty page array", () => {
    expect(cleanBuilderProject({ pages: [], forms: [] }).pages).toEqual([]);
  });

  it("does not run historical layout cleanup during routine modern normalization", () => {
    const project = cleanBuilderProject({
      directLayoutVersion: 4,
      pages: [{
        id: "reports",
        name: "Reports",
        sections: [
          {
            id: "empty-direct",
            mode: "direct",
            rows: [],
            freeElements: [],
            customSectionField: { keep: true },
          },
          {
            id: "responses",
            mode: "auto",
            rows: [{ id: "row", columns: [{ id: "column", elements: [{
              id: "responses-table",
              type: "responsesTable",
              customBlockField: "keep",
            }] }] }],
          },
        ],
      }],
      forms: [],
    });

    expect(project.pages[0].sections).toHaveLength(2);
    expect(project.pages[0].sections[0].rows).toEqual([]);
    expect(project.pages[0].sections[0].customSectionField).toEqual({ keep: true });
    expect(project.pages[0].sections[1].rows[0].columns[0].elements[0]).toMatchObject({
      id: "responses-table",
      type: "responsesTable",
      customBlockField: "keep",
    });
  });

  it("normalizes malformed input deterministically without random or time-based IDs", () => {
    const source = { pages: [{ name: "Reports", sections: [{ mode: "direct", freeElements: [{ type: "text" }] }] }], forms: [{}] };
    const first = cleanBuilderProject(source);
    const second = cleanBuilderProject(source);

    expect(first).toEqual(second);
    expect(first.pages[0].id).toBe("page_page_0");
    expect(first.pages[0].sections[0].freeElements[0].id).toContain("element_page_0_section_0_free_0");
    expect(first.forms[0].id).toBe("form_form_0");
  });

  it("does not introduce responsive metadata into an existing legacy schema", () => {
    const project = cleanBuilderProject({
      pages: [{ id: "home", name: "Home", slug: "/", sections: [] }],
      forms: [],
    });

    expect(Object.hasOwn(project, "responsiveLayout")).toBe(false);
  });
});
