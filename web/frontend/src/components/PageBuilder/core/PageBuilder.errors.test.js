import { describe, expect, it } from "vitest";

import {
  collectProjectIdIssues,
  collectFormConnectionIssues,
  getFormConnectionFocusTarget,
  getFormConnectionIssueMessage,
  getBuilderConflictMessage,
  isBuilderRevisionError,
} from "./PageBuilder.errors";

describe("publish id validation", () => {
  it("detects duplicate block ids across pages with safe occurrence context", () => {
    const project = {
      pages: [
        { id: "home", name: "Home", sections: [{ freeElements: [{ id: "duplicate", type: "text" }] }] },
        { id: "page-2", name: "Page 2", sections: [{ rows: [{ columns: [{ elements: [{ id: "duplicate", type: "formBlock" }] }] }] }] },
      ],
      forms: [],
    };
    const before = structuredClone(project);

    expect(collectProjectIdIssues(project)).toEqual([{
      issue_type: "duplicate_block_id",
      duplicate_id: "duplicate",
      occurrences: [
        expect.objectContaining({ page_id: "home", page_name: "Home", block_type: "text" }),
        expect.objectContaining({ page_id: "page-2", page_name: "Page 2", block_type: "formBlock" }),
      ],
    }]);
    expect(project).toEqual(before);
  });

  it("detects duplicate page and form ids in their project-wide scopes", () => {
    const issues = collectProjectIdIssues({
      pages: [{ id: "page", name: "One" }, { id: "page", name: "Two" }],
      forms: [{ id: "form", title: "One" }, { id: "form", title: "Two" }],
    });

    expect(issues.map((issue) => issue.issue_type)).toEqual([
      "duplicate_page_id",
      "duplicate_form_id",
    ]);
  });

  it("leaves a valid project free of id issues across repeated preflight checks", () => {
    const project = {
      pages: [{ id: "home", sections: [{ freeElements: [{ id: "block", type: "text" }] }] }],
      forms: [{ id: "form" }],
    };
    expect(collectProjectIdIssues(project)).toEqual([]);
    expect(collectProjectIdIssues(project)).toEqual([]);
  });
});

describe("builder revision recovery", () => {
  it("recognizes stale and missing revision responses without discarding edits", () => {
    expect(isBuilderRevisionError({ code: "project_revision_conflict" })).toBe(true);
    expect(isBuilderRevisionError({ code: "project_revision_required" })).toBe(true);
    expect(
      getBuilderConflictMessage({
        code: "project_revision_conflict",
        context: { current_revision: 9 },
      })
    ).toContain("revision 9");
    expect(
      getBuilderConflictMessage({ code: "project_revision_conflict" })
    ).toContain("local edits are still here");
  });
});

describe("publish form connection validation", () => {
  it("passes a valid canonical connection without mutating or duplicating blocks", () => {
    const project = {
      forms: [{ id: "form-1" }],
      pages: [{ id: "home", name: "Home", sections: [{
        freeElements: [{ id: "block-1", type: "formBlock", connectedFormId: "form-1" }],
      }] }],
    };
    const before = JSON.stringify(project);

    expect(collectFormConnectionIssues(project)).toEqual([]);
    expect(collectFormConnectionIssues(project)).toEqual([]);
    expect(JSON.stringify(project)).toBe(before);
    expect(project.pages[0].sections[0].freeElements).toHaveLength(1);
  });

  it("identifies every orphaned form block with actionable page context", () => {
    const issues = collectFormConnectionIssues({
      forms: [{ id: "valid-form" }],
      pages: [{
        id: "page-1",
        name: "Contact",
        sections: [{
          rows: [{ columns: [{ elements: [
            { id: "valid-block", type: "formBlock", connectedFormId: "valid-form" },
            { id: "orphan", type: "formBlock", connectedFormId: "deleted-form", name: "Contact form" },
          ] }] }],
        }],
      }],
    });

    expect(issues).toEqual([expect.objectContaining({
      issue_type: "orphaned_form_block",
      page_id: "page-1",
      page_name: "Contact",
      block_id: "orphan",
      form_id: "deleted-form",
    })]);
    expect(getFormConnectionIssueMessage(issues[0])).toContain("Contact");
    expect(getFormConnectionIssueMessage(issues[0])).toContain("connect this block");
    expect(getFormConnectionFocusTarget(issues[0])).toEqual({
      pageId: "page-1",
      selection: { type: "element", id: "orphan" },
    });
  });

  it("keeps valid references independent across multiple pages", () => {
    const project = {
      forms: [{ id: "form-1" }, { id: "form-2" }],
      pages: [
        { id: "home", sections: [{ elements: [{ id: "b1", type: "formBlock", connectedFormId: "form-1" }] }] },
        { id: "contact", sections: [{ elements: [{ id: "b2", type: "formBlock", connectedFormId: "form-2" }] }] },
      ],
    };
    expect(collectFormConnectionIssues(project)).toEqual([]);
  });
});
