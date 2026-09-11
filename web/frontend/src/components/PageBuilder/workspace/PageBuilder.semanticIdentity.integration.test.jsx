import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { builderInitialProjectLoadPromises } from "../core/PageBuilder.config";
import { getBuilderRecoveryStorageKey } from "../core/PageBuilder.recovery";
import PageBuilder from "./PageBuilder";

const apiMocks = vi.hoisted(() => ({
  fetchBuilderProject: vi.fn(),
  fetchWebsiteSettings: vi.fn(),
  publishBuilderProject: vi.fn(),
  updateBuilderProject: vi.fn(),
  updateWebsiteSettings: vi.fn(),
}));

vi.mock("../services/PageBuilder.api", async (importOriginal) => ({
  ...(await importOriginal()),
  ...apiMocks,
}));

const projectId = "project-semantic-identity";
const user = { id: "user-1", tenant_id: "tenant-1" };
const actualCrashSchema = globalThis.process?.env?.MADAR_ACTUAL_BUILDER_SCHEMA
  ? JSON.parse(globalThis.process.env.MADAR_ACTUAL_BUILDER_SCHEMA)
  : null;

const schemaA = {
  id: "schema-project",
  name: "Semantic identity site",
  slug: "semantic-identity-site",
  directLayoutVersion: 4,
  defaultPageId: "page-home",
  pages: [{
    id: "page-home",
    name: "Home",
    slug: "/",
    isDefault: true,
    showInNavigation: true,
    navigationLabel: "Home",
    sections: [{
      id: "section-main",
      name: "Main",
      mode: "direct",
      isPageCanvas: true,
      rows: [],
      freeElements: [{
        id: "block-button",
        type: "button",
        name: "Action button",
        content: "Start",
        styles: { color: "var(--theme-text-inverse)", backgroundColor: "var(--theme-primary)" },
        action: { type: "none", value: "" },
      }],
      layout: { width: "full", minHeight: 720 },
    }],
  }],
  forms: [{
    id: "form-contact",
    name: "Contact",
    sections: [{ id: "form-section", title: "Details", fields: [] }],
  }],
  collections: [],
  workflows: [],
  roles: [],
  users: [],
  theme: { colors: { primary: "#111111", surface: "#ffffff" }, radius: "12px" },
  siteChrome: {
    header: { layout: "default", cta: { label: "Contact", pageId: "page-home" } },
    footer: { layout: "default", copyright: "Madar" },
  },
  publish: { subdomain: "semantic-test" },
};

const reverseObjectKeys = (value) => {
  if (Array.isArray(value)) return value.map(reverseObjectKeys);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value)
      .reverse()
      .map(([key, nestedValue]) => [key, reverseObjectKeys(nestedValue)])
  );
};

const flushMicrotasks = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
};

