import { expect, it } from "vitest";
import { learningDescription } from "./elearningPresentation";
it("hides fixture metadata while preserving the course description", () => {
  expect(learningDescription("[Development seed: madar-elearning-demo-v1] Practice thoughtful decisions, coaching, and collaborative team leadership.")).toBe("Practice thoughtful decisions, coaching, and collaborative team leadership.");
  expect(learningDescription("[Development seed: madar-elearning-demo-v1] Guided practice: coaching. Summary only; content has not been built.")).toBe("Guided practice: coaching.");
});
it("preserves ordinary text and handles absent descriptions", () => {
  expect(learningDescription("Learn leadership.\nPractice together.")).toBe("Learn leadership.\nPractice together.");
  expect(learningDescription("Explain [Development seed: example] in a lesson.")).toBe("Explain [Development seed: example] in a lesson.");
  expect(learningDescription(null)).toBe("");
});
