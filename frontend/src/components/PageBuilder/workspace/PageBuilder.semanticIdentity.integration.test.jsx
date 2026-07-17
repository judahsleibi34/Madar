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
}));

vi.mock("../services/PageBuilder.api", async (importOriginal) => ({
  ...(await importOriginal()),
  ...apiMocks,
}));

const projectId = "project-semantic-identity";
const user = { id: "user-1", tenant_id: "tenant-1" };

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
});
