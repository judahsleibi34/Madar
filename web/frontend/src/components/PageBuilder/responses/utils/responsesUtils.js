export const normalizeBackendResponse = (submission) => ({
  id: submission?.id || `submission_${Date.now()}`,
  createdAt: submission?.createdAt || submission?.submitted_at || submission?.created_at || "",
  status: submission?.status || "New",
  answers: submission?.answers && typeof submission.answers === "object" ? submission.answers : {},
  quiz: submission?.quiz || submission?.quiz_result || null,
  resumeToken: submission?.resumeToken || "",
  pageIndex: Math.max(0, Number(submission?.pageIndex) || 0),
  language: submission?.language || "en",
  submittedBy: submission?.submittedBy || submission?.submitted_by || {
    user_id: null,
    membership_id: null,
    name: "Guest",
    email: "",
    role: "guest",
    authenticated: false,
  },
  backendSubmission: true,
});

export const normalizeStatus = (status) => String(status || "New").trim().toLowerCase();

export const uniqueByNormalizedStatus = (statuses) => {
  const seen = new Set();
  return statuses.filter((status) => {
    const label = String(status === null || status === undefined ? "" : status).trim();
    if (!label) return false;
    const key = normalizeStatus(label);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export const isStatusField = (field) =>
  field?.type === "status" || /(^|\s)status($|\s)/i.test(String(field?.label || "").trim());

const statusAnswerValues = (value) => {
  if (Array.isArray(value)) return value;
  return value === undefined || value === null || value === "" ? [] : [value];
};

export const getResponseStatusValues = (response, statusFields = []) => [
  response?.status || "New",
  ...statusFields.flatMap((field) => statusAnswerValues(response?.answers?.[field.id])),
];

export const getDynamicStatusOptions = (fields, responses) => {
  const statusFields = fields.filter(isStatusField);
  const configuredOptions = statusFields.flatMap((field) =>
    Array.isArray(field.options) ? field.options : []
  );
  const savedValues = responses.flatMap((response) =>
    getResponseStatusValues(response, statusFields)
  );

  return uniqueByNormalizedStatus([...configuredOptions, ...savedValues]);
};

export const getAnswerSearchText = (answers, formatSavedValue) =>
  Object.values(answers || {})
    .map((value) => formatSavedValue(value))
    .filter((value) => value !== undefined && value !== null)
    .join(" ")
    .toLowerCase();

export const getResponseLoadMessage = (error, t) => {
  if (error?.status === 403) return t.forbidden;
  if (error?.status === 404) return t.notFound;
  return t.errorText;
};

export const hasAnswerValue = (value) =>
  value !== undefined &&
  value !== null &&
  value !== "" &&
  (!Array.isArray(value) || value.length > 0);
