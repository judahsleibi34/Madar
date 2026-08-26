export const normalizeBackendResponse = (submission) => ({
  id: submission?.id || `submission_${Date.now()}`,
  createdAt: submission?.createdAt || submission?.submitted_at || submission?.created_at || "",
  status: submission?.status || "New",
  answers: submission?.answers && typeof submission.answers === "object" ? submission.answers : {},
  quiz: submission?.quiz || submission?.quiz_result || null,
  resumeToken: submission?.resumeToken || "",
  pageIndex: Math.max(0, Number(submission?.pageIndex) || 0),
  language: submission?.language || "en",
  backendSubmission: true,
});

export const normalizeStatus = (status) => String(status || "New").trim().toLowerCase();

export const uniqueByNormalizedStatus = (statuses) => {
  const seen = new Set();
  return statuses.filter((status) => {
    const key = normalizeStatus(status);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

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
