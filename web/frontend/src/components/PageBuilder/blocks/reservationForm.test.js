import { describe, expect, it } from "vitest";

import {
  createReservationFormItem,
  getReservationAnswerError,
  isValidRegionalPhone,
  isValidReservationEmail,
  normalizeReservationFormItems,
  normalizeReservationPhone,
  localizeReservationFormItem,
} from "./reservationForm";

describe("reservation form schema", () => {
  it("translates known starter components while preserving custom text and submitted options", () => {
    for (const type of ["heading", "paragraph", "availability", "text", "email", "phone", "checkbox", "radio", "button"]) {
      const item = createReservationFormItem(type);
      const localized = localizeReservationFormItem(item, "ar");
      const key = ["heading", "paragraph"].includes(type) ? "text" : "label";
      expect(localized[key]).not.toBe(item[key]);
      expect(localizeReservationFormItem(item, "en")[key]).toBe(item[key]);
    }
    const choice = createReservationFormItem("radio");
    expect(localizeReservationFormItem(choice, "ar").options).toEqual(["Option 1", "Option 2"]);
    expect(localizeReservationFormItem(choice, "ar").optionLabels).toEqual({ "Option 1": "الخيار 1", "Option 2": "الخيار 2" });
    const custom = { id: "intro", type: "heading", text: "An authored headline" };
    expect(localizeReservationFormItem(custom, "ar").text).toBe(custom.text);
    expect(localizeReservationFormItem({ ...createReservationFormItem("heading"), translations: { ar: { text: "عنواني الخاص" } } }, "ar").text).toBe("عنواني الخاص");
  });
  it("provides Arabic validation messages without changing validation rules", () => {
    expect(getReservationAnswerError({ type: "email" }, "invalid", "ar")).toMatch(/بريدًا إلكترونيًا/);
    expect(getReservationAnswerError({ type: "phone" }, "123", "ar")).toMatch(/رقم هاتف/);
    expect(getReservationAnswerError({ type: "phone" }, "+970599000000", "ar")).toBe("");
  });
  it("preserves direction overrides for each translation and mirrors Arabic fallback content", () => {
    const [item] = normalizeReservationFormItems([{ id: "intro", type: "heading", text: "Book", direction: "ltr",
      translations: { ar: { direction: "ltr" } } }]);
    expect(localizeReservationFormItem(JSON.parse(JSON.stringify(item)), "ar").direction).toBe("ltr");
    expect(localizeReservationFormItem({ ...item, translations: {} }, "ar").direction).toBe("rtl");
    expect(localizeReservationFormItem(item, "en").direction).toBe("ltr");
  });
  it("preserves multiple dividers and their layouts without treating them as questions", () => {
    const items = normalizeReservationFormItems(JSON.parse(JSON.stringify([
      createReservationFormItem("divider", { id: "line1", required: true, label: "unused", layout: { desktop: { columns: 6 } } }),
      createReservationFormItem("divider", { id: "line2" }),
    ])));
    expect(items.map(item => item.id)).toEqual(["line1", "line2"]);
    expect(items[0].layout.desktop.columns).toBe(6);
    expect(items[0].required).toBeUndefined();
    expect(items[0].label).toBeUndefined();
    expect(getReservationAnswerError(items[0], "")).toBe("");
  });
  it("preserves translations through saving while keeping canonical choice values", () => {
    const [item] = normalizeReservationFormItems([{ id: "time", type: "radio", label: "Time",
      options: ["Morning", "Evening"], translations: {
        ar: { label: " الوقت ", options: { Morning: "صباحًا", Unknown: "ignored" } },
        en: { label: "", placeholder: 123 }, fr: { label: "ignored" },
      } }]);
    expect(item.translations).toEqual({ ar: { label: "الوقت", options: { Morning: "صباحًا" } }, en: { label: "" } });
    const [reloaded] = normalizeReservationFormItems(JSON.parse(JSON.stringify([item])));
    const arabic = localizeReservationFormItem(reloaded, "ar-PS");
    expect(arabic.label).toBe("الوقت");
    expect(arabic.direction).toBe("rtl");
    expect(arabic.options).toEqual(["Morning", "Evening"]);
    expect(arabic.optionLabels).toEqual({ Morning: "صباحًا" });
    expect(localizeReservationFormItem(reloaded, "en").label).toBe("Time");
    expect(reloaded.label).toBe("Time");
    expect(localizeReservationFormItem({ type: "heading", text: "Book", translations: { ar: { text: "احجز" } } }, "ar").textStyle)
      .toEqual(expect.objectContaining({ textAlign: "right", fontFamily: "IBM Plex Sans Arabic" }));
  });
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
  it("validates dedicated email and Palestinian or Israeli phone fields", () => {
    expect(createReservationFormItem("email")).toEqual(expect.objectContaining({ type: "email", required: true }));
    expect(createReservationFormItem("phone")).toEqual(expect.objectContaining({ type: "phone", required: true }));
    expect(isValidReservationEmail("person@example.com")).toBe(true);
    expect(isValidReservationEmail("not-an-email")).toBe(false);
    expect(isValidRegionalPhone("+970 59 123 4567")).toBe(true);
    expect(isValidRegionalPhone("00972-50-123-4567")).toBe(true);
    expect(isValidRegionalPhone("+971 50 123 4567")).toBe(false);
    expect(normalizeReservationPhone("00970 (59) 123-4567")).toBe("+970591234567");
    expect(getReservationAnswerError({ type: "phone" }, "+971501234567")).toContain("+970");
  });
});
