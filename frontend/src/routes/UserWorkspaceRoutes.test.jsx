import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

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
  default: () => <div>General settings page</div>,
}));

import UserWorkspaceRoutes from "./UserWorkspaceRoutes";

const routeProps = {
  lang: "en",
  onGoToDashboard: vi.fn(),
  onUserUpdated: vi.fn(),
  shellProps: {},
  themeMode: "light",
  user: { id: 3 },
};

describe("workspace settings routes", () => {
  it("keeps the dedicated security route on direct navigation/refresh", async () => {
    render(
      <MemoryRouter initialEntries={["/settings/security"]}>
        <UserWorkspaceRoutes {...routeProps} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Dedicated security page")).toBeTruthy();
    expect(screen.queryByText("General settings page")).toBeNull();
  });
});
