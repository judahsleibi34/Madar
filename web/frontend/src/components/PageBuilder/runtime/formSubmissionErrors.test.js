import { describe, expect, it } from "vitest";

import { getSubmissionErrorGuidance } from "./formSubmissionErrors";

const fields = [
  { id: "email", label: "Email address" },
  { id: "notes", label: "Notes" },
];

describe("form submission error guidance", () => {
  it("attaches a backend required-field rejection to the correct field", () => {
    const guidance = getSubmissionErrorGuidance({
      status: 400,
      data: { detail: { message: "Required field is missing", field_id: "email", field_label: "Email address" } },
    }, fields);

    expect(guidance.title).toBe("Please complete the required field");
    expect(guidance.fieldErrors).toEqual({ email: "Email address is required." });
    expect(guidance.firstFieldId).toBe("email");
  });

  it("guides the user to shorten an oversized field", () => {
    const guidance = getSubmissionErrorGuidance({
      status: 413,
      data: { detail: { message: "Submission answer is too large", field_id: "notes", max_length: 5000 } },
    }, fields);

    expect(guidance.fieldErrors.notes).toContain("5,000 characters or fewer");
  });

  it("turns a server type rejection into field-level guidance", () => {
    const guidance = getSubmissionErrorGuidance({
      status: 400,
      data: { detail: {
        message: "Invalid field value", field_id: "email", field_label: "Email address", reason: "email",
      } },
    }, fields);

    expect(guidance.title).toBe("Please correct this field");
    expect(guidance.fieldErrors.email).toBe("Enter a valid email address.");
  });

  it("maps validation arrays without exposing backend messages", () => {
    const guidance = getSubmissionErrorGuidance({
      status: 422,
      data: { detail: [
        { loc: ["body", "answers", "email"], msg: "backend implementation detail" },
        { loc: ["body", "answers", "notes"], msg: "another backend detail" },
      ] },
    }, fields);

    expect(guidance.fieldErrors.email).toContain("cannot accept");
    expect(guidance.fieldErrors.notes).toContain("cannot accept");
    expect(guidance.message).toContain("2 highlighted fields");
    expect(guidance.message).not.toContain("backend implementation detail");
  });

  it.each([
    [0, "Could not reach the server"],
    [400, "Please check the form"],
    [401, "Your session ended"],
    [403, "Submission is not allowed"],
    [404, "Form unavailable"],
    [408, "The request timed out"],
    [409, "The form changed"],
    [410, "This form session expired"],
    [413, "The submission is too large"],
    [422, "Please check the form"],
    [429, "Please wait before trying again"],
    [500, "The server could not save the form"],
    [503, "The server could not save the form"],
  ])("handles HTTP status %s", (status, title) => {
    expect(getSubmissionErrorGuidance({ status }, fields).title).toBe(title);
  });

  it("provides recovery guidance for an expired quiz", () => {
    const guidance = getSubmissionErrorGuidance({ code: "quiz_attempt_expired", status: 410 }, fields);
    expect(guidance.message).toContain("Start a new attempt");
  });
});
