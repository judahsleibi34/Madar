import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import UserDashboard from "./UserDashboard";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key, options) => options?.defaultValue || _key,
  }),
}));

vi.mock("./WeeklyScreenTimePanel", () => ({
  default: () => <div>Weekly activity</div>,
}));

vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  fetchBuilderSiteMembers: vi.fn().mockResolvedValue([]),
  fetchBuilderStorageUsage: vi.fn().mockResolvedValue({}),
  listBuilderProjects: vi.fn().mockResolvedValue({
    projects: [{ id: "project-1", publish: { subdomain: "olive-house" } }],
  }),
  listBuilderReservations: vi.fn().mockResolvedValue({
    reservations: [],
    pagination: { has_more: false },
  }),
}));

vi.mock("../../services/siteVisitApi", () => ({
  fetchSiteVisitMetrics: vi.fn().mockResolvedValue({
    website_visits: 42,
    store_visits: 17,
  }),
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
});

describe("UserDashboard shortcuts", () => {
  it("opens the website and store on their production URLs", async () => {
    render(
      <MemoryRouter>
        <UserDashboard user={{ id: 3, name: "Madar" }} />
      </MemoryRouter>,
    );

    const websiteLink = await screen.findByRole("link", { name: "View website" });
    expect(websiteLink.getAttribute("href")).toBe(
      "https://madarportal.com/site/olive-house/",
    );
    expect(websiteLink.getAttribute("target")).toBe("_blank");

    const storeLink = screen.getByRole("link", { name: "View store" });
    expect(storeLink.getAttribute("href")).toBe(
      "https://madarportal.com/site/olive-house/shop",
    );
    expect(storeLink.getAttribute("target")).toBe("_blank");
    expect(await screen.findByText("42")).toBeTruthy();
    expect(screen.getByText("17")).toBeTruthy();
    expect(
      Array.from(document.querySelectorAll(".user-dashboard-metric-label"))
        .map((element) => element.textContent),
    ).toEqual([
      "Plan",
      "Website visits",
      "Store visits",
      "Reservation notifications",
      "Users with permissions",
      "Permission types",
      "Used space",
      "Forms used",
      "Reservation forms used",
    ]);
    expect(
      document.querySelector(".user-dashboard-metric-card--plan")
        ?.textContent,
    ).toContain("Workspace plan");
  });

  it("renders safely when an older cache entry lacks visit metrics", () => {
    const scope = "tenant:7:user:3";
    sessionStorage.setItem("madar-dashboard-cache-v1", JSON.stringify({
      [`metrics:${scope}`]: {
        cachedAt: Date.now(),
        value: {
          forms: 1,
          reservationForms: 0,
          newReservations: 0,
          usedBytes: 0,
          quotaBytes: 0,
          permittedUsers: 0,
          permissionTypes: [],
        },
      },
    }));

    render(
      <MemoryRouter>
        <UserDashboard user={{ id: 3, tenant_id: 7, name: "Madar" }} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Website visits")).toBeTruthy();
    expect(screen.getByText("Store visits")).toBeTruthy();
  });

  it("customizes visible cards and remembers hidden cards", async () => {
    render(
      <MemoryRouter>
        <UserDashboard user={{ id: 3, name: "Madar" }} />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Customize dashboard" }));
    const storeCheckbox = screen.getByRole("checkbox", { name: "Store visits" });
    expect(storeCheckbox.checked).toBe(true);
    fireEvent.click(storeCheckbox);

    expect(
      document.querySelector(".user-dashboard-metrics-grid")?.textContent,
    ).not.toContain("Store visits");
    await waitFor(() => {
      expect(
        localStorage.getItem("madar-dashboard-card-visibility-v1:user:3"),
      ).toContain("store-visits");
    });
  });
});
