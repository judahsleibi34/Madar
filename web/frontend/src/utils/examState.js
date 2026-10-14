// Exam card state from an assessment outline row.
export const examState = exam => exam.locked ? "locked" : exam.passed ? "passed" : exam.attempts ? "failed" : "available";
