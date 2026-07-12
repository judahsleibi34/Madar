import { describe, expect, it } from "vitest";
import { createElement, createPage, createSection } from "./PageBuilder.factories";
import { getSectionElements } from "./PageBuilder.layout";
import { cleanBuilderProject } from "./PageBuilder.project";

describe("cleanBuilderProject", () => {
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
    expect(savedForm.responses).toEqual([]);
  });
});
