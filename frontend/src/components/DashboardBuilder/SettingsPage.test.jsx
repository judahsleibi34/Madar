import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildProfilePayload } from "./profilePayload";
import SettingsPage from "./SettingsPage";
import { apiFetch } from "../../utils/apiClient";
import { getBuilderStorageKey } from "../PageBuilder/core/PageBuilder.constants";
import {
  fetchBuilderProject,
  listBuilderProjects,
  updateBuilderProject,
} from "../PageBuilder/services/PageBuilder.api";

vi.mock("../../utils/apiClient", () => ({ apiFetch: vi.fn() }));
vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  fetchBuilderProject: vi.fn(),
  listBuilderProjects: vi.fn(),
  updateBuilderProject: vi.fn(),
  uploadBuilderAsset: vi.fn(),
}));

const response = (data) => ({
  ok: true,
  status: 200,
  text: async () => JSON.stringify(data),
});

beforeEach(() => {
  vi.clearAllMocks();
  listBuilderProjects.mockResolvedValue({ projects: [], pagination: {} });
  localStorage.clear();
});

describe("SettingsPage canonical email handling", () => {
  it("never includes the displayed canonical email in normal profile updates", () => {
    expect(
      buildProfilePayload({
        first_name: "  Madar ",
        last_name: " Owner  ",
        email: "different@example.com",
        phone: "  +970000000  ",
        avatar: "  /avatar_uploads/test.webp  ",
      })
    ).toEqual({
      first_name: "Madar",
      last_name: "Owner",
      phone: "+970000000",
      avatar: "/avatar_uploads/test.webp",
    });
  });

  it("loads account info once in Strict Mode and keeps saved names", async () => {
    const initialUser = {
      id: 3,
      first_name: "Old",
      last_name: "Name",
      email: "owner@example.com",
      phone: "",
      avatar: "",
    };
    const updatedUser = { ...initialUser, first_name: "New", last_name: "Owner" };
    apiFetch.mockImplementation((_url, options = {}) => {
      if (options.method === "PUT") return Promise.resolve(response({ user: updatedUser }));
      if (String(_url).includes("/website/settings")) {
        return Promise.resolve(response({ website: {} }));
      }
      return Promise.resolve(response({ user: initialUser }));
    });

    render(
      <StrictMode>
        <MemoryRouter>
          <SettingsPage user={initialUser} onUserUpdated={vi.fn()} />
        </MemoryRouter>
      </StrictMode>
    );

    await waitFor(() => {
      expect(apiFetch.mock.calls.filter(([url]) => String(url).endsWith("/info"))).toHaveLength(1);
    });
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: "New" } });
    fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: "Owner" } });
    fireEvent.click(screen.getByRole("button", { name: /save profile/i }));

    await waitFor(() => expect(screen.getByLabelText(/first name/i).value).toBe("New"));
    expect(screen.getByLabelText(/last name/i).value).toBe("Owner");
    expect(apiFetch.mock.calls.filter(([, options]) => options?.method === "PUT")).toHaveLength(1);
    expect(apiFetch.mock.calls.filter(([url]) => String(url).endsWith("/info"))).toHaveLength(1);
  });

  it("does not merge another account's cached website details into backend settings", async () => {
    const currentUser = {
      id: 22,
      tenant_id: 9,
      first_name: "Judah",
      last_name: "Sleibi",
      email: "judah@example.com",
    };
    localStorage.setItem(
      "madar_app_builder_frontend_v4",
      JSON.stringify({
        siteChrome: {
          brand: "Other tenant brand",
          contactEmail: "other@example.com",
        },
      })
    );
    localStorage.setItem(
      getBuilderStorageKey(currentUser.id),
      JSON.stringify({
        ...JSON.parse(localStorage.getItem("madar_app_builder_frontend_v4")),
        publish: { subdomain: "other-tenant" },
      })
    );
    apiFetch.mockImplementation((url) => {
      if (String(url).includes("/website/settings")) {
        return Promise.resolve(response({
          website: {
            tenant_id: 9,
            subdomain: "jus",
            brand: "",
            contact_email: "",
          },
        }));
      }
      return Promise.resolve(response({ user: currentUser }));
    });

    render(
      <MemoryRouter>
        <SettingsPage user={currentUser} onUserUpdated={vi.fn()} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("tab", { name: /website/i }));

    await waitFor(() => expect(screen.getByLabelText(/subdomain name/i).value).toBe("jus"));
    expect(screen.getByLabelText(/brand name/i).value).toBe("");
    expect(screen.getByLabelText(/contact email/i).value).toBe("");
    expect(screen.queryByDisplayValue("Other tenant brand")).toBeNull();
    expect(screen.queryByDisplayValue("other@example.com")).toBeNull();
  });

  it("shows only the logo filename while retaining the backend path", async () => {
    const currentUser = { id: 23, tenant_id: 7, email: "owner@example.com" };
    const logoFileName = "56fee3e0f73c4110abdf423c12345678.png";
    const logoPath = `/uploads/tenant_7/builder_assets/${logoFileName}`;
    listBuilderProjects.mockResolvedValue({
      projects: [{ id: "builder-project-1" }],
      pagination: { count: 1, has_more: false },
    });
    fetchBuilderProject.mockResolvedValue({
      id: "builder-project-1",
      draft_revision: 4,
      draft_schema: { siteChrome: { brand: "Old brand" } },
    });
    updateBuilderProject.mockResolvedValue({ id: "builder-project-1", draft_revision: 5 });
    apiFetch.mockImplementation((url, options = {}) => {
      if (String(url).includes("/website/settings") && options.method === "PUT") {
        return Promise.resolve(response({
          website: { subdomain: "demo", brand: "Demo", logo_url: logoPath },
        }));
      }
      if (String(url).includes("/website/settings")) {
        return Promise.resolve(response({ website: { logo_url: logoPath } }));
      }
      return Promise.resolve(response({ user: currentUser }));
    });

    render(
      <MemoryRouter initialEntries={["/settings?tab=website"]}>
        <SettingsPage user={currentUser} onUserUpdated={vi.fn()} />
      </MemoryRouter>
    );

    const logoField = await screen.findByLabelText(/logo file/i);
    expect(logoField.value).toBe(logoFileName);
    expect(logoField.value).not.toContain("/uploads/");

    fireEvent.change(screen.getByLabelText(/subdomain name/i), {
      target: { value: "demo" },
    });
    fireEvent.change(screen.getByLabelText(/brand name/i), {
      target: { value: "Demo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save website details/i }));
    await waitFor(() => {
      const saveCall = apiFetch.mock.calls.find(([, options]) => options?.method === "PUT");
      expect(JSON.parse(saveCall[1].body).logo_url).toBe(logoPath);
    });
    expect(updateBuilderProject).toHaveBeenCalledWith(
      "builder-project-1",
      expect.objectContaining({
        expected_revision: 4,
        draft_schema: expect.objectContaining({
          siteChrome: expect.objectContaining({
            brand: "Demo",
            logoUrl: logoPath,
          }),
        }),
      })
    );
  });
});

afterEach(() => {
  cleanup();
});

