import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardSidebar from "./DashboardSidebar";

afterEach(cleanup);

const labels = {
  "sidebar.aria": "Dashboard sidebar",
  "sidebar.navigation": "Dashboard navigation",
  "sidebar.brand": "Madar",
  "sidebar.search": "Search",
  "sidebar.home": "Home",
  "sidebar.dashboard": "Dashboard",
  "sidebar.workspace": "Workspace",
  "sidebar.ecommerce": "Ecommerce",
  "sidebar.tags": "Tags",
  "sidebar.categories": "Categories",
  "sidebar.products": "Products",
  "sidebar.store": "Store",
  "sidebar.pageBuilder": "Page Builder",
  "sidebar.submissions": "Submissions",
  "sidebar.dataLogs": "Data Logs",
  "sidebar.calendar": "Calendar",
  "sidebar.archive": "Archive",
  "sidebar.myPlan": "My Plan",
  "sidebar.security": "Security",
  "sidebar.settings": "Settings",
  "sidebar.themeMode": "Theme",
  "sidebar.logout": "Log out",
  "sidebar.userRole": "User",
  "user.fallbackName": "Madar User",
};

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, options) => labels[key] || options?.defaultValue || key,
    i18n: { resolvedLanguage: "en" },
  }),
}));

vi.mock("../LanguageSwitcher", () => ({
  default: ({ onChange }) => (
    <button type="button" onClick={() => onChange("ar")}>
      Language
    </button>
  ),
}));

vi.mock("../ThemeChanger/ThemeToggle", () => ({
  default: ({ label, onChange }) => (
    <button type="button" onClick={() => onChange("dark")}>
      {label}
    </button>
  ),
}));

vi.mock("./NotificationBell", () => ({
  default: () => (
    <div className="admin-sidebar-notifications">
      <button type="button">Notifications</button>
    </div>
  ),
}));

function renderSidebar(pathname = "/dashboard") {
  const props = {
    lang: "en",
    user: { name: "Test User", email: "test@example.com" },
    onLogout: vi.fn(),
    onLanguageChange: vi.fn(),
    onNavigate: vi.fn(),
    onThemeModeChange: vi.fn(),
    showNotifications: true,
    themeMode: "light",
  };

  render(
    <MemoryRouter initialEntries={[pathname]}>
      <DashboardSidebar {...props} />
    </MemoryRouter>,
  );

  return props;
}

