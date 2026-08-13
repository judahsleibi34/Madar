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
const actualCrashSchema = process.env.MADAR_ACTUAL_BUILDER_SCHEMA
  ? JSON.parse(process.env.MADAR_ACTUAL_BUILDER_SCHEMA)
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
