import { describe, expect, it } from "vitest";
import { assembleLessonSteps } from "./lessonSteps";

const text = (id, kind) => ({ id, type: "text", content: kind ? { component: { kind } } : { body: "x" } });
const quiz = (id, types, mode = "practice") => ({ id, type: "assessment", assessment: { activity_mode: mode, question_types: types } });

describe("lesson steps follow the book's topic structure", () => {
  it("orders blocks as Situation, Listen, Understand, Expressions, Vocabulary, Listen & Match, Communication, Speak Now, Review", () => {
    // Stored order differs from the book; the first choice quiz before any
    // expressions or vocabulary is "Understand", later ones are practice.
    const blocks = [quiz("speak", ["speaking_practice"]), quiz("understand", ["multiple_choice"]), text("vocab", "vocabulary"), { id: "audio", type: "audio" }, text("situation", "situation"),
      quiz("exam", ["written"], "graded"), text("expr", "expressions"), quiz("lm", ["picture_listen"]), quiz("best", ["multiple_choice"]), text("tip", "speaker_tip")];
    expect(assembleLessonSteps(blocks).map(group => [group.step, group.blocks.map(block => block.id)])).toEqual([
      ["situation", ["situation"]], ["listen", ["audio"]], ["understand", ["understand"]], ["expressions", ["expr"]], ["vocabulary", ["vocab", "tip"]],
      ["listenMatch", ["lm"]], ["communication", ["best"]], ["speak", ["speak"]], ["review", ["exam"]]]);
  });
  it("keeps plain text with the step it follows and never drops a block", () => {
    const blocks = [text("intro"), { id: "audio", type: "audio" }, text("note"), quiz("lm", ["picture_listen"])];
    const groups = assembleLessonSteps(blocks);
    expect(groups.map(group => [group.step, group.blocks.map(block => block.id)])).toEqual([["listen", ["intro", "audio", "note"]], ["listenMatch", ["lm"]]]);
    expect(groups.flatMap(group => group.blocks)).toHaveLength(blocks.length);
  });
});
