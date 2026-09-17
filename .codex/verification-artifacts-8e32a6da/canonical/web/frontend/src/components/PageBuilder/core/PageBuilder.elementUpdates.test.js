import { describe, expect, it } from "vitest";

import { elementTypes } from "./PageBuilder.constants";
import { createElement } from "./PageBuilder.factories";
import { updateElementInSectionsPreservingLayout } from "./PageBuilder.elementUpdates";

const structureOf = (sections) =>
  sections.map((section) => ({
    id: section.id,
    mode: section.mode,
    freeElementIds: (section.freeElements || []).map((element) => element.id),
    rows: (section.rows || []).map((row) => ({
      id: row.id,
      columns: (row.columns || []).map((column) => ({
        id: column.id,
        elementIds: (column.elements || []).map((element) => element.id),
      })),
    })),
  }));

describe("updateElementInSectionsPreservingLayout", () => {
  it("edits every registered component type without changing auto-layout structure", () => {
    const elements = elementTypes.map(({ id }, index) =>
      createElement(id, { id: `element-${index}`, name: `Original ${id}` })
    );
    const sections = [{
      id: "section-auto",
      mode: "auto",
      rows: [{
        id: "row-1",
        columns: [{ id: "column-1", elements }],
      }],
      freeElements: [],
    }];
    const originalStructure = structureOf(sections);

    elements.forEach((element) => {
      const updated = updateElementInSectionsPreservingLayout(
        sections,
        element.id,
        { name: "Edited", styles: { color: "#123456" } }
      );

      expect(structureOf(updated)).toEqual(originalStructure);
      expect(updated[0].mode).toBe("auto");
      expect(updated[0].rows[0].columns[0].elements.find(
        (candidate) => candidate.id === element.id
      )).toMatchObject({
        id: element.id,
        name: "Edited",
        styles: expect.objectContaining({ color: "#123456" }),
      });
    });
  });

  it("edits a direct component without moving or resizing it", () => {
    const element = createElement("image", {
      id: "image-1",
      position: {
        desktop: { x: 24, y: 36, width: 420, height: 240 },
      },
    });
    const sections = [{
      id: "section-direct",
      mode: "direct",
      rows: [],
      freeElements: [element],
    }];

    const updated = updateElementInSectionsPreservingLayout(
      sections,
      element.id,
      { name: "Updated image" }
    );

    expect(structureOf(updated)).toEqual(structureOf(sections));
    expect(updated[0].freeElements[0].position).toEqual(element.position);
    expect(updated[0].freeElements[0].name).toBe("Updated image");
  });
});