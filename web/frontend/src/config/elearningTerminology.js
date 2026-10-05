// Stable English values are persisted in each tenant's settings document.
// Add choices here without changing the form or the storage schema.
export const elearningTerminologyGroups = [
  {
    key: "learningStructure",
    fields: [
      { key: "course_label", options: ["Course", "Program", "Training"] },
      { key: "section_label", options: ["Level", "Section", "Module", "Unit"] },
      { key: "lesson_label", options: ["Lesson", "Topic", "Chapter", "Session"] },
    ],
  },
  {
    key: "participantLabels",
    fields: [
      { key: "group_label", options: ["Group", "Class", "Cohort", "Team", "Batch"] },
      { key: "instructor_label", options: ["Instructor", "Teacher", "Trainer", "Tutor", "Coach"] },
    ],
  },
];

const defaults = { course: "Course", section: "Section", lesson: "Lesson", group: "Group", instructor: "Instructor" };
const plurals = {
  Course: "Courses", Program: "Programs", Training: "Training", Level: "Levels",
  Section: "Sections", Module: "Modules", Unit: "Units", Lesson: "Lessons", Topic: "Topics",
  Chapter: "Chapters", Session: "Sessions", Group: "Groups", Class: "Classes", Cohort: "Cohorts",
  Team: "Teams", Batch: "Batches", Instructor: "Instructors", Teacher: "Teachers", Trainer: "Trainers",
  Tutor: "Tutors", Coach: "Coaches",
};

export function getELearningTerminology(settings = {}) {
  const labels = Object.fromEntries(Object.entries(defaults).map(([key, fallback]) => {
    const value = settings?.[`${key}_label`];
    return [key, typeof value === "string" && value.trim() ? value.trim() : fallback];
  }));
  return { ...labels, plural: Object.fromEntries(Object.entries(labels).map(([key, value]) => [key, plurals[value] || `${value}s`])) };
}

