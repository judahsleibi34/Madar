import { describe, expect, it } from "vitest";

import { elementTypes } from "./PageBuilder.constants";
import { createElement } from "./PageBuilder.factories";
import { directElementHeight, getDirectElementMinimumSize } from "./PageBuilder.layout";

describe("horizontal line", () => {
  it("is available as a separate Word-style rule with compact dimensions", () => {
    expect(elementTypes).toContainEqual({
      id: "thinDivider",
      label: "Horizontal Line",
      group: "Content",
    });

    const divider = createElement("thinDivider");
    expect(divider.name).toBe("Horizontal Line");
    expect(divider.styles.color).toBe("var(--theme-border-strong)");
    expect(divider.styles.backgroundColor).toBe("transparent");
    expect(divider.styles["--divider-thickness"]).toBe("1px");
    expect(getDirectElementMinimumSize(divider)).toEqual({ width: 80, height: 24 });
    expect(directElementHeight(divider)).toBe(32);
  });
});