describe("mounted PageBuilder semantic acknowledgement", () => {
  beforeEach(() => {
    localStorage.clear();
    builderInitialProjectLoadPromises.clear();
    vi.clearAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    apiMocks.fetchWebsiteSettings.mockResolvedValue({ subdomain: "semantic-test" });
    apiMocks.updateWebsiteSettings.mockResolvedValue({ subdomain: "semantic-test" });
    apiMocks.fetchBuilderProject.mockResolvedValue({
      id: projectId,
      name: "Semantic identity site",
      slug: "semantic-identity-site",
      status: "draft",
      draft_revision: 100,
      draft_schema: schemaA,
      published_revision: 0,
      published_version: 0,
      published_schema: schemaA,
      updated_at: "2026-07-15T10:00:00.000Z",
    });
    apiMocks.updateBuilderProject.mockImplementation(async (_id, payload) => ({
      id: projectId,
      name: payload.name,
      slug: payload.slug,
      status: "draft",
      draft_revision: 101,
      draft_schema: reverseObjectKeys(payload.draft_schema),
      published_revision: 0,
      published_version: 0,
      published_schema: schemaA,
      updated_at: "2026-07-15T10:01:00.000Z",
    }));
    apiMocks.publishBuilderProject.mockImplementation(async (_id, expectedRevision) => ({
      project: {
        id: projectId,
        draft_revision: expectedRevision,
        draft_schema: reverseObjectKeys(apiMocks.updateBuilderProject.mock.calls[0][1].draft_schema),
        published_revision: 1,
        published_version: 1,
        published_schema: reverseObjectKeys(apiMocks.updateBuilderProject.mock.calls[0][1].draft_schema),
        status: "published",
      },
      site: { subdomain: "semantic-test" },
    }));
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
    builderInitialProjectLoadPromises.clear();
  });

  it("sends an explicit sidebar Save click to the backend even when the draft is already acknowledged", async () => {
    render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );

    expect((await screen.findByLabelText("Page name")).value).toBe("Home");
    await waitFor(() => expect(screen.getAllByText(/^Saved$/).length).toBeGreaterThan(0));
    expect(apiMocks.updateBuilderProject).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /^Save$/i }));

    await waitFor(() => expect(apiMocks.updateBuilderProject).toHaveBeenCalledTimes(1));
    expect(apiMocks.updateBuilderProject).toHaveBeenCalledWith(
      projectId,
      expect.objectContaining({
        expected_revision: 100,
        draft_schema: expect.objectContaining({ id: schemaA.id }),
      }),
      user.id
    );
  });

  it("renders public responsive navigation inside builder Preview", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/page-builder/projects/" + projectId + "/pages"]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );

    await screen.findByLabelText("Page name");
    fireEvent.click(screen.getByRole("button", { name: /preview site/i }));
    fireEvent.click(screen.getByRole("button", { name: "mobile" }));

    expect(screen.getByLabelText("Open navigation menu")).toBeTruthy();
    expect(container.querySelector(".builder-canvas.viewport-mobile")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /exit site preview/i }));

    expect(container.querySelector(".builder-canvas.viewport-desktop")).toBeTruthy();
    expect(container.querySelector(".builder-canvas.viewport-mobile")).toBeNull();
  });
  it("hydrates Header & Footer controls directly from Website Settings", async () => {
    apiMocks.fetchWebsiteSettings.mockResolvedValue({
      subdomain: "madar-demo",
      brand: "Madar Demo",
      footer_store_name: "Madar demo",
      logo_url: "/uploads/tenant_1/builder_assets/56fee3e0f73c4110abdf423d501fb835.png",
      contact_email: "demo@madar.com",
      phone: "+970123456",
      description: "Synced website description",
    });

    render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/header-footer`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Brand name").value).toBe("Madar Demo");
    });
    expect(screen.getByLabelText("Footer brand name").value).toBe("Madar demo");
    expect(screen.getByLabelText("Contact email").value).toBe("demo@madar.com");
    expect(screen.getByLabelText("Phone").value).toBe("+970123456");
    await waitFor(() =>
      expect(screen.getByLabelText("Logo").value)
        .toBe("56fee3e0f73c4110abdf423d501fb835.png")
    );
    expect(screen.getByLabelText("Footer description").value)
      .toBe("Synced website description");
  });

  it("accepts a recursively reordered jsonb acknowledgement and publishes without another draft save", async () => {
    render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );

    expect((await screen.findByLabelText("Page name")).value).toBe("Home");
    await waitFor(() => expect(screen.getAllByText(/^Saved$/).length).toBeGreaterThan(0));
    expect(apiMocks.updateBuilderProject).not.toHaveBeenCalled();

    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText("Navigation label"), {
      target: { value: "Welcome" },
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });
    await flushMicrotasks();

    expect(apiMocks.updateBuilderProject).toHaveBeenCalledTimes(1);
    expect(apiMocks.updateBuilderProject.mock.calls[0][1].expected_revision).toBe(100);
    expect(screen.getAllByText(/^Saved(?: at .*)?$/).length).toBeGreaterThan(0);
    expect(localStorage.getItem(getBuilderRecoveryStorageKey({
      userId: user.id,
      tenantId: user.tenant_id,
      projectId,
    }))).toBeNull();
    expect(screen.queryByText(/browser recovery/i)).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });
    await flushMicrotasks();
    expect(apiMocks.updateBuilderProject).toHaveBeenCalledTimes(1);
    expect(screen.getAllByText(/^Saved(?: at .*)?$/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Go Live" }));
    await flushMicrotasks();

    expect(apiMocks.updateBuilderProject).toHaveBeenCalledTimes(1);
    expect(apiMocks.publishBuilderProject).toHaveBeenCalledTimes(1);
    expect(apiMocks.publishBuilderProject).toHaveBeenCalledWith(projectId, 101);
    expect(screen.getByTestId("builder-publication-state").textContent).toMatch(/Published/);
    expect(screen.queryByText(/Save failed/i)).toBeNull();
  });

  it("uses the themed website modal before publishing a draft with fewer pages", async () => {
    const publishedSchemaWithExtraPage = {
      ...schemaA,
      pages: [
        ...schemaA.pages,
        {
          ...schemaA.pages[0],
          id: "page-old",
          name: "Old live page",
          slug: "/old-live-page",
          isDefault: false,
        },
      ],
    };
    apiMocks.fetchBuilderProject.mockResolvedValueOnce({
      id: projectId,
      name: "Semantic identity site",
      slug: "semantic-identity-site",
      status: "published",
      draft_revision: 100,
      draft_schema: schemaA,
      published_revision: 2,
      published_version: 2,
      published_schema: publishedSchemaWithExtraPage,
      updated_at: "2026-07-15T10:00:00.000Z",
    });
    apiMocks.publishBuilderProject.mockResolvedValueOnce({
      project: {
        id: projectId,
        status: "published",
        draft_revision: 100,
        draft_schema: schemaA,
        published_revision: 3,
        published_version: 3,
        published_schema: schemaA,
      },
      site: { subdomain: "semantic-test" },
    });

    render(
      <MemoryRouter initialEntries={["/page-builder/projects/" + projectId + "/pages"]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );

    await screen.findByLabelText("Page name");
    fireEvent.click(screen.getByRole("button", { name: "Go Live" }));

    expect(await screen.findByRole("heading", { name: "Publish fewer pages?" })).toBeTruthy();
    expect(screen.getByText(/Publishing will remove/i)).toBeTruthy();
    expect(apiMocks.publishBuilderProject).not.toHaveBeenCalled();
    expect(window.confirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Publish smaller site" }));

    await waitFor(() =>
      expect(apiMocks.publishBuilderProject).toHaveBeenCalledWith(projectId, 100)
    );
  });
  it("reloads a saved project after duplicating text and horizontal-line elements", async () => {
    const reloadSchema = {
      ...schemaA,
      pages: [{
        ...schemaA.pages[0],
        sections: [{
          ...schemaA.pages[0].sections[0],
          freeElements: [
            {
              id: "block-heading",
              type: "text",
              name: "Intro text",
              content: "Build. Engage. Understand.\n\nNormal supporting text.",
              textBlockFormats: ["h1", "text", "text"],
              styles: { color: "#202735", fontSize: "17px" },
            },
            {
              id: "block-line",
              type: "thinDivider",
              name: "Horizontal Line",
              content: "",
              styles: {
                color: "#080808",
                backgroundColor: "var(--theme-border-strong)",
                "--divider-thickness": "2px",
              },
            },
          ],
        }],
      }],
    };
    apiMocks.fetchBuilderProject.mockResolvedValueOnce({
      id: projectId,
      name: reloadSchema.name,
      slug: reloadSchema.slug,
      status: "draft",
      draft_revision: 100,
      draft_schema: reloadSchema,
      published_revision: 0,
      published_version: 0,
      published_schema: reloadSchema,
      updated_at: "2026-07-15T10:00:00.000Z",
    });
    apiMocks.updateBuilderProject.mockImplementationOnce(async (_id, payload) => ({
      id: projectId,
      name: payload.name,
      slug: payload.slug,
      status: "draft",
      draft_revision: 101,
      draft_schema: payload.draft_schema,
      published_revision: 0,
      published_version: 0,
      published_schema: reloadSchema,
      updated_at: "2026-07-15T10:01:00.000Z",
    }));

    const firstMount = render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages/sections`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );
    await screen.findByLabelText("Page name");

    fireEvent.pointerDown(firstMount.container.querySelector('[data-builder-element-id="block-line"]'));
    fireEvent.click(await screen.findByRole("button", { name: "Duplicate" }));
    await waitFor(() => {
      expect(firstMount.container.querySelectorAll(".direct-element-frame-thinDivider")).toHaveLength(2);
    });

    fireEvent.pointerDown(firstMount.container.querySelector('[data-builder-element-id="block-heading"]'));
    fireEvent.click(await screen.findByRole("button", { name: "Duplicate" }));
    await waitFor(() => {
      expect(firstMount.container.querySelectorAll(".direct-element-frame-text")).toHaveLength(2);
    });

    const copiedTextFrame = firstMount.container.querySelectorAll(".direct-element-frame-text")[1];
    const copiedTextEditor = copiedTextFrame.querySelector('[contenteditable="true"]');
    const copiedTextBlocks = copiedTextEditor.querySelectorAll("[data-builder-text-block]");
    copiedTextBlocks[copiedTextBlocks.length - 1].textContent = "Normal supporting text with new data.";
    fireEvent.input(copiedTextEditor);
    fireEvent.blur(copiedTextEditor);
    await waitFor(() => {
      expect(copiedTextFrame.textContent).toContain("new data");
      expect(copiedTextFrame.querySelector('[contenteditable="true"]')).not.toBe(copiedTextEditor);
    });

    fireEvent.click(screen.getByRole("button", { name: /^Save$/i }));
    await waitFor(() => expect(apiMocks.updateBuilderProject).toHaveBeenCalledTimes(1));
    const savedSchema = apiMocks.updateBuilderProject.mock.calls[0][1].draft_schema;
    expect(savedSchema.pages[0].sections[0].freeElements.some(
      (element) => element.type === "text" && element.content.includes("new data")
    )).toBe(true);

    firstMount.unmount();
    builderInitialProjectLoadPromises.clear();
    apiMocks.fetchBuilderProject.mockResolvedValueOnce({
      id: projectId,
      name: savedSchema.name,
      slug: savedSchema.slug,
      status: "draft",
      draft_revision: 101,
      draft_schema: savedSchema,
      published_revision: 0,
      published_version: 0,
      published_schema: savedSchema,
      updated_at: "2026-07-15T10:01:00.000Z",
    });

    const secondMount = render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages/sections`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );
    await screen.findByLabelText("Page name");
    await waitFor(() => {
      expect(secondMount.container.querySelectorAll(".direct-element-frame-thinDivider")).toHaveLength(2);
      expect(secondMount.container.querySelectorAll(".direct-element-frame-text")).toHaveLength(2);
    });
    expect(screen.queryByText("We could not open this page")).toBeNull();
  });

  it.each(["first click", "select all"])("formats every selected line as H1 after %s", async (selectionMethod) => {
    const schema = {
      ...schemaA,
      pages: [{ ...schemaA.pages[0], sections: [{ ...schemaA.pages[0].sections[0],
        freeElements: [{ id: "mixed-heading", type: "heading", name: "Mixed heading",
          content: "Empowering Change\nmakers", textBlockFormats: ["h1", "text"],
          styles: { fontSize: "46px" } }],
      }] }],
    };
    apiMocks.fetchBuilderProject.mockResolvedValueOnce({
      id: projectId, name: schema.name, slug: schema.slug, status: "draft",
      draft_revision: 100, draft_schema: schema, published_revision: 0,
      published_version: 0, published_schema: schema,
    });
    const mounted = render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages/sections`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );
    await screen.findByLabelText("Page name");
    const frame = mounted.container.querySelector('[data-builder-element-id="mixed-heading"]');
    let editor = frame.querySelector('[contenteditable="true"]');
    const selection = window.getSelection();
    selection.removeAllRanges();
    if (selectionMethod === "first click") {
      const focus = vi.spyOn(editor, "focus");
      fireEvent.pointerDown(editor);
      fireEvent.click(editor);
      expect(focus).toHaveBeenCalledWith({ preventScroll: true });
      expect(selection.toString()).toBe("Empowering Changemakers");
      expect(editor.classList.contains("is-selected")).toBe(true);
    } else {
      fireEvent.pointerDown(editor);
      fireEvent.click(editor);
      editor = frame.querySelector('[contenteditable="true"]');
      const range = document.createRange();
      range.selectNodeContents(editor);
      selection.removeAllRanges();
      selection.addRange(range);
      fireEvent.keyUp(editor, { key: "a", ctrlKey: true });
    }
    const boundary = mounted.container.querySelector('[data-selection-for="mixed-heading"]');
    expect(boundary.parentElement).toBe(frame.parentElement);
    expect(boundary.previousElementSibling).toBe(frame);
    expect(boundary.querySelector('[aria-label="Resize Mixed heading"]')).not.toBeNull();
    expect(screen.getAllByRole("button", { name: "Move Mixed heading" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Move component" })).toBeNull();
    const parent = frame.parentElement;
    Object.defineProperties(parent, {
      clientWidth: { configurable: true, value: 1200 },
      clientHeight: { configurable: true, value: 720 },
      offsetWidth: { configurable: true, value: 1200 },
      offsetHeight: { configurable: true, value: 720 },
    });
    parent.getBoundingClientRect = () => ({ left: 0, top: 0, right: 1200, bottom: 720, width: 1200, height: 720 });
    Object.defineProperties(frame, {
      offsetWidth: { configurable: true, get: () => Number.parseFloat(frame.style.width) },
      offsetHeight: { configurable: true, get: () => Number.parseFloat(frame.style.height) },
    });
    const initialBox = { transform: frame.style.transform, width: frame.style.width, height: frame.style.height };
    const resize = boundary.querySelector('[aria-label="Resize Mixed heading"]');
    fireEvent.pointerDown(resize, { pointerId: 4, clientX: 500, clientY: 200 });
    expect({ transform: frame.style.transform, width: frame.style.width, height: frame.style.height }).toEqual(initialBox);
    fireEvent.pointerUp(resize, { pointerId: 4, clientX: 500, clientY: 200 });
    expect({ transform: frame.style.transform, width: frame.style.width, height: frame.style.height }).toEqual(initialBox);
    expect(screen.getByRole("button", { name: "Undo last builder change" }).disabled).toBe(true);
    const style = await screen.findByLabelText("Text style");
    expect(style.value).toBe("mixed");
    fireEvent.pointerDown(style);
    fireEvent.blur(editor);
    fireEvent.change(style, { target: { value: "h1" } });
    fireEvent.pointerUp(style);
    await waitFor(() => {
      expect([...frame.querySelectorAll("[data-builder-text-block]")]
        .map((block) => block.dataset.builderTextBlock)).toEqual(["h1", "h1"]);
    });
    // Subsequent clicks allow caret placement instead of reselecting the body.
    const updatedEditor = frame.querySelector('[contenteditable="true"]');
    const caret = document.createRange();
    caret.setStart(updatedEditor.firstChild.firstChild, 3);
    caret.collapse(true);
    selection.removeAllRanges();
    selection.addRange(caret);
    fireEvent.pointerDown(updatedEditor);
    fireEvent.click(updatedEditor);
    expect(selection.isCollapsed).toBe(true);
  });

  it("applies bullets only to the selected text line", async () => {
    const lineSchema = {
      ...schemaA,
      pages: [{
        ...schemaA.pages[0],
        sections: [{
          ...schemaA.pages[0].sections[0],
          freeElements: [{
            id: "block-lines",
            type: "text",
            name: "Mixed lines",
            content: "First line\nOnly this line\nLast line",
            textBlockFormats: ["text", "text", "text"],
            styles: { color: "#202735", fontSize: "17px" },
          }],
        }],
      }],
    };
    apiMocks.fetchBuilderProject.mockResolvedValueOnce({
      id: projectId,
      name: lineSchema.name,
      slug: lineSchema.slug,
      status: "draft",
      draft_revision: 100,
      draft_schema: lineSchema,
      published_revision: 0,
      published_version: 0,
      published_schema: lineSchema,
      updated_at: "2026-07-15T10:00:00.000Z",
    });

    const mounted = render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages/sections`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );
    await screen.findByLabelText("Page name");
    const frame = mounted.container.querySelector('[data-builder-element-id="block-lines"]');
    fireEvent.pointerDown(frame);
    const editor = frame.querySelector('[contenteditable="true"]');
    const selectedBlock = editor.querySelectorAll("[data-builder-text-block]")[1];
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(selectedBlock);
    selection.removeAllRanges();
    selection.addRange(range);
    fireEvent.mouseUp(editor);

    fireEvent.click(await screen.findByRole("button", { name: "Bullets" }));
    await waitFor(() => {
      const formats = [...frame.querySelectorAll("[data-builder-text-block]")]
        .map((block) => block.dataset.builderTextBlock);
      expect(formats).toEqual(["text", "bullets", "text"]);
    });
  });

  it("keeps the highlighted heading range while changing its font size", async () => {
    const headingSchema = {
      ...schemaA,
      pages: [{
        ...schemaA.pages[0],
        sections: [{
          ...schemaA.pages[0].sections[0],
          freeElements: [{
            id: "block-heading-size",
            type: "heading",
            name: "Heading",
            content: "Natalie\nAbu Allies",
            textBlockFormats: ["h1", "h1"],
            styles: { color: "#202735", fontSize: "54px" },
          }],
        }],
      }],
    };
    apiMocks.fetchBuilderProject.mockResolvedValueOnce({
      id: projectId,
      name: headingSchema.name,
      slug: headingSchema.slug,
      status: "draft",
      draft_revision: 100,
      draft_schema: headingSchema,
      published_revision: 0,
      published_version: 0,
      published_schema: headingSchema,
      updated_at: "2026-07-15T10:00:00.000Z",
    });

    const mounted = render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages/sections`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );
    await screen.findByLabelText("Page name");
    const frame = mounted.container.querySelector('[data-builder-element-id="block-heading-size"]');
    fireEvent.pointerDown(frame);
    const editor = frame.querySelector('[contenteditable="true"]');
    const firstLine = editor.querySelector('[data-builder-text-block="h1"]');
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(firstLine);
    selection.removeAllRanges();
    selection.addRange(range);
    fireEvent.mouseUp(editor);

    const sizeInput = (await screen.findByTitle("Text size")).querySelector('input[type="number"]');
    fireEvent.pointerDown(sizeInput);
    fireEvent.focus(sizeInput);
    fireEvent.change(sizeInput, { target: { value: "72" } });
    fireEvent.pointerUp(sizeInput);

    await waitFor(() => {
      const sizedText = frame.querySelector('[data-builder-text-block="h1"] span');
      expect(sizedText.style.fontSize).toContain("72px");
      expect(frame.querySelectorAll('[data-builder-text-block="h1"]')[1].querySelector("span"))
        .toBeNull();
    });
  });

  it("undoes and redoes a component edit without changing its page structure", async () => {
    const mounted = render(
      <MemoryRouter initialEntries={["/page-builder/projects/" + projectId + "/pages/sections"]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );
    await screen.findByLabelText("Page name");

    const frame = mounted.container.querySelector('[data-builder-element-id="block-button"]');
    fireEvent.click(frame.querySelector(".builder-element-button"));

    const nameInput = await screen.findByLabelText("Name");
    fireEvent.change(nameInput, { target: { value: "Updated action button" } });
    expect(nameInput.value).toBe("Updated action button");

    const undoButton = screen.getByRole("button", { name: "Undo last builder change" });
    await waitFor(() => expect(undoButton.disabled).toBe(false));
    fireEvent.keyDown(document, { key: "z", ctrlKey: true });

    await waitFor(() => expect(screen.getByLabelText("Name").value).toBe("Action button"));
    expect(mounted.container.querySelector(".site-section.direct-layout-section")).toBeTruthy();

    const redoButton = screen.getByRole("button", { name: "Redo builder change" });
    await waitFor(() => expect(redoButton.disabled).toBe(false));
    fireEvent.click(redoButton);

    await waitFor(() =>
      expect(screen.getByLabelText("Name").value).toBe("Updated action button")
    );
    expect(mounted.container.querySelector(".site-section.direct-layout-section")).toBeTruthy();
  });
  it("converts an auto-layout text component to draggable direct layout from the move toolbar", async () => {
    const autoLayoutSchema = {
      ...schemaA,
      pages: [{
        ...schemaA.pages[0],
        sections: [{
          id: "section-auto",
          name: "Generated hero",
          mode: "auto",
          rows: [{
            id: "row-auto",
            layout: { columns: "1", align: "center", gap: "medium" },
            columns: [{
              id: "column-auto",
              name: "Generated copy",
              layout: { align: "left" },
              elements: [{
                id: "generated-auto-text",
                type: "text",
                mode: "auto",
                name: "Generated eyebrow",
                content: "Palestinian ideas. Lasting change.",
                styles: { color: "#005571", fontSize: "17px" },
              }],
            }],
          }],
          freeElements: [],
          layout: { width: "large", minHeight: 320 },
        }],
      }],
    };
    apiMocks.fetchBuilderProject.mockResolvedValueOnce({
      id: projectId,
      name: autoLayoutSchema.name,
      slug: autoLayoutSchema.slug,
      status: "draft",
      draft_revision: 100,
      draft_schema: autoLayoutSchema,
      published_revision: 0,
      published_version: 0,
      published_schema: autoLayoutSchema,
      updated_at: "2026-07-15T10:00:00.000Z",
    });

    const mounted = render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages/sections`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );
    await screen.findByLabelText("Page name");

    const editor = mounted.container.querySelector(".builder-element-text");
    fireEvent.click(editor);
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editor);
    selection.removeAllRanges();
    selection.addRange(range);
    fireEvent.mouseUp(editor);

    const moveHandle = await screen.findByRole("button", { name: "Move component" });
    const sectionNode = editor.closest(".site-section");
    const artboard = editor.closest(".site-renderer-artboard");
    const logicalWidth = Number(artboard.parentElement.dataset.logicalWidth);
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(logicalWidth);
    artboard.getBoundingClientRect = () => ({ width: logicalWidth / 2 });
    sectionNode.getBoundingClientRect = () => ({ left: 100, top: 200, height: 320 });
    editor.getBoundingClientRect = () => ({ left: 150, top: 230, width: 220, height: 30 });
    fireEvent.pointerDown(moveHandle, { pointerId: 9, clientX: 220, clientY: 180 });

    await waitFor(() => {
      const convertedFrame = mounted.container.querySelector('[data-builder-element-id="generated-auto-text"]');
      expect(convertedFrame).not.toBeNull();
      expect(Number(convertedFrame.dataset.logicalX)).toBe(100);
      expect(Number(convertedFrame.dataset.logicalY)).toBe(60);
      expect(Number(convertedFrame.dataset.logicalWidth)).toBe(440);
      expect(mounted.container.querySelector(".site-section.direct-layout-section"))
        .not.toBeNull();
    });
  });
  it.skipIf(!actualCrashSchema)("edits copied mixed-format text from the current saved schema", async () => {
    apiMocks.fetchBuilderProject.mockResolvedValueOnce({
      id: projectId,
      name: actualCrashSchema?.name || "Builder project",
      slug: actualCrashSchema?.slug || "builder-project",
      status: "draft",
      draft_revision: 47,
      draft_schema: actualCrashSchema,
      published_revision: 0,
      published_version: 0,
      published_schema: actualCrashSchema,
      updated_at: "2026-07-26T14:34:42.945724+00:00",
    });

    const mounted = render(
      <MemoryRouter initialEntries={[`/page-builder/projects/${projectId}/pages/sections`]}>
        <PageBuilder user={user} />
      </MemoryRouter>
    );
    await screen.findByLabelText("Page name");

    const copiedTextFrames = Array.from(
      mounted.container.querySelectorAll(".direct-element-frame-text")
    ).filter((frame) => frame.querySelector(".builder-element-text")?.textContent?.length > 300);
    expect(copiedTextFrames.length).toBeGreaterThan(0);

    for (const frame of copiedTextFrames) {
      fireEvent.pointerDown(frame);
      const editor = frame.querySelector('[contenteditable="true"]');
      const lastBlock = editor.querySelector("[data-builder-text-block]:last-child");
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(lastBlock);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
      fireEvent.keyDown(editor, { key: "Enter", code: "Enter" });
      const insertedBlock = editor.querySelector("[data-builder-text-block]:last-child");
      insertedBlock.textContent = "New copied data";
      fireEvent.input(editor);
      fireEvent.blur(editor);
      await waitFor(() => expect(frame.textContent).toContain("New copied data"));
    }
  });
});
