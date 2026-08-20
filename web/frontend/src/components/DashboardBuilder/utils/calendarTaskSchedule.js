export function taskIsOpen(task) {
  return !["done", "cancelled"].includes(task?.status);
}

export function taskPlacementStart(task) {
  return task?.scheduled_start || task?.due_at || null;
}

function advanceTaskOccurrence(date, rule, anchorDay) {
  const next = new Date(date);
  if (rule === "FREQ=DAILY") next.setDate(next.getDate() + 1);
  else if (rule === "FREQ=WEEKLY") next.setDate(next.getDate() + 7);
  else if (rule === "FREQ=MONTHLY") {
    next.setDate(1);
    next.setMonth(next.getMonth() + 1);
    const lastDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate();
    next.setDate(Math.min(anchorDay, lastDay));
  }
  return next;
}

export function expandTaskOccurrences(tasks, rangeStart, rangeEnd) {
  const occurrences = [];
  tasks.forEach((task) => {
    const placementStart = taskPlacementStart(task);
    if (!placementStart) return;
    const baseStart = new Date(placementStart);
    const duration = task.scheduled_end
      ? Math.max(0, new Date(task.scheduled_end) - baseStart)
      : Number(task.estimate_minutes || 60) * 60000;
    if (!task.recurrence_rule) {
      if (baseStart >= rangeStart && baseStart < rangeEnd) {
        occurrences.push({
          ...task,
          agenda_start: baseStart.toISOString(),
          agenda_end: new Date(baseStart.getTime() + duration).toISOString(),
        });
      }
      return;
    }
    let occurrence = new Date(baseStart);
    const anchorDay = baseStart.getDate();
    let guard = 0;
    while (occurrence < rangeStart && guard < 1000) {
      occurrence = advanceTaskOccurrence(occurrence, task.recurrence_rule, anchorDay);
      guard += 1;
    }
    while (occurrence < rangeEnd && guard < 1000) {
      occurrences.push({
        ...task,
        agenda_start: occurrence.toISOString(),
        agenda_end: new Date(occurrence.getTime() + duration).toISOString(),
      });
      occurrence = advanceTaskOccurrence(occurrence, task.recurrence_rule, anchorDay);
      guard += 1;
    }
  });
  return occurrences;
}
