import { describe, expect, it } from "vitest";

import {
  sanitizeCsvForSpreadsheetExport,
  sanitizeSpreadsheetCell,
  sanitizeSpreadsheetRows,
} from "./dataframeExport";

describe("spreadsheet export sanitization", () => {
  it.each([
    ['=HYPERLINK("http://evil.example","click")'],
    ["+cmd"],
    ["-SUM(1,2)"],
    ["@formula"],
    ["\t=FORMULA"],
    ["\r=FORMULA"],
    ["   =FORMULA"],
    ["-123"],
  ])("prefixes dangerous string cell %s", (value) => {
    expect(sanitizeSpreadsheetCell(value)).toBe(`'${value}`);
  });

  it("preserves normal strings, nullish values, and numeric negatives", () => {
    expect(sanitizeSpreadsheetCell("hello world")).toBe("hello world");
    expect(sanitizeSpreadsheetCell(null)).toBeNull();
    expect(sanitizeSpreadsheetCell(undefined)).toBeUndefined();
    expect(sanitizeSpreadsheetCell(-123)).toBe(-123);
  });

  it("sanitizes every string cell in row arrays", () => {
    expect(
      sanitizeSpreadsheetRows([
        ["Name", "Formula", "Number"],
        ["Alice", "=SUM(1,2)", -123],
        ["Bob", "   @formula", "-123"],
      ])
    ).toEqual([
      ["Name", "Formula", "Number"],
      ["Alice", "'=SUM(1,2)", -123],
      ["Bob", "'   @formula", "'-123"],
    ]);
  });

  it("sanitizes parsed CSV output before browser downloads", () => {
    expect(
      sanitizeCsvForSpreadsheetExport(
        'name,value,notes\nAlice,"=HYPERLINK(""http://evil.example"",""click"")",ok\nBob,+cmd,"   @formula"'
      )
    ).toBe(
      'name,value,notes\nAlice,"\'=HYPERLINK(""http://evil.example"",""click"")",ok\nBob,\'+cmd,\'   @formula'
    );
  });
});
