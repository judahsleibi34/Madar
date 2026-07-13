import React, { StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildProfilePayload } from "./profilePayload";
import SettingsPage from "./SettingsPage";
import { apiFetch } from "../../utils/apiClient";

vi.mock("../../utils/apiClient", () => ({ apiFetch: vi.fn() }));
vi.mock("../PageBuilder/services/PageBuilder.api", () => ({ uploadBuilderAsset: vi.fn() }));

const response = (data) => ({
  ok: true,
  status: 200,
  text: async () => JSON.stringify(data),
});

beforeEach(() => {
  vi.clearAllMocks();
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
});
