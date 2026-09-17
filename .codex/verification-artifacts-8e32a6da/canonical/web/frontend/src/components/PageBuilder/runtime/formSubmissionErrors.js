const asObject = (value) =>
  value && typeof value === "object" && !Array.isArray(value) ? value : {};

const cleanText = (value) => typeof value === "string" ? value.trim() : "";

const fieldLabel = (fields, fieldId, fallback = "This field") => {
  const match = fields.find((field) => String(field?.id || "") === String(fieldId || ""));
  return cleanText(match?.label) || fallback;
};

const result = (title, message, { fieldId = "", fieldMessage = "" } = {}) => ({
  title,
  message,
  fieldErrors: fieldId && fieldMessage ? { [fieldId]: fieldMessage } : {},
  firstFieldId: fieldId || "",
});

const pydanticFieldId = (item, fields) => {
  const location = Array.isArray(item?.loc) ? item.loc.map(String) : [];
  const answersIndex = location.indexOf("answers");
  if (answersIndex >= 0 && location[answersIndex + 1]) {
    const candidate = location[answersIndex + 1];
    return fields.some((field) => String(field?.id || "") === candidate) ? candidate : "";
  }
  return "";
};

/**
 * Convert every public-form API failure into safe, actionable guidance.
 * Backend/provider messages are deliberately not displayed directly.
 */
