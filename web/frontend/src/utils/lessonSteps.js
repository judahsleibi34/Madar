// The book document's topic structure (§10, A–K), as learner-visible steps. The
// topic title (A) is the lesson heading; C–E (dialogue, listen, transcript) are
// one Listen step because the dialogue recording carries its own transcript.
export const LESSON_STEPS = ["situation", "listen", "understand", "expressions", "vocabulary", "listenMatch", "communication", "speak", "review"];

const CHOICE = new Set(["multiple_choice", "true_false", "matching"]);

function stepOf(block, seen) {
  if (block.type === "audio" || block.type === "video") return "listen";
  if (block.type === "text") {
    const kind = block.content?.component?.kind;
    if (kind === "situation") return "situation";
    if (kind === "expressions") return "expressions";
    if (kind === "vocabulary" || kind === "speaker_tip") return "vocabulary";
    return null;
  }
  if (block.type === "assessment") {
    const assessment = block.assessment || {};
    const types = assessment.question_types || [];
    if (assessment.activity_mode !== "practice") return "review";
    if (types.length && types.every(type => type === "picture_listen" || type === "listen_match")) return "listenMatch";
    if (types.length && types.every(type => type === "speaking_practice" || type === "speaking")) return "speak";
    if (types.some(type => CHOICE.has(type))) return seen.has("understand") || seen.has("expressions") || seen.has("vocabulary") ? "communication" : "understand";
    return "communication";
  }
  return null;
}

/**
 * Group lesson blocks into the book's steps. Plain text blocks stay with the
 * step they follow (leading ones join the first step), so the owner's wording
 * is never dropped. Returns [{ step, blocks }] in book order.
 */
export function assembleLessonSteps(blocks) {
  const seen = new Set(), placed = [];
  let previous = null;
  for (const block of blocks) {
    const step = stepOf(block, seen);
    if (step) { seen.add(step); previous = step; }
    placed.push({ block, step: step || previous });
  }
  const first = placed.find(entry => entry.step)?.step || "situation";
  const groups = new Map();
  for (const entry of placed) {
    const step = entry.step || first;
    if (!groups.has(step)) groups.set(step, []);
    groups.get(step).push(entry.block);
  }
  return LESSON_STEPS.filter(step => groups.has(step)).map(step => ({ step, blocks: groups.get(step) }));
}

export const stepAnchor = step => `lesson-step-${step}`;
