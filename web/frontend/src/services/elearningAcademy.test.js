import { expect, it } from "vitest";
import { academyReturnPath } from "./elearningAcademy";
const base = "/academy/tenant", origin = "https://app.example.com";
it.each([
  [`${base}/courses/course?plan=plan#access`, `${base}/courses/course?plan=plan#access`],
  ["/academy/other/courses/course", base],
  ["https://other.example.com/academy/tenant/courses", base],
  [`${base}/../../admin`, base],
  [`${base}/%2e%2e/other`, base],
  ["//other.example.com/academy/tenant", base],
  [`${base}/%252e%252e/other`, base],
  [`${base}/%255c%255cevil.test`, base],
  [`${base}\\..\\other`, base],
])("safely resumes Academy authentication from %s", (requested, expected) => {
  expect(academyReturnPath(requested, base, origin)).toBe(expected);
});
