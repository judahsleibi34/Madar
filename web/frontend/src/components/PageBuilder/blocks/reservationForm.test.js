import { describe, expect, it } from "vitest";

import { createReservationFormItem, normalizeReservationFormItems } from "./reservationForm";

describe("reservation form schema", () => {
  it("creates editable presets and normalizes unsafe or duplicate controls", () => {
    expect(createReservationFormItem("radio")).toEqual(expect.objectContaining({
      type: "radio",
      options: ["Option 1", "Option 2"],
    }));

    const normalized = normalizeReservationFormItems([
      { id: "title", type: "heading", text: "  Welcome  " },
      { id: "choice", type: "checkbox", label: " Topics ", options: [" Design ", "", "Build"], required: true },
      { id: "slots-1", type: "availability", label: " Pick a time " },
      { id: "slots-2", type: "availability", label: " Duplicate " },
      { id: "submit-1", type: "button", label: "Send" },
      { id: "submit-2", type: "button", label: "Duplicate" },
      { id: "unsafe", type: "html", text: "<script />" },
    ]);

    expect(normalized).toHaveLength(4);
    expect(normalized[0].text).toBe("Welcome");
    expect(normalized[1]).toEqual(expect.objectContaining({ options: ["Design", "Build"], required: true }));
    expect(normalized.filter((item) => item.type === "button")).toHaveLength(1);
    expect(normalized.filter((item) => item.type === "availability")).toEqual([
      expect.objectContaining({ label: "Pick a time" }),
    ]);
  });
});