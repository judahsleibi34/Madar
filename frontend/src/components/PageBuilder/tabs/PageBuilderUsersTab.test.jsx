// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PageBuilderUsersTab from "./PageBuilderUsersTab";

const permissionGroups = [
  { title: "Site", permissions: [{ key: "view", label: "View site" }] },
];

const renderUsersTab = (overrides = {}) => {
  const props = {
    project: {
      activePageId: "home",
      roles: [
        {
          id: "customer",
          name: "Customer",
          description: "Published site customer",
          permissions: { view: true },
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
    ...overrides,
  };

  render(<PageBuilderUsersTab {...props} />);
  return props;
};

describe("PageBuilderUsersTab", () => {
  it("shows registered subdomain users and their source", () => {
    renderUsersTab();
    expect(screen.getByText("Registered Person")).toBeTruthy();
    expect(screen.getByText("registered@example.com")).toBeTruthy();
    expect(screen.getByText("Registered on site")).toBeTruthy();
    expect(screen.getByText("Customer")).toBeTruthy();
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
    fireEvent.change(screen.getByLabelText("Temporary password"), {
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
