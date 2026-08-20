import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../components/common/RouteSuspense", () => ({
  default: ({ children }) => children,
}));
vi.mock("./shared", () => ({
  DashboardLoadingElement: () => null,
  DashboardShell: ({ children }) => <div>{children}</div>,
  RestrictedAccessWindow: () => null,
}));
vi.mock("../components/DashboardBuilder/SecurityMfaPage", () => ({
  default: () => <div>Dedicated security page</div>,
}));
vi.mock("../components/DashboardBuilder/SettingsPage", () => ({
  default: ({ initialTab }) => (
    <div>{initialTab === "security" ? "Tabbed security settings" : "General settings page"}</div>
  ),
}));
vi.mock("../components/DashboardBuilder/EcommerceStorePage", () => ({
  default: () => <h1>Live Store</h1>,
}));
vi.mock("../components/DashboardBuilder/ReservationCalendarPage", async () => {
  const React = await import("react");
  function CalendarMock({ user, initialView, onViewChange }) {
    const [mountedTenant] = React.useState(user?.tenant_id || "missing");
    return (
      <div>
        Calendar mounted for {mountedTenant} in {initialView || "calendar"} view
        <button type="button" onClick={() => onViewChange?.("agenda")}>Open agenda</button>
      </div>
    );
  }
  return {
    default: CalendarMock,
  };
});
vi.mock("../components/PageBuilder", () => ({
  default: () => <div>Explicit project editor</div>,
}));
vi.mock("../components/PageBuilder/workspace/BuilderProjectChooser", () => ({
  default: () => <div>Project chooser</div>,
}));

import UserWorkspaceRoutes from "./UserWorkspaceRoutes";

afterEach(cleanup);

const routeProps = {
  lang: "en",
  onGoToDashboard: vi.fn(),
  onUserUpdated: vi.fn(),
  shellProps: {},
  themeMode: "light",
  user: { id: 3 },
};

describe("workspace settings routes", () => {
  it.each([
    ["/ecommerce/tags", "Tags"],
    ["/ecommerce/categories", "Categories"],
    ["/ecommerce/products", "Products"],
    ["/ecommerce/cv-rerank", "CV Rerank"],
  ])("renders the Ecommerce page for %s", async (pathname, heading) => {
    render(
      <MemoryRouter initialEntries={[pathname]}>
        <UserWorkspaceRoutes {...routeProps} />
      </MemoryRouter>
    );

    expect(await screen.findByRole(
      "heading",
      { name: heading, level: 1 },
      { timeout: 5000 }
    )).toBeTruthy();
  });

  it("renders the authenticated live Store page", async () => {
    render(
      <MemoryRouter initialEntries={["/ecommerce/store"]}>
        <UserWorkspaceRoutes {...routeProps} />
      </MemoryRouter>
    );
    expect(await screen.findByRole("heading", { name: "Live Store", level: 1 })).toBeTruthy();
  });

  it("opens the Security tab on direct navigation/refresh", async () => {
    render(
      <MemoryRouter initialEntries={["/settings/security"]}>
        <UserWorkspaceRoutes {...routeProps} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Tabbed security settings")).toBeTruthy();
    expect(screen.queryByText("Dedicated security page")).toBeNull();
  });

  it("does not mount the editor at a legacy project-less builder URL", async () => {
    render(
      <MemoryRouter initialEntries={["/page-builder/pages"]}>
        <UserWorkspaceRoutes {...routeProps} />
      </MemoryRouter>
    );
    expect(await screen.findByText("Project chooser")).toBeTruthy();
    expect(screen.queryByText("Explicit project editor")).toBeNull();
  });

  it("mounts the editor only when the backend project id is explicit", async () => {
    render(
      <MemoryRouter initialEntries={["/page-builder/projects/project-7/pages"]}>
        <UserWorkspaceRoutes {...routeProps} />
      </MemoryRouter>
    );
    expect(await screen.findByText("Explicit project editor")).toBeTruthy();
    expect(screen.queryByText("Project chooser")).toBeNull();
  });

  it("remounts the calendar before rendering after the authenticated tenant changes", async () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={["/calendar"]}>
        <UserWorkspaceRoutes
          {...routeProps}
          user={{ id: 3, tenant_id: "tenant-a" }}
        />
      </MemoryRouter>
    );
    expect(await screen.findByText("Calendar mounted for tenant-a in calendar view")).toBeTruthy();

    rerender(
      <MemoryRouter initialEntries={["/calendar"]}>
        <UserWorkspaceRoutes
          {...routeProps}
          user={{ id: 3, tenant_id: "tenant-b" }}
        />
      </MemoryRouter>
    );

    expect(await screen.findByText("Calendar mounted for tenant-b in calendar view")).toBeTruthy();
    expect(screen.queryByText("Calendar mounted for tenant-a in calendar view")).toBeNull();
  });

  it("opens Agenda directly on its own refresh-safe route", async () => {
    render(
      <MemoryRouter initialEntries={["/agenda"]}>
        <UserWorkspaceRoutes {...routeProps} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Calendar mounted for missing in agenda view")).toBeTruthy();
  });

  it("navigates from calendar to the refresh-safe agenda route", async () => {
    render(
      <MemoryRouter initialEntries={["/calendar"]}>
        <UserWorkspaceRoutes {...routeProps} />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "Open agenda" }));
    expect(await screen.findByText("Calendar mounted for missing in agenda view")).toBeTruthy();
  });
});
