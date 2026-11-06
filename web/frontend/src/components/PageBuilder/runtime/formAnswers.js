export const getAnswerValue = (answer) =>
  answer && typeof answer === "object" && !Array.isArray(answer) && "value" in answer
    ? answer.value
    : answer;

export const isOptionAnswerChecked = (answer, option, optionIndex) => {
  if (answer && typeof answer === "object" && !Array.isArray(answer)) {
    return answer.optionIndex === optionIndex;
  }

  return answer === option;
};

export const isCheckboxOptionChecked = (answers, option, optionIndex) =>
  answers.some((answer) => {
    if (answer && typeof answer === "object" && !Array.isArray(answer)) {
      return answer.optionIndex === optionIndex;
    }

    return answer === option;
  });
