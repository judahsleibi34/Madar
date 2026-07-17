import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PageBuilderTopbar from "./PageBuilderTopbar";

describe("PageBuilderTopbar", () => {
  it("keeps project identity in the header without duplicating sidebar save controls", () => {
    render(
      <PageBuilderTopbar
        project={{ name: "Site" }}
        activeHelper="Build pages"
      />
    );

    expect(screen.getByRole("heading", { name: "Site" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Save$/i })).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });
});
