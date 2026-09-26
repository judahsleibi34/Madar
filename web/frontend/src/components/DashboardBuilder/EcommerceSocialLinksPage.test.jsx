import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EcommerceSocialLinksPage from "./EcommerceSocialLinksPage";
import { fetchEcommerceSocialLinks, saveEcommerceSocialLinks } from "../../services/ecommerceApi";
import { clearEcommerceAdminCache } from "./utils/ecommerceAdminCache";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceSocialLinks: vi.fn(),
  saveEcommerceSocialLinks: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  fetchEcommerceSocialLinks.mockResolvedValue({ social_links: { instagram: "https://instagram.com/madar" } });
  saveEcommerceSocialLinks.mockImplementation(async (socialLinks) => ({ social_links: socialLinks }));
});

afterEach(() => {
  cleanup();
  clearEcommerceAdminCache("authenticated", "social-links");
});

describe("EcommerceSocialLinksPage", () => {
  it("uses a page-shaped social links skeleton while loading", () => {
    fetchEcommerceSocialLinks.mockReturnValue(new Promise(() => {}));
    const { container } = render(<EcommerceSocialLinksPage />);

    expect(screen.getByRole("status", { name: "Loading social links" })).toBeTruthy();
    expect(container.querySelectorAll(".ecommerce-social-skeleton-grid > div")).toHaveLength(4);
  });

  it("loads and saves the complete social profile set", async () => {
    const { container } = render(<EcommerceSocialLinksPage />);

    const instagram = await screen.findByDisplayValue("https://instagram.com/madar");
    expect(instagram).toBeTruthy();
    expect(container.querySelectorAll("[data-network-icon]")).toHaveLength(4);
    const facebook = screen.getByPlaceholderText("https://facebook.com/your-page");
    fireEvent.change(facebook, { target: { value: "https://facebook.com/madar" } });
    fireEvent.click(screen.getByRole("button", { name: "Save social links" }));

    await waitFor(() => expect(saveEcommerceSocialLinks).toHaveBeenCalledWith(expect.objectContaining({
      facebook: "https://facebook.com/madar",
      instagram: "https://instagram.com/madar",
      snapchat: "",
    }), { scope: "authenticated" }));
    expect(await screen.findByText("Social links saved")).toBeTruthy();
  });

  it("rejects insecure links before saving", async () => {
    render(<EcommerceSocialLinksPage />);
    const facebook = await screen.findByPlaceholderText("https://facebook.com/your-page");
    fireEvent.change(facebook, { target: { value: "http://facebook.com/madar" } });
    fireEvent.click(screen.getByRole("button", { name: "Save social links" }));

    expect(await screen.findByText("Check the social links")).toBeTruthy();
    expect(saveEcommerceSocialLinks).not.toHaveBeenCalled();
  });

  it("accepts a Snapchat username and creates the profile URL automatically", async () => {
    fetchEcommerceSocialLinks.mockResolvedValueOnce({ social_links: { snapchat: "https://www.snapchat.com/add/existing.user" } });
    render(<EcommerceSocialLinksPage />);

    const snapchat = await screen.findByDisplayValue("existing.user");
    fireEvent.change(snapchat, { target: { value: "@madar.shop" } });
    fireEvent.click(screen.getByRole("button", { name: "Save social links" }));

    await waitFor(() => expect(saveEcommerceSocialLinks).toHaveBeenCalledWith(expect.objectContaining({
      snapchat: "https://www.snapchat.com/add/madar.shop",
    }), { scope: "authenticated" }));
    expect(screen.getByDisplayValue("madar.shop")).toBeTruthy();
  });
});
