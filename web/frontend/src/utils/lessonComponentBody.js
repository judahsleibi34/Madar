// Plain-text fallback for a structured lesson card: academies that have not
// opted in (and any older client) still show readable content.
export const LESSON_COMPONENT_KINDS = ["situation", "vocabulary", "expressions", "speaker_tip"];

export function componentBody(component) {
  if (!component) return "";
  const line = (...parts) => parts.filter(Boolean).join(" — ");
  if (component.kind === "vocabulary") return component.items.map(item => [line(item.word, item.meaning), item.arabic, item.example && `Example: ${item.example}`].filter(Boolean).join("\n")).join("\n\n");
  if (component.kind === "expressions") return component.items.map(item => [line(`“${item.expression}”`, item.meaning), item.arabic, item.example].filter(Boolean).join("\n")).join("\n\n");
  if (component.kind === "speaker_tip") return [component.tip, component.arabic, component.avoid && `Avoid: ${component.avoid}`, component.say && `Say: ${component.say}`].filter(Boolean).join("\n");
  if (component.kind === "situation") return component.text;
  return "";
}

export function emptyComponent(kind) {
  if (kind === "vocabulary") return { kind, items: [{ word: "", meaning: "", arabic: "", example: "", pronunciation: "", stress: "" }] };
  if (kind === "expressions") return { kind, items: [{ expression: "", meaning: "", arabic: "", example: "" }] };
  if (kind === "speaker_tip") return { kind, tip: "", arabic: "", avoid: "", say: "" };
  return { kind: "situation", text: "" };
}

export function componentComplete(component) {
  if (!component) return false;
  if (component.kind === "vocabulary") return component.items.length > 0 && component.items.every(item => item.word.trim() && item.meaning.trim());
  if (component.kind === "expressions") return component.items.length > 0 && component.items.every(item => item.expression.trim());
  if (component.kind === "speaker_tip") return Boolean(component.tip.trim());
  return Boolean(component.text?.trim());
}
