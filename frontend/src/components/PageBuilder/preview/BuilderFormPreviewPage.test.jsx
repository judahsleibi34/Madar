import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getBuilderStorageKey } from "../core/PageBuilder.constants";
import { createBlankWorkspaceProject } from "../core/PageBuilder.starters";
import BuilderFormPreviewPage from "./BuilderFormPreviewPage";

describe("BuilderFormPreviewPage page position", () => {
  beforeEach(() => {
    localStorage.clear();
    window.scrollTo = vi.fn();
  });

  it("stays on the current page when the same form is synchronized", async () => {
    const storageKey = getBuilderStorageKey();
    const project = createBlankWorkspaceProject();
    const form = {
      ...project.forms[0],
      id: "form_regression",
      title: "Regression form",
      sections: [
        { id: "page_1", title: "First page", description: "", fields: [] },
        { id: "page_2", title: "Second page", description: "", fields: [] },
      ],
    };
    const savedProject = { ...project, forms: [form], activeFormId: form.id };
    localStorage.setItem(storageKey, JSON.stringify(savedProject));

    render(
      <MemoryRouter initialEntries={[`/page-builder/form-preview/${form.id}`]}>
        <Routes>
          <Route
            path="/page-builder/form-preview/:formId"
            element={<BuilderFormPreviewPage />}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getAllByText("Page 1 of 2")).toHaveLength(2));
    await Promise.resolve();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getAllByText("Page 2 of 2")).toHaveLength(2);

    const synchronizedProject = {
      ...savedProject,
      forms: [{ ...form, description: "Autosaved while previewing" }],
    };
    const serializedProject = JSON.stringify(synchronizedProject);
    localStorage.setItem(storageKey, serializedProject);
    window.dispatchEvent(new StorageEvent("storage", {
      key: storageKey,
      newValue: serializedProject,
    }));

    await waitFor(() => expect(screen.getAllByText("Page 2 of 2")).toHaveLength(2));
    expect(screen.getByText("Second page")).toBeTruthy();
  });
});
