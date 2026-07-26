import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PageBuilderPageInspector from "./PageBuilderPageInspector";

afterEach(cleanup);

describe("PageBuilderPageInspector", () => {
  it("renders the active page and updates persisted page fields", () => {
    const onUpdate = vi.fn();
    const onSetDefault = vi.fn();
    render(
      <PageBuilderPageInspector
        page={{ id: "page-2", name: "Page 2", slug: "/page-2", showInNavigation: false }}
        hasRoutingIssue={false}
        onSetDefault={onSetDefault}
        onUpdate={onUpdate}
      />
    );

    expect(screen.getByDisplayValue("Page 2")).toBeTruthy();
    expect(screen.getByLabelText("Use as homepage").type).toBe("checkbox");
    expect(screen.getByLabelText("Show this page in the header").type).toBe("checkbox");
    expect(screen.queryByLabelText("Page address")).toBeNull();
    fireEvent.change(screen.getByLabelText("Page name"), { target: { value: "Our Services" } });
    fireEvent.click(screen.getByLabelText("Use as homepage"));
    fireEvent.click(screen.getByLabelText("Show this page in the header"));
    expect(onUpdate).toHaveBeenCalledWith({ name: "Our Services" });
    expect(onSetDefault).toHaveBeenCalledWith(true);
    expect(onUpdate).toHaveBeenCalledWith({ showInNavigation: true });
  });

  it("keeps a custom navigation label separate from the page name", () => {
    const onUpdate = vi.fn();
    render(
      <PageBuilderPageInspector
        page={{ id: "home", name: "Home", slug: "/", isDefault: true }}
        hasRoutingIssue={false}
        onSetDefault={vi.fn()}
        onUpdate={onUpdate}
      />
    );
    fireEvent.change(screen.getByLabelText("Navigation label"), { target: { value: "Start" } });
    expect(onUpdate).toHaveBeenCalledWith({ navigationLabel: "Start" });
  });

  it("preserves a typed space so multi-word page names can be entered", () => {
    const onUpdate = vi.fn();
    render(
      <PageBuilderPageInspector
        page={{ id: "home", name: "Home", slug: "/", isDefault: true }}
        hasRoutingIssue={false}
        onSetDefault={vi.fn()}
        onUpdate={onUpdate}
      />
    );

    const input = screen.getByLabelText("Page name");
    fireEvent.change(input, { target: { value: "Home " } });
    expect(onUpdate).toHaveBeenCalledWith({ name: "Home " });
  });
});