describe("DashboardSidebar navigation hierarchy", () => {
  it("renders notifications first and expands only workspace children", () => {
    renderSidebar();

    const navigation = screen.getByRole("navigation", {
      name: "Dashboard navigation",
    });
    const buttons = within(navigation).getAllByRole("button");

    expect(buttons.map((button) => button.textContent)).toEqual([
      "Notifications",
      "Home",
      "Dashboard",
      "Workspace",
      "Ecommerce",
      "My Plan",
    ]);

    const workspace = screen.getByRole("button", { name: "Workspace" });
    expect(workspace.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(workspace);
    expect(workspace.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("button", { name: "Page Builder" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Calendar" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Archive" })).toBeTruthy();
  });

  it("renders Ecommerce below Workspace as an expandable section", () => {
    renderSidebar();

    const workspace = screen.getByRole("button", { name: "Workspace" });
    const ecommerce = screen.getByRole("button", { name: "Ecommerce" });

    expect(
      workspace.compareDocumentPosition(ecommerce) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(ecommerce.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(ecommerce);

    expect(ecommerce.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById("dashboard-sidebar-ecommerce")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Tags" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Categories" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Products" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "Store" })).toBeTruthy();
  });

  it("opens Ecommerce on a child route and highlights the active page", () => {
    renderSidebar("/ecommerce/categories");

    const ecommerce = screen.getByRole("button", { name: "Ecommerce" });
    const categories = screen.getByRole("button", { name: "Categories" });

    expect(ecommerce.getAttribute("aria-expanded")).toBe("true");
    expect(ecommerce.classList.contains("active-parent")).toBe(true);
    expect(categories.getAttribute("aria-current")).toBe("page");
    expect(
      screen.getByRole("button", { name: "Products" }).hasAttribute("aria-current"),
    ).toBe(false);
  });

  it("opens Ecommerce and highlights Store on the live view route", () => {
    renderSidebar("/ecommerce/store");
    expect(screen.getByRole("button", { name: "Ecommerce" }).getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("button", { name: "Store" }).getAttribute("aria-current")).toBe("page");
  });

  it("keeps only one expandable sidebar section open at a time", () => {
    renderSidebar();

    const workspace = screen.getByRole("button", { name: "Workspace" });
    const ecommerce = screen.getByRole("button", { name: "Ecommerce" });
    const settings = screen.getByRole("button", { name: "Settings" });

    fireEvent.click(workspace);
    expect(workspace.getAttribute("aria-expanded")).toBe("true");
    expect(settings.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(ecommerce);
    expect(workspace.getAttribute("aria-expanded")).toBe("false");
    expect(ecommerce.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(workspace);
    expect(workspace.getAttribute("aria-expanded")).toBe("true");
    expect(ecommerce.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(settings);
    expect(workspace.getAttribute("aria-expanded")).toBe("false");
    expect(settings.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(workspace);
    expect(workspace.getAttribute("aria-expanded")).toBe("true");
    expect(settings.getAttribute("aria-expanded")).toBe("false");
  });
  it("opens workspace for its active route and highlights only the child", () => {
    renderSidebar("/builder-data");

    const sidebar = screen.getByLabelText("Dashboard sidebar");
    const workspace = screen.getByRole("button", { name: "Workspace" });
    const activeChild = screen.getByRole("button", { name: "Data Logs" });
    const expandSidebar = screen.getByRole("button", {
      name: "Expand sidebar",
    });

    expect(sidebar.classList.contains("is-workspace-collapsed")).toBe(true);
    expect(workspace.getAttribute("aria-expanded")).toBe("true");
    expect(workspace.classList.contains("active-parent")).toBe(true);
    expect(workspace.hasAttribute("aria-current")).toBe(false);
    expect(activeChild.getAttribute("aria-current")).toBe("page");
    expect(
      screen
        .getByRole("button", { name: "Page Builder" })
        .hasAttribute("aria-current"),
    ).toBe(false);

    fireEvent.click(expandSidebar);
    expect(sidebar.classList.contains("is-workspace-collapsed")).toBe(false);
    expect(
      screen.getByRole("button", { name: "Collapse sidebar" }),
    ).toBeTruthy();
  });

  it("expands the workspace sidebar when a navigation icon is pressed", () => {
    renderSidebar("/page-builder/projects/project-1/pages");

    const sidebar = screen.getByLabelText("Dashboard sidebar");
    expect(sidebar.classList.contains("is-workspace-collapsed")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(sidebar.classList.contains("is-workspace-collapsed")).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(sidebar.classList.contains("is-workspace-collapsed")).toBe(true);

    const settings = screen.getAllByRole("button", { name: "Settings" })[0];
    fireEvent.click(settings);
    expect(sidebar.classList.contains("is-workspace-collapsed")).toBe(false);
    expect(settings.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById("dashboard-sidebar-settings")).toBeTruthy();
  });

  it("collapses the expanded workspace sidebar when clicking outside it", () => {
    renderSidebar("/page-builder/projects/project-1/pages");

    const sidebar = screen.getByLabelText("Dashboard sidebar");
    fireEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(sidebar.classList.contains("is-workspace-collapsed")).toBe(false);

    fireEvent.pointerDown(document.body);
    expect(sidebar.classList.contains("is-workspace-collapsed")).toBe(true);
  });

  it("keeps settings above the account and reuses all utility actions", () => {
    const props = renderSidebar("/settings");
    const settings = screen.getAllByRole("button", { name: "Settings" })[0];

    expect(settings.getAttribute("aria-expanded")).toBe("true");
    expect(settings.classList.contains("active-parent")).toBe(true);
    expect(screen.getByRole("button", { name: "Language" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Theme" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(props.onLogout).toHaveBeenCalledOnce();

    const group = settings.closest(".admin-sidebar-settings-group");
    const account = screen.getByText("test@example.com").closest(
      ".admin-sidebar-user",
    );
    expect(
      group.compareDocumentPosition(account) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
