import { getFormFields } from "./PageBuilder.factories";
import { splitLines } from "./PageBuilder.text";

export const singleAnswerQuizTypes = new Set(["dropdown", "radio", "status", "yesNo", "linearScale", "rating"]);
export const textAnswerQuizTypes = new Set(["shortText", "paragraph", "email", "phone", "url", "number", "money"]);
export const correctableQuizTypes = new Set([...singleAnswerQuizTypes, "checkboxes", ...textAnswerQuizTypes]);

export const normalizeQuizAnswer = (value) => String(value ?? "").trim().toLowerCase();

export const hasQuizAnswerKey = (field = {}) => {
  if (!correctableQuizTypes.has(field.type)) return false;

  if (field.type === "checkboxes") {
    return Array.isArray(field.quizCorrectAnswer) && field.quizCorrectAnswer.length > 0;
  }

  if (textAnswerQuizTypes.has(field.type)) {
    return Array.isArray(field.quizCorrectAnswer)
      ? field.quizCorrectAnswer.some((answer) => String(answer || "").trim())
      : Boolean(String(field.quizCorrectAnswer || "").trim());
  }

  return Boolean(String(field.quizCorrectAnswer || "").trim());
};

export const isQuizAnswerCorrect = (field = {}, answer) => {
  if (!hasQuizAnswerKey(field)) return null;

  if (field.type === "checkboxes") {
    const expected = Array.isArray(field.quizCorrectAnswer)
      ? field.quizCorrectAnswer.map(normalizeQuizAnswer).sort()
      : [];
    const received = Array.isArray(answer) ? answer.map(normalizeQuizAnswer).sort() : [];

    return expected.length === received.length && expected.every((item, index) => item === received[index]);
  }

  if (textAnswerQuizTypes.has(field.type)) {
    const expectedAnswers = Array.isArray(field.quizCorrectAnswer)
      ? field.quizCorrectAnswer
      : splitLines(field.quizCorrectAnswer);
    const received = normalizeQuizAnswer(answer);

    return expectedAnswers.map(normalizeQuizAnswer).includes(received);
  }

  return normalizeQuizAnswer(field.quizCorrectAnswer) === normalizeQuizAnswer(answer);
};

export const getQuizSettings = (form = {}) => ({
  lockScreen: false,
  totalTimeLimitSec: 0,
  questionTimeLimitSec: 0,
  showQuestionTimer: true,
  showTotalTimer: true,
  scoring: "automatic",
  passingScore: 70,
  showResults: true,
  allowRetakes: true,
  maxRetakes: 0,
  ...(form.quiz || {}),
});

export const gradeQuizResponse = (form = {}, answers = {}) => {
  const settings = getQuizSettings(form);
  const fields = getFormFields(form);

  if (settings.scoring === "completion") {
    const answered = fields.filter((field) => {
      const value = answers[field.id];
      return value !== undefined && value !== null && value !== "" && (!Array.isArray(value) || value.length > 0);
    }).length;

    const score = fields.length ? Math.round((answered / fields.length) * 100) : 0;

    return {
      mode: "completion",
      correct: answered,
      total: fields.length,
      score,
      passed: score >= Number(settings.passingScore || 0),
      passingScore: Number(settings.passingScore || 0),
    };
  }

  if (settings.scoring === "manual") {
    return {
      mode: "manual",
      correct: 0,
      total: 0,
      score: null,
      passed: null,
      passingScore: Number(settings.passingScore || 0),
    };
  }

  const keyedFields = fields.filter(hasQuizAnswerKey);
  const correct = keyedFields.filter((field) => isQuizAnswerCorrect(field, answers[field.id])).length;
  const score = keyedFields.length ? Math.round((correct / keyedFields.length) * 100) : null;

  return {
    mode: "automatic",
    correct,
    total: keyedFields.length,
    score,
    passed: score === null ? null : score >= Number(settings.passingScore || 0),
    passingScore: Number(settings.passingScore || 0),
  };
};

export const formatQuizTime = (seconds = 0) => {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;

  return `${minutes}:${String(remainder).padStart(2, "0")}`;
};

