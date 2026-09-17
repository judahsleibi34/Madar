import { describe, expect, it } from "vitest";
import {
  getAnswerSearchText,
  getDynamicStatusOptions,
  getResponseStatusValues,
  normalizeBackendResponse,
} from "./responsesUtils";

const formatSavedValue = (value) => {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return value.name || JSON.stringify(value);
  return String(value || "");
};

describe("response search helpers", () => {
  it("includes product names stored outside the current form fields", () => {
    const text = getAnswerSearchText(
      {
        buyer_email: "buyer@example.com",
        legacy_product: { id: "product-1", name: "Walnut Desk" },
      },
      formatSavedValue
    );

    expect(text).toContain("walnut desk");
  });

  it("builds status choices from the selected form and saved values", () => {
    const fields = [
      { id: "order_status", type: "dropdown", label: "Order status", options: ["", "Pending", "Packed"] },
    ];
    const responses = [
      { status: "New", answers: { order_status: "Shipped" } },
      { status: "Contacted", answers: { order_status: "Packed" } },
    ];

    expect(getDynamicStatusOptions(fields, responses)).toEqual([
      "Pending",
      "Packed",
      "New",
      "Shipped",
      "Contacted",
    ]);
  });

  it("returns review status and the selected form status value", () => {
    const statusFields = [{ id: "order_status", type: "status", label: "Status" }];
    expect(
      getResponseStatusValues(
        { status: "In review", answers: { order_status: "Ready" } },
        statusFields
      )
    ).toEqual(["In review", "Ready"]);
  });

  it("always normalizes a submitted user, including the Guest fallback", () => {
    expect(normalizeBackendResponse({
      id: "submission-1",
      submitted_by: { user_id: 31, name: "Ada Lovelace", role: "vip" },
    }).submittedBy.name).toBe("Ada Lovelace");
    expect(normalizeBackendResponse({ id: "submission-2" }).submittedBy.name).toBe("Guest");
  });
});
