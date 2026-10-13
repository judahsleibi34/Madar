// EduHope Levels: Levels 1–2 A1, 3–4 A2, 5–6 B1, 7–8 B2, 9–10 C1 (owner documents).
export const levelCefr = index => ["A1", "A1", "A2", "A2", "B1", "B1", "B2", "B2", "C1", "C1"][index] || "";

/** Level state from a course section: Locked, Available, In Progress (%), Completed. */
export function levelState(section) {
  const lessons = section.lessons || [];
  if (lessons.length && lessons.every(lesson => lesson.completed)) return "completed";
  if (lessons.length && lessons.every(lesson => lesson.locked)) return "locked";
  if (lessons.some(lesson => lesson.completed) || Number(section.progress_percent) > 0) return "inProgress";
  return "available";
}

export function courseLevels(course) {
  return (course?.sections || []).map((section, index) => ({ ...section, number: index + 1, cefr: levelCefr(index), state: levelState(section) }));
}

/** The first Level that is not completed, else the last one. */
export function currentLevel(levels) {
  return levels.find(level => level.state !== "completed" && level.state !== "locked") || levels.find(level => level.state !== "completed") || levels.at(-1) || null;
}
