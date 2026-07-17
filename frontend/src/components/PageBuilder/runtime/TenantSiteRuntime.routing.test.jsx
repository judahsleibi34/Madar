import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TenantSiteRuntime, { getBuilderPreviewBasePath } from "./TenantSiteRuntime";
import {
  fetchBuilderProject,
  fetchPublicSite,
  getTenantVisitorStatus,
} from "../services/PageBuilder.api";

vi.mock("../services/PageBuilder.api", async () => ({
  ...(await vi.importActual("../services/PageBuilder.api")),
  fetchBuilderProject: vi.fn(),
  fetchPublicSite: vi.fn(),
  getTenantVisitorStatus: vi.fn(),
}));

const PROJECT_ID = "3023144a-6f48-46ee-90ed-fe712f51283a";

const renderPreview = ({ showHeader = true, showFooter = true } = {}) => {
  fetchBuilderProject.mockResolvedValue({
    id: PROJECT_ID,
    draft_schema: {
      defaultPageId: "home",
      siteChrome: { showHeader, showFooter, brand: "Route Test" },
      theme: {},
      forms: [],
      pages: [
        { id: "home", name: "Home", slug: "/", sections: [] },
        {
          id: "team",
          name: "Team",
          slug: "/about/team",
          sections: [],
        },
      ],
    },
  });

  return render(
    <MemoryRouter
      initialEntries={[
        `/page-builder/projects/${PROJECT_ID}/preview/about/team`,
      ]}
    >
      <Routes>
        <Route
          path="/page-builder/projects/:projectId/preview/*"
          element={<TenantSiteRuntime draftPreview />}
        />
      </Routes>
    </MemoryRouter>
  );
};

const renderPublic = ({ showHeader = true, showFooter = true } = {}) => {
  getTenantVisitorStatus.mockResolvedValue({ logged_in: false, user: null });
  fetchPublicSite.mockResolvedValue({
    site: { subdomain: "tenant-site" },
    project: {
      published_schema: {
        defaultPageId: "home",
        siteChrome: { showHeader, showFooter, brand: "Route Test" },
        theme: {},
        forms: [],
        pages: [
          { id: "home", name: "Home", slug: "/", sections: [] },
          { id: "team", name: "Team", slug: "/about/team", sections: [] },
        ],
      },
    },
  });

  return render(
    <MemoryRouter initialEntries={["/site/tenant-site/about/team"]}>
      <Routes>
        <Route path="/site/:subdomain/*" element={<TenantSiteRuntime />} />
      </Routes>
    </MemoryRouter>
  );
};

describe("TenantSiteRuntime explicit project preview", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("derives the nested preview base from the routed project id", async () => {
    renderPreview();

    await waitFor(() => {
      expect(document.querySelector('[data-page-id="team"]')).toBeTruthy();
    });
    expect(fetchBuilderProject).toHaveBeenCalledTimes(1);
    expect(fetchBuilderProject).toHaveBeenCalledWith(PROJECT_ID);
    expect(getBuilderPreviewBasePath(PROJECT_ID)).toBe(
      `/page-builder/projects/${PROJECT_ID}/preview`
    );
    expect(screen.getByText("Draft preview")).toBeTruthy();
  });

  it.each([
    [true, true, true, true],
    [false, true, false, true],
    [true, false, true, false],
    [false, false, false, false],
  ])(
    "honors header=%s footer=%s in preview",
    async (showHeader, showFooter, expectsHeader, expectsFooter) => {
      renderPreview({ showHeader, showFooter });
      await waitFor(() => {
        expect(document.querySelector('[data-page-id="team"]')).toBeTruthy();
      });

      expect(Boolean(document.querySelector(".tenant-site-header"))).toBe(expectsHeader);
      expect(Boolean(document.querySelector(".tenant-site-footer"))).toBe(expectsFooter);
    }
  );

  it.each([
    [true, true, true, true],
    [false, true, false, true],
    [true, false, true, false],
    [false, false, false, false],
  ])(
    "honors header=%s footer=%s in public runtime",
    async (showHeader, showFooter, expectsHeader, expectsFooter) => {
      renderPublic({ showHeader, showFooter });
      await waitFor(() => {
        expect(document.querySelector('[data-page-id="team"]')).toBeTruthy();
      });

      expect(Boolean(document.querySelector(".tenant-site-header"))).toBe(expectsHeader);
      expect(Boolean(document.querySelector(".tenant-site-footer"))).toBe(expectsFooter);
    }
  );
});
