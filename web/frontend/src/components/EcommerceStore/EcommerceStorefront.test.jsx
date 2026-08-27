import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceStorefront from "./EcommerceStorefront";
import { fetchPublicEcommerceCatalog } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchPublicEcommerceCatalog: vi.fn(),
  fetchPublicEcommerceProduct: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});

const catalog = {
  site: { brand: "Test Store" },
  catalog: {
    categories: [],
    tags: [],
    products: [],
    pagination: { page: 1, pages: 1, total: 0, limit: 12 },
  },
};

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="current query">{location.search}</output>;
}

describe("EcommerceStorefront", () => {
  it("submits the current search draft and refreshes it from URL state", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    render(
      <MemoryRouter initialEntries={["/site/demo/shop?search=original"]}>
        <Routes>
          <Route
            path="/site/:subdomain/shop"
            element={
              <>
                <EcommerceStorefront />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    const search = await screen.findByRole("textbox");
    expect(search.value).toBe("original");
    fireEvent.change(search, { target: { value: "updated" } });
    fireEvent.submit(search.closest("form"));

    await waitFor(() => {
      expect(screen.getByLabelText("current query").textContent).toContain(
        "search=updated"
      );
    });
    expect(screen.getByRole("textbox").value).toBe("updated");
    expect(fetchPublicEcommerceCatalog).toHaveBeenLastCalledWith(
      "demo",
      expect.objectContaining({ search: "updated" })
    );
  });
});

describe("EcommerceStorefront theme synchronization", () => {
  it("applies the published website theme to the store root", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue({
      ...catalog,
      site: {
        brand: "Form & Flow",
        theme: {
          background: "#f3efe7",
          surface: "#fffdf8",
          text: "#21312a",
          muted: "#68736d",
          primary: "#365849",
          accent: "#365849",
          accentDark: "#294438",
          buttonText: "#ffffff",
        },
      },
    });

    const { container } = render(
      <MemoryRouter initialEntries={["/site/demo/shop"]}>
        <Routes>
          <Route path="/site/:subdomain/shop" element={<EcommerceStorefront />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findAllByText("Form & Flow");
    const store = container.querySelector(".live-store");
    expect(store.style.getPropertyValue("--theme-bg")).toBe("#f3efe7");
    expect(store.style.getPropertyValue("--theme-primary")).toBe("#365849");
    expect(store.style.getPropertyValue("--madar-navy")).toBe("#365849");
  });

  it("shows the Pilates dummy catalog when the connected store is empty", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue({
      site: { brand: "Form & Flow" },
      catalog: {
        categories: [],
        tags: [],
        products: [],
        pagination: { page: 1, pages: 1, total: 0, limit: 12 },
      },
    });

    render(
      <MemoryRouter initialEntries={["/site/demo/shop"]}>
        <Routes>
          <Route path="/site/:subdomain/shop" element={<EcommerceStorefront />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("Studio Grip Socks")).toBeTruthy();
    expect(screen.getByText("Movement Journal")).toBeTruthy();
    expect(screen.getByText(/Showing/).textContent).toContain("6");
  });
});
