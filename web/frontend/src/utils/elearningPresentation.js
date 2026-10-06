// Development fixture identifiers belong to stored data, not visible descriptions.
export function learningDescription(value) {
  if (typeof value !== "string") return "";
  const marker = /^\s*\[Development seed:[^\]]+\]\s*/;
  if (!marker.test(value)) return value;
  return value.replace(marker, "").replace(/\s*Summary only; content has not been built\.\s*$/, "");
}
