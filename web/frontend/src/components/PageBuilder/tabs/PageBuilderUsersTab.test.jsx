// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PageBuilderUsersTab from "./PageBuilderUsersTab";

const permissionGroups = [
  { title: "Site", permissions: [{ key: "view", label: "View site" }] },
];

const renderUsersTab = (overrides = {}) => {
  const props = {
    project: {
      activePageId: "home",
      pages: [{
        id: "home",
        name: "Home",
        sections: [{ freeElements: [{ id: "booking", type: "reservationBlock", name: "Consultation booking" }] }],
      }],
      forms: [{ id: "intake", name: "Intake form" }],
      roles: [
        {
          id: "customer",
          name: "Customer",
          description: "Published site customer",
          permissions: { view: true },
          resourceAccess: { pageIds: [], formIds: [], reservationBlockIds: [] },
        },
      ],
    },
    users: [
      {
        id: "21",
        name: "Registered Person",
        email: "registered@example.com",
        roleId: "customer",
        status: "Active",
        source: "registered",
      },
    ],
    usersLoading: false,
    usersError: "",
    userMutationId: "",
    selected: { type: "page", id: "home" },
    selectedRole: null,
    permissionGroups,
    addUser: vi.fn().mockResolvedValue({ id: "22" }),
    addRole: vi.fn(),
    updateUser: vi.fn(),
    updateRole: vi.fn(),
    deleteUser: vi.fn(),
    reloadUsers: vi.fn(),
    setSelected: vi.fn(),
    isSavingProject: false,
    onSave: vi.fn(),
    saveDisabled: false,
    saveState: "dirty",
    ...overrides,
  };

  render(<PageBuilderUsersTab {...props} />);
  return props;
};

afterEach(cleanup);

describe("PageBuilderUsersTab", () => {
  it("allows an immediate manual save without an inline notification card", () => {
    const props = renderUsersTab();
    expect(screen.queryByRole("status")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save now" }));
    expect(props.onSave).toHaveBeenCalledTimes(1);
  });

  it("shows registered subdomain users and their source", () => {
    renderUsersTab();
    expect(screen.getByText("Registered Person")).toBeTruthy();
    expect(screen.getByText("registered@example.com")).toBeTruthy();
    expect(screen.getByText("Registered on site")).toBeTruthy();
    const usersPanel = screen.getByRole("heading", { name: "Subdomain users" }).closest("section");
    expect(within(usersPanel).getByText("Customer")).toBeTruthy();
  });

  it("minimizes and restores the role editor", () => {
    renderUsersTab();

    fireEvent.click(screen.getByRole("button", { name: "Minimize role editor" }));
    expect(screen.queryByLabelText("Intake form")).toBeNull();
    expect(screen.getByRole("button", { name: "Expand role editor" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Expand role editor" }));
    expect(screen.getByLabelText("Intake form")).toBeTruthy();
  });
  it("updates resource allowlists for the selected role", () => {
    const props = renderUsersTab();
    fireEvent.click(screen.getByLabelText("Intake form"));
    expect(props.updateRole).toHaveBeenCalledWith("customer", {
      resourceAccess: {
        pageIds: [],
        formIds: ["intake"],
        reservationBlockIds: [],
      },
    });
    expect(screen.getByLabelText("Home")).toBeTruthy();
    expect(screen.getByLabelText("Consultation booking")).toBeTruthy();
  });
  it("creates an admin user through the server-backed callback", async () => {
    const props = renderUsersTab();
    fireEvent.click(screen.getByRole("button", { name: "Add user" }));

    fireEvent.change(screen.getByLabelText("Full name"), {
      target: { value: "Admin Created" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "created@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^Temporary password/), {
      target: { value: "safe-password-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create user" }));

    await waitFor(() => expect(props.addUser).toHaveBeenCalledWith({
      full_name: "Admin Created",
      email: "created@example.com",
      password: "safe-password-123",
      role_id: "customer",
      status: "active",
    }));
  });
});