export const getSubmissionErrorGuidance = (error = {}, fields = [], copy = {}) => {
  const detail = error?.data?.detail;
  const detailObject = asObject(detail);
  const code = cleanText(detailObject.code || error?.code).toLowerCase();
  const backendMessage = cleanText(detailObject.message);
  const status = Number(error?.status || 0);
  const errors = copy?.errors || {};

  if (backendMessage === "Required field is missing") {
    const fieldId = cleanText(detailObject.field_id);
    const label = cleanText(detailObject.field_label) || fieldLabel(fields, fieldId, errors.requiredFallback || "This field");
    const message = `${label} ${errors.requiredSuffix || "is required."}`;
    return result("Please complete the required field", message, { fieldId, fieldMessage: message });
  }

  if (backendMessage === "Submission answer is too large") {
    const fieldId = cleanText(detailObject.field_id);
    const maxLength = Number(detailObject.max_length || 0);
    const label = fieldLabel(fields, fieldId);
    const message = maxLength > 0
      ? `${label} is too long. Shorten it to ${maxLength.toLocaleString()} characters or fewer.`
      : `${label} is too long. Shorten the answer and try again.`;
    return result("Please shorten an answer", message, { fieldId, fieldMessage: message });
  }

  if (backendMessage === "Invalid field value") {
    const fieldId = cleanText(detailObject.field_id);
    const label = cleanText(detailObject.field_label) || fieldLabel(fields, fieldId);
    const messages = {
      text: `${label} must contain text.`,
      email: "Enter a valid email address.",
      website: "Enter a complete website address beginning with http:// or https://.",
      phone: "Enter a valid phone number.",
      number: "Enter a valid number.",
      amount: "Enter a valid amount.",
      date: "Choose a valid date.",
      time: "Choose a valid time.",
      choice: "Choose one of the available options.",
      choices: "Choose only from the available options.",
      scale: "Choose a value within the displayed range.",
      file: "Choose a valid file.",
      file_size: "Choose a smaller file.",
    };
    const message = messages[cleanText(detailObject.reason)] || `${label} contains a value the form cannot accept.`;
    return result("Please correct this field", message, { fieldId, fieldMessage: message });
  }

  if (backendMessage === "Submission contains unknown fields") {
    return result("The form was updated", errors.unknownFields || "Refresh this page, review your answers, and submit again.");
  }

  if (backendMessage === "Submission contains too many answer fields") {
    return result("The form could not be submitted", "This form contains more answers than the server accepts. Refresh the page. If it still happens, contact the form owner.");
  }

  if (backendMessage === "Submission answers payload is too large" || status === 413) {
    return result("The submission is too large", "Shorten long answers or remove large attachments, then submit again. Your answers are still here.");
  }

  if (Array.isArray(detail)) {
    const fieldErrors = detail.reduce((allErrors, item) => {
      const fieldId = pydanticFieldId(item, fields);
      if (fieldId) {
        const label = fieldLabel(fields, fieldId);
        allErrors[fieldId] = `${label} contains a value the form cannot accept. Correct it and try again.`;
      }
      return allErrors;
    }, {});
    const invalidFieldIds = Object.keys(fieldErrors);
    const message = invalidFieldIds.length === 1
      ? fieldErrors[invalidFieldIds[0]]
      : invalidFieldIds.length > 1
        ? `Correct the ${invalidFieldIds.length} highlighted fields, then submit again.`
        : "Some submitted information has an invalid format. Review the form and try again.";
    return {
      title: "Please check the form",
      message,
      fieldErrors,
      firstFieldId: invalidFieldIds[0] || "",
    };
  }

  const codeMessages = {
    submission_rejected: ["Submission needs attention", "Wait a moment, review your answers, and submit again."],
    idempotency_conflict: ["The submission changed", "Your answers were not lost. Review them and submit again."],
    idempotency_key_invalid: ["Please try submitting again", "Your answers are still here. Submit the form again."],
    quiz_attempt_required: ["Restart the quiz", "This quiz needs a new attempt before it can be submitted."],
    quiz_mode_required: ["This quiz changed", "Refresh the page before starting again."],
    quiz_attempt_limit_reached: ["No attempts remaining", "You have used all available attempts. Contact the form owner if you need another attempt."],
    quiz_attempt_invalid: ["The quiz could not be graded", "Refresh the page and start a new attempt."],
    quiz_attempt_expired: ["This quiz attempt expired", "Start a new attempt to continue."],
    dependency_unavailable: ["The service is temporarily unavailable", "Your answers are still here. Wait a moment and try again."],
    publication_forms_invalid: ["This form is temporarily unavailable", "The form owner needs to republish it. Please try again later."],
    publication_form_ids_ambiguous: ["This form is temporarily unavailable", "The form owner needs to republish it. Please try again later."],
    publication_form_ambiguous: ["This form is temporarily unavailable", "The form owner needs to republish it. Please try again later."],
  };
  if (codeMessages[code]) return result(...codeMessages[code]);

  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return result("You are offline", errors.offline || "Reconnect to the internet, then try again. Your answers are still here.");
  }

  if (status === 400) return result("Please check the form", "The server could not accept some of the information. Review your answers and try again.");
  if (status === 401) return result("Your session ended", "Refresh the page or sign in again, then submit the form. Save your progress first if needed.");
  if (status === 402 || status === 403) return result("Submission is not allowed", "You do not currently have permission to submit this form. Sign in if required or contact the form owner.");
  if (status === 404) return result("Form unavailable", errors.unavailable || "This form is no longer available. Refresh the page or contact the form owner.");
  if (status === 408 || status === 504) return result("The request timed out", "Your answers are still here. Check your connection and try again.");
  if (status === 409) return result("The form changed", "Your answers are still here. Refresh the page, review them, and submit again.");
  if (status === 410) return result("This form session expired", "Refresh the page and try again. Save a draft first if the option is available.");
  if (status === 422) return result("Please check the form", "Some information has an invalid format. Review your answers and try again.");
  if (status === 429) return result("Please wait before trying again", errors.tooMany || "Too many submissions were made. Wait a moment, then try again.");
  if (status >= 500) return result("The server could not save the form", "Your answers are still here. Wait a moment and try again. If it continues, contact the form owner.");
  if (status === 0) return result("Could not reach the server", "Check your internet connection and try again. Your answers are still here.");

  return result("Could not submit the form", errors.generic || "Review your answers and try again. Your answers are still here.");
};
