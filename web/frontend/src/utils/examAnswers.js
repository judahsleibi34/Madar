// Whether an exam question has a complete answer.
export const answered = (question, answer) => {
  if (!answer) return false;
  if (["matching", "listen_match"].includes(question.type)) return Object.values(answer.matches || {}).filter(Boolean).length === (question.config.prompts || []).length;
  return true;
};
