import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ScrollToTop from "./ScrollToTop";

function Navigation() {
  const navigate = useNavigate();
  return <>
    <button onClick={() => navigate("/settings")}>Settings</button>
    <button onClick={() => navigate("/ecommerce/products")}>Products</button>
    <button onClick={() => navigate(-1)}>Back</button>
    <main className="authenticated-main" data-testid="content" />
    <aside className="admin-sidebar" data-testid="sidebar" />
    <div className="live-store" data-testid="store" />
  </>;
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("ScrollToTop", () => {
  it("resets the real page scrollers on navigation while preserving sidebar position", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    render(<MemoryRouter initialEntries={["/ecommerce/products"]}><ScrollToTop /><Navigation /></MemoryRouter>);
    screen.getByTestId("content").scrollTop = 300;
    screen.getByTestId("store").scrollTop = 200;
    screen.getByTestId("sidebar").scrollTop = 100;
    fireEvent.click(screen.getByText("Settings"));
    expect(screen.getByTestId("content").scrollTop).toBe(0);
    expect(screen.getByTestId("store").scrollTop).toBe(0);
    expect(screen.getByTestId("sidebar").scrollTop).toBe(100);
  });

  it("resets when the user selects the same page again", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    render(<MemoryRouter initialEntries={["/ecommerce/products"]}><ScrollToTop /><Navigation /></MemoryRouter>);
    fireEvent.click(screen.getByText("Products"));
    screen.getByTestId("content").scrollTop = 300;
    fireEvent.click(screen.getByText("Products"));
    expect(screen.getByTestId("content").scrollTop).toBe(0);
  });

  it("keeps existing browser back behavior", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    render(<MemoryRouter initialEntries={["/ecommerce/products"]}><ScrollToTop /><Navigation /></MemoryRouter>);
    fireEvent.click(screen.getByText("Settings"));
    screen.getByTestId("content").scrollTop = 300;
    fireEvent.click(screen.getByText("Back"));
    expect(screen.getByTestId("content").scrollTop).toBe(300);
  });
});
