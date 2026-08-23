import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TenantSiteRuntime, { getBuilderPreviewBasePath } from "./TenantSiteRuntime";
import {
  fetchBuilderProject,
  fetchProtectedSitePage,
  fetchPublicSite,
  fetchPublicSiteBootstrap,
  getTenantVisitorStatus,
  loginTenantVisitor,
} from "../services/PageBuilder.api";

vi.mock("../services/PageBuilder.api", async () => ({
  ...(await vi.importActual("../services/PageBuilder.api")),
  fetchBuilderProject: vi.fn(),
  fetchProtectedSitePage: vi.fn(),
  fetchPublicSite: vi.fn(),
  fetchPublicSiteBootstrap: vi.fn(),
  getTenantVisitorStatus: vi.fn(),
  loginTenantVisitor: vi.fn(),
}));

const PROJECT_ID = "3023144a-6f48-46ee-90ed-fe712f51283a";

const renderPreview = ({
  showHeader = true,
  showFooter = true,
  teamSections = [],
} = {}) => {
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
          sections: teamSections,
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

const renderPublic = ({
  showHeader = true,
  showFooter = true,
  footerShopLinks = "",
  footerHelpLinks = "",
  headerButtonLabel = "",
  headerBackgroundColor = "",
  contactEmail = "",
  phone = "",
  teamSections = [],
} = {}) => {
  getTenantVisitorStatus.mockResolvedValue({ logged_in: false, user: null });
  fetchPublicSiteBootstrap.mockResolvedValue({
    site: { subdomain: "tenant-site", brand: "Route Test", logo_url: "" },
  });
  fetchPublicSite.mockResolvedValue({
    site: { subdomain: "tenant-site", site_id: "site-1", project_id: "project-1" },
    project: {
      site_id: "site-1",
      site_identifier: "tenant-site",
      project_id: "project-1",
      published_version: 1,
      publication_key: "site-1:tenant-site:project-1:1:hash",
      published_schema: {
        defaultPageId: "home",
        siteChrome: {
          showHeader,
          showFooter,
          brand: "Route Test",
          footerShopLinks,
          footerHelpLinks,
          headerButtonLabel,
          headerBackgroundColor,
          contactEmail,
          phone,
        },
        theme: {},
        forms: [],
        pages: [
          { id: "home", name: "Home", slug: "/", sections: [] },
          { id: "team", name: "Team", slug: "/about/team", sections: teamSections },
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

  it("marks background artwork so responsive content sizing leaves it authored", async () => {
    const position = {
      desktop: { x: 24, y: 24, width: 320, height: 180 },
      tablet: { x: 20, y: 20, width: 280, height: 160 },
      mobile: { x: 12, y: 16, width: 260, height: 140 },
    };
    renderPreview({
      teamSections: [{
        id: "responsive-section",
        mode: "direct",
        layout: { minHeight: 420 },
        freeElements: [
          {
            id: "background-artwork",
            type: "image",
            layer: "behindText",
            content: "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==",
            styles: {},
            position,
          },
          {
            id: "foreground-copy",
            type: "text",
            content: "Responsive copy",
            styles: {},
            position,
          },
        ],
      }],
    });

    await waitFor(() => {
      expect(document.querySelector('[data-page-id="team"]')).toBeTruthy();
    });

    expect(document.querySelector(".direct-element-frame-image.is-behind-text")).toBeTruthy();
    expect(document.querySelector(".direct-element-frame-text.is-behind-text")).toBeNull();
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

      expect(Boolean(document.querySelector(".built-site-header"))).toBe(expectsHeader);
      expect(Boolean(document.querySelector(".built-site-footer"))).toBe(expectsFooter);
    }
  );

  it("applies the saved header color in the public runtime", async () => {
    renderPublic({ headerBackgroundColor: "#123456" });
    await waitFor(() => {
      expect(document.querySelector('[data-page-id="team"]')).toBeTruthy();
    });

    expect(document.querySelector(".built-site-header")?.style.backgroundColor).toBe("rgb(18, 52, 86)");
  });

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

      expect(Boolean(document.querySelector(".built-site-header"))).toBe(expectsHeader);
      expect(Boolean(document.querySelector(".built-site-footer"))).toBe(expectsFooter);
    }
  );

  it("hides unresolved internal page ids from the footer", async () => {
    renderPublic({
      footerShopLinks: "page_restricted-12345678",
      footerHelpLinks: "About Us",
    });

    await waitFor(() => {
      expect(document.querySelector('[data-page-id="team"]')).toBeTruthy();
    });

    expect(screen.queryByText("page_restricted-12345678")).toBeNull();
    expect(screen.getByText("About Us")).toBeTruthy();
  });

  it("keeps intentionally blank header and contact settings blank", async () => {
    renderPublic();

    await waitFor(() => {
      expect(document.querySelector('[data-page-id="team"]')).toBeTruthy();
    });

    expect(document.querySelector(".built-site-cta")).toBeNull();
    expect(document.querySelector(".built-site-mobile-menu-cta")).toBeNull();
    expect(document.querySelectorAll(".ecommerce-contact-row")).toHaveLength(0);
    expect(screen.queryByText("info@madar.com")).toBeNull();
    expect(screen.queryByText("+972599203857")).toBeNull();
  });

  it("renders validated button colors on the standard public path", async () => {
    renderPublic({
      teamSections: [{
        id: "buttons",
        layout: { width: "large", paddingY: "medium", background: "transparent" },
        rows: [{ id: "row", layout: { columns: 1, align: "stretch", gap: "medium" }, columns: [{ id: "column", layout: { align: "stretch" }, elements: [{
          id: "button-1",
          type: "button",
          content: "Contact us",
          styles: {},
          backgroundColor: "#112233",
          textColor: "#FFFFFF",
          hoverBackgroundColor: "#334455",
          hoverTextColor: "#EEEEEE",
          borderColor: "#556677",
        }] }] }],
        freeElements: [],
      }],
    });
    const button = await screen.findByRole("button", { name: "Contact us" });
    expect(button.className).toContain("has-button-background-color");
    expect(button.className).toContain("has-button-hover-text-color");
    expect(button.style.getPropertyValue("--button-border-color")).toBe("#556677");
  });
});

const protectedLoginPage = {
  id: "home",
  name: "Home",
  slug: "/",
  isDefault: true,
  sections: [{
    id: "login-section",
    mode: "free",
    layout: {
      width: "large",
      paddingY: "small",
      background: "transparent",
      minHeight: 320,
    },
    rows: [],
    freeElements: [{
      id: "login-block",
      type: "loginBlock",
      auth: {},
      styles: {},
    }],
  }],
};

const protectedMembersPage = {
  id: "members",
  name: "Members",
  slug: "/members",
  sections: [],
};

const RuntimeLocation = () => {
  const current = useLocation();
  return (
    <output data-testid="runtime-location">
      {current.pathname}{current.search}
    </output>
  );
};

const renderProtectedPublic = () => {
  getTenantVisitorStatus.mockResolvedValue({ logged_in: false, user: null });
  fetchPublicSite.mockResolvedValue({
      site: { subdomain: "tenant-site", site_id: "site-1", project_id: "project-1" },
      project: {
        site_id: "site-1",
        site_identifier: "tenant-site",
        project_id: "project-1",
        published_version: 1,
        publication_key: "site-1:tenant-site:project-1:1:hash",
      published_schema: {
        defaultPageId: "home",
        siteChrome: { brand: "Protected Route Test" },
        theme: {},
        forms: [],
        pages: [protectedLoginPage],
      },
    },
  });

  return render(
    <MemoryRouter initialEntries={["/site/tenant-site/members"]}>
      <Routes>
        <Route
          path="/site/:subdomain/*"
          element={(
            <>
              <TenantSiteRuntime />
              <RuntimeLocation />
            </>
          )}
        />
      </Routes>
    </MemoryRouter>
  );
};

describe("TenantSiteRuntime protected page login redirect", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("redirects an anonymous protected-page request to login with a safe return path", async () => {
    fetchProtectedSitePage.mockRejectedValue(
      Object.assign(new Error("Log in to access this resource"), { status: 401 })
    );

    renderProtectedPublic();

    await waitFor(() => {
      expect(screen.getByTestId("runtime-location").textContent).toBe(
        "/site/tenant-site/?returnTo=%2Fmembers"
      );
    });
    expect(fetchProtectedSitePage).toHaveBeenCalledWith("tenant-site", "members");
    expect(document.querySelector('input[name="email"]')).toBeTruthy();
  });

  it("returns to the protected page after a successful login", async () => {
    fetchProtectedSitePage
      .mockRejectedValueOnce(
        Object.assign(new Error("Log in to access this resource"), { status: 401 })
      )
      .mockResolvedValueOnce({
        site: { subdomain: "tenant-site", site_id: "site-1", project_id: "project-1" },
        project: {
          site_id: "site-1",
          site_identifier: "tenant-site",
          project_id: "project-1",
          published_version: 1,
          publication_key: "site-1:tenant-site:project-1:1:hash",
          published_schema: {
            defaultPageId: "home",
            siteChrome: { brand: "Protected Route Test" },
            theme: {},
            forms: [],
            pages: [protectedLoginPage, protectedMembersPage],
          },
        },
      });
    loginTenantVisitor.mockResolvedValue({
      logged_in: true,
      user: { id: 7, email: "member@example.com" },
      message: "Logged in",
    });

    renderProtectedPublic();

    await waitFor(() => {
      expect(document.querySelector('input[name="email"]')).toBeTruthy();
    });
    fireEvent.change(document.querySelector('input[name="email"]'), {
      target: { value: "member@example.com" },
    });
    fireEvent.change(document.querySelector('input[name="password"]'), {
      target: { value: "password123" },
    });
    fireEvent.submit(document.querySelector('input[name="email"]').closest("form"));

    await waitFor(() => {
      expect(document.querySelector('[data-page-id="members"]')).toBeTruthy();
    });
    expect(screen.getByTestId("runtime-location").textContent).toBe(
      "/site/tenant-site/members"
    );
    expect(fetchProtectedSitePage).toHaveBeenCalledTimes(2);
  });
});
