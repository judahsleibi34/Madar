import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import UserDashboard from "./UserDashboard";
import { clearAllDashboardSnapshotCaches } from "./utils/dashboardSnapshotCache";
import { listBuilderProjects, fetchBuilderStorageUsage, listBuilderReservations } from "../PageBuilder/services/PageBuilder.api";
import { fetchSiteVisitMetrics } from "../../services/siteVisitApi";
import { fetchEcommerceDashboardSummary } from "../../services/ecommerceApi";

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

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceDashboardSummary: vi.fn().mockResolvedValue({
    catalog: {
      products: 12,
      active_products: 10,
      tags: 8,
      categories: 4,
      low_stock: 2,
      out_of_stock: 1,
    },
    sales: {
      revenue: "1234.50",
      currency: "USD",
      orders: 9,
      paid_orders: 6,
      pending_orders: 2,
      average_order_value: "205.75",
    },
    top_products: [
      { product_id: "product-1", name: "Everyday Linen Shirt", units_sold: 7, revenue: "476.00" },
    ],
  }),
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
  clearAllDashboardSnapshotCaches();
  vi.clearAllMocks();
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
      "https://olive-house.madarportal.com/",
    );
    expect(websiteLink.getAttribute("target")).toBe("_blank");

    const storeLink = screen.getByRole("link", { name: "View store" });
    expect(storeLink.getAttribute("href")).toBe(
      "https://olive-house.madarportal.com/shop",
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
      "Products",
      "Categories",
      "Tags",
      "Revenue",
      "Orders",
      "Average order value",
      "Inventory alerts",
      "Top 5 products",
    ]);
    expect(
      document.querySelector(".user-dashboard-metric-card--plan")
        ?.textContent,
    ).toContain("Workspace plan");
    expect(screen.getByText("Top 5 products")).toBeTruthy();
    expect(screen.getByText("Everyday Linen Shirt")).toBeTruthy();
    expect(screen.getByText("7 sold")).toBeTruthy();
    expect(screen.getByText("$1,234.50")).toBeTruthy();
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

it("renders cached dashboard metrics on return without another backend request", async () => {
  const user = { id: 20, tenant_id: 7, name: "Owner" };
  const first = render(<MemoryRouter><UserDashboard user={user} /></MemoryRouter>);
  await screen.findByText("42");
  first.unmount();
  const projectCalls = listBuilderProjects.mock.calls.length;
  const visitCalls = fetchSiteVisitMetrics.mock.calls.length;
  render(<MemoryRouter><UserDashboard user={user} /></MemoryRouter>);
  expect(screen.getByText("42")).toBeTruthy();
  await waitFor(() => expect(document.querySelector(".user-dashboard-skeleton")).toBeNull());
  expect(listBuilderProjects.mock.calls.length).toBe(projectCalls);
  expect(fetchSiteVisitMetrics.mock.calls.length).toBe(visitCalls);
  expect(fetchEcommerceDashboardSummary).toHaveBeenCalledTimes(1);
});

it("starts storage, reservations, and visit reads before the project list finishes", async () => {
  let resolve;
  listBuilderProjects.mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  render(<MemoryRouter><UserDashboard user={{ id: 21, tenant_id: 7 }} /></MemoryRouter>);
  await waitFor(() => expect(fetchBuilderStorageUsage).toHaveBeenCalled());
  expect(listBuilderReservations).toHaveBeenCalled();
  expect(fetchSiteVisitMetrics).toHaveBeenCalled();
  expect(fetchEcommerceDashboardSummary).toHaveBeenCalled();
  resolve({ projects: [] });
  await screen.findByText("42");
});

it("keeps the dashboard usable without exposing a failed commerce response", async () => {
  fetchEcommerceDashboardSummary.mockRejectedValueOnce(new Error("database connection details"));
  render(<MemoryRouter><UserDashboard user={{ id: 22, tenant_id: 7 }} /></MemoryRouter>);
  await screen.findByText("No paid product sales yet.");
  expect(document.body.textContent).not.toContain("database connection details");
  expect(screen.getByText("Top 5 products")).toBeTruthy();
});
