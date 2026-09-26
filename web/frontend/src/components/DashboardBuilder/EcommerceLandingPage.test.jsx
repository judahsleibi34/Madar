import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EcommerceLandingPage from "./EcommerceLandingPage";
import {
  fetchEcommerceLandingPage,
  saveEcommerceLandingPage,
  uploadEcommerceProductImage,
} from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceLandingPage: vi.fn(),
  saveEcommerceLandingPage: vi.fn(),
  uploadEcommerceProductImage: vi.fn(),
}));

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  fetchEcommerceLandingPage.mockResolvedValue({ landing_page: { autoplay_enabled: true, interval_ms: 5000, slides: [] } });
  uploadEcommerceProductImage.mockResolvedValue("/uploads/tenant_7/builder_assets/0123456789abcdef0123456789abcdef.webp");
  saveEcommerceLandingPage.mockImplementation(async (value) => ({ landing_page: value }));
});

describe("EcommerceLandingPage", () => {
  it("starts with three editable demo slides and publishes an added slide with the autoplay interval", async () => {
    render(<EcommerceLandingPage user={{ tenant_id: 7 }} />);
    expect(await screen.findByRole("heading", { name: "Landing page" })).toBeTruthy();
    expect(screen.getAllByRole("tab")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Add slide" }));

    const imageInput = document.querySelector('.ecommerce-landing-image-field input[type="file"]');
    fireEvent.change(imageInput, { target: { files: [new File(["hero"], "hero.webp", { type: "image/webp" })] } });
    await waitFor(() => expect(uploadEcommerceProductImage).toHaveBeenCalled());
    fireEvent.change(screen.getAllByLabelText("Headline")[0], { target: { value: "Weekend sale" } });
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Publish landing page" }));

    await waitFor(() => expect(saveEcommerceLandingPage).toHaveBeenCalledWith(
      expect.objectContaining({
        interval_ms: 8000,
        slides: expect.arrayContaining([expect.objectContaining({ title_en: "Weekend sale" })]),
      }),
      expect.any(Object),
    ));
    expect(saveEcommerceLandingPage.mock.calls[0][0].slides).toHaveLength(4);
  });
});
