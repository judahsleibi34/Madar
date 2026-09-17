import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";
import { describe, expect, it } from "vitest";

const styles = readFileSync(
  resolve(process.cwd(), "src/styles/admin/dashboard/reservation-calendar.css"),
  "utf8"
);

describe("Calendar Reservations theme contract", () => {
  it("uses the available calendar surface width instead of the viewport", () => {
    expect(styles).toMatch(/calendar-reservations-view[\s\S]*?container: calendar-reservations \/ inline-size/);
    expect(styles).toMatch(/calendar-reservations-table \{[^}]*min-width: 760px/);
    expect(styles).toMatch(/@container calendar-reservations \(max-width: 760px\)[\s\S]*?calendar-reservations-table thead \{ display: none/);
  });

  it("uses shared theme tokens for controls and row interactions", () => {
    expect(styles).toMatch(/calendar-reservations-tools :is\(input, select, button\)[^}]*background: var\(--theme-surface-elevated\)/);
    expect(styles).toMatch(/calendar-reservations-table tbody[^}]*:hover[^}]*background: var\(--theme-primary-soft\)/);
  });

  it("keeps control labels and table actions from overlapping", () => {
    expect(styles).toMatch(/calendar-reservations-search svg[^}]*top: 50%[^}]*translateY\(-50%\)/);
    expect(styles).toMatch(/calendar-reservations-tools button[^}]*display: inline-flex[^}]*gap: 8px/);
    expect(styles).toMatch(/calendar-reservations-table th:nth-child\(6\) \{ width: 16%; \}/);
    expect(styles).not.toMatch(/calendar-reservations-table th:nth-child\(7\)/);
    expect(styles).not.toContain("calendar-reservation-expand-cell");
  });
});
