import { useEffect, useState } from "react";
import {
  fetchBuilderFormSubmissionsPage,
  updateBuilderFormSubmissionStatus,
} from "./PageBuilder.api";

const responsesText = {
  en: {
    kicker: "Form information",
    title: "Form Results",
    subtitle: "View each form, its questions, and the answers submitted by users.",
    copy: "Copy results",
    copied: "Results copied.",
    printed: "Results printed to console.",
    openBuilder: "Open builder",
    forms: "Forms",
    submissions: "Submissions",
    questions: "Questions in selected form",
    completion: "Completion",
    selectForm: "Select a form to inspect its submissions.",
    selectedForm: "Selected form",
    savedOnly: "Saved as form submissions only",
    savingTo: "Saving to",
    response: "response",
    responses: "responses",
    submission: "submission",
    submissionsLower: "submissions",
    field: "field",
    fields: "fields",
    required: "Required questions",
    optional: "Optional questions",
    formsWithData: "Forms with data",
    latest: "Latest submission",
    none: "None",
    status: "Status",
    reviewStatus: "Review Status",
    created: "Created",
    newStatus: "New",
    emptyTitle: "No submissions yet",
    emptyText: "When users submit this form, their answers will appear here as rows in this table.",
    noForm: "No form selected",
    noFormText: "Create a form first, then submitted answers will appear here.",
    loadingTitle: "Loading submissions",
    loadingText: "Fetching the latest saved submissions for this form.",
    errorTitle: "Could not load submissions",
    errorText: "Try again in a moment or confirm you still have access to this project.",
    refresh: "Refresh",
    refreshing: "Refreshing...",
    previous: "Previous",
    next: "Next",
    page: "Page",
    statusFilter: "Status filter",
    allStatuses: "All",
    filteredEmptyTitle: "No matching submissions",
    filteredEmptyText: "No submissions on this loaded page match the selected status.",
    updateStatusFailed: "Could not update submission status.",
  },
  ar: {
    kicker: "\u0645\u0639\u0644\u0648\u0645\u0627\u062a \u0627\u0644\u0646\u0645\u0648\u0630\u062c",
    title: "\u0646\u062a\u0627\u0626\u062c \u0627\u0644\u0646\u0645\u0648\u0630\u062c",
    subtitle: "\u0631\u0627\u062c\u0639 \u0643\u0644 \u0646\u0645\u0648\u0630\u062c \u0648\u0623\u0633\u0626\u0644\u062a\u0647 \u0648\u0627\u0644\u0625\u062c\u0627\u0628\u0627\u062a \u0627\u0644\u062a\u064a \u0623\u0631\u0633\u0644\u0647\u0627 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0648\u0646.",
    copy: "\u0646\u0633\u062e \u0627\u0644\u0646\u062a\u0627\u0626\u062c",
    copied: "\u062a\u0645 \u0646\u0633\u062e \u0627\u0644\u0646\u062a\u0627\u0626\u062c.",
    printed: "\u062a\u0645\u062a \u0637\u0628\u0627\u0639\u0629 \u0627\u0644\u0646\u062a\u0627\u0626\u062c \u0641\u064a \u0648\u062d\u062f\u0629 \u0627\u0644\u062a\u062d\u0643\u0645.",
    openBuilder: "\u0641\u062a\u062d \u0627\u0644\u0645\u0646\u0634\u0626",
    forms: "\u0627\u0644\u0646\u0645\u0627\u0630\u062c",
    submissions: "\u0627\u0644\u0631\u062f\u0648\u062f",
    questions: "\u0623\u0633\u0626\u0644\u0629 \u0627\u0644\u0646\u0645\u0648\u0630\u062c \u0627\u0644\u0645\u062d\u062f\u062f",
    completion: "\u0627\u0644\u0627\u0643\u062a\u0645\u0627\u0644",
    selectForm: "\u0627\u062e\u062a\u0631 \u0646\u0645\u0648\u0630\u062c\u0627 \u0644\u0645\u0631\u0627\u062c\u0639\u0629 \u0631\u062f\u0648\u062f\u0647.",
    selectedForm: "\u0627\u0644\u0646\u0645\u0648\u0630\u062c \u0627\u0644\u0645\u062d\u062f\u062f",
    savedOnly: "\u0645\u062d\u0641\u0648\u0638 \u0643\u0631\u062f\u0648\u062f \u0646\u0645\u0648\u0630\u062c \u0641\u0642\u0637",
    savingTo: "\u064a\u062a\u0645 \u0627\u0644\u062d\u0641\u0638 \u0641\u064a",
    response: "\u0631\u062f",
    responses: "\u0631\u062f\u0648\u062f",
    submission: "\u0631\u062f",
    submissionsLower: "\u0631\u062f\u0648\u062f",
    field: "\u062d\u0642\u0644",
    fields: "\u062d\u0642\u0648\u0644",
    required: "\u0627\u0644\u0623\u0633\u0626\u0644\u0629 \u0627\u0644\u0645\u0637\u0644\u0648\u0628\u0629",
    optional: "\u0627\u0644\u0623\u0633\u0626\u0644\u0629 \u0627\u0644\u0627\u062e\u062a\u064a\u0627\u0631\u064a\u0629",
    formsWithData: "\u0646\u0645\u0627\u0630\u062c \u0628\u0647\u0627 \u0628\u064a\u0627\u0646\u0627\u062a",
    latest: "\u0622\u062e\u0631 \u0631\u062f",
    none: "\u0644\u0627 \u064a\u0648\u062c\u062f",
    status: "\u0627\u0644\u062d\u0627\u0644\u0629",
    reviewStatus: "\u062d\u0627\u0644\u0629 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
    created: "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0625\u0646\u0634\u0627\u0621",
    newStatus: "\u062c\u062f\u064a\u062f",
    emptyTitle: "\u0644\u0627 \u062a\u0648\u062c\u062f \u0631\u062f\u0648\u062f \u0628\u0639\u062f",
    emptyText: "\u0639\u0646\u062f\u0645\u0627 \u064a\u0631\u0633\u0644 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0648\u0646 \u0647\u0630\u0627 \u0627\u0644\u0646\u0645\u0648\u0630\u062c\u060c \u0633\u062a\u0638\u0647\u0631 \u0625\u062c\u0627\u0628\u0627\u062a\u0647\u0645 \u0647\u0646\u0627.",
    noForm: "\u0644\u0645 \u064a\u062a\u0645 \u0627\u062e\u062a\u064a\u0627\u0631 \u0646\u0645\u0648\u0630\u062c",
    noFormText: "\u0623\u0646\u0634\u0626 \u0646\u0645\u0648\u0630\u062c\u0627 \u0623\u0648\u0644\u0627\u060c \u062b\u0645 \u0633\u062a\u0638\u0647\u0631 \u0627\u0644\u0631\u062f\u0648\u062f \u0647\u0646\u0627.",
    loadingTitle: "\u062c\u0627\u0631\u064a \u062a\u062d\u0645\u064a\u0644 \u0627\u0644\u0631\u062f\u0648\u062f",
    loadingText: "\u064a\u062a\u0645 \u062c\u0644\u0628 \u0623\u062d\u062f\u062b \u0627\u0644\u0631\u062f\u0648\u062f \u0627\u0644\u0645\u062d\u0641\u0648\u0638\u0629 \u0644\u0647\u0630\u0627 \u0627\u0644\u0646\u0645\u0648\u0630\u062c.",
    errorTitle: "\u062a\u0639\u0630\u0631 \u062a\u062d\u0645\u064a\u0644 \u0627\u0644\u0631\u062f\u0648\u062f",
    errorText: "\u062d\u0627\u0648\u0644 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649 \u0628\u0639\u062f \u0642\u0644\u064a\u0644 \u0623\u0648 \u062a\u0623\u0643\u062f \u0645\u0646 \u0635\u0644\u0627\u062d\u064a\u0629 \u0627\u0644\u0648\u0635\u0648\u0644.",
    refresh: "\u062a\u062d\u062f\u064a\u062b",
    refreshing: "\u062c\u0627\u0631\u064a \u0627\u0644\u062a\u062d\u062f\u064a\u062b...",
    previous: "\u0627\u0644\u0633\u0627\u0628\u0642",
    next: "\u0627\u0644\u062a\u0627\u0644\u064a",
    page: "\u0635\u0641\u062d\u0629",
    statusFilter: "\u062a\u0635\u0641\u064a\u0629 \u0627\u0644\u062d\u0627\u0644\u0629",
    allStatuses: "\u0627\u0644\u0643\u0644",
    filteredEmptyTitle: "\u0644\u0627 \u062a\u0648\u062c\u062f \u0631\u062f\u0648\u062f \u0645\u0637\u0627\u0628\u0642\u0629",
    filteredEmptyText: "\u0644\u0627 \u062a\u0648\u062c\u062f \u0631\u062f\u0648\u062f \u0641\u064a \u0647\u0630\u0647 \u0627\u0644\u0635\u0641\u062d\u0629 \u062a\u0637\u0627\u0628\u0642 \u0627\u0644\u062d\u0627\u0644\u0629 \u0627\u0644\u0645\u062d\u062f\u062f\u0629.",
    updateStatusFailed: "\u062a\u0639\u0630\u0631 \u062a\u062d\u062f\u064a\u062b \u062d\u0627\u0644\u0629 \u0627\u0644\u0631\u062f.",
  },
};

const normalizeBackendResponse = (submission) => ({
  id: submission?.id || `submission_${Date.now()}`,
  createdAt: submission?.createdAt || submission?.submitted_at || submission?.created_at || "",
  status: submission?.status || "New",
  answers: submission?.answers && typeof submission.answers === "object" ? submission.answers : {},
  quiz: submission?.quiz || submission?.quiz_result || null,
  backendSubmission: true,
});

const RESPONSE_PAGE_SIZE = 50;
const SUBMISSION_STATUSES = ["New", "Contacted", "Closed", "Spam", "Archived"];
const STATUS_FILTER_OPTIONS = ["All", ...SUBMISSION_STATUSES];

const normalizeStatus = (status) => String(status || "New").trim().toLowerCase();

const getResponseLoadMessage = (error, t) => {
  if (error?.status === 403) {
    return "You do not have access to these submissions.";
  }

  if (error?.status === 404) {
    return "This project, form, or submissions list was not found.";
  }

  return t.errorText;
};

export default function BuilderResponsesPage({
  lang = "en",
  user = null,
  project,
  builderProjectId = "",
  activeForm,
  selectForm,
  getFormFields,
  formatSavedValue,
  showToast,
}) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = responsesText[activeLang];
  const selectedForm = activeForm || project.forms?.[0];
  const selectedFormId = selectedForm?.id || "";
  const allForms = project.forms || [];
  const [backendResponsesByForm, setBackendResponsesByForm] = useState({});
  const [backendPaginationByForm, setBackendPaginationByForm] = useState({});
  const [responsePageByForm, setResponsePageByForm] = useState({});
  const [responsesLoading, setResponsesLoading] = useState(false);
  const [responsesError, setResponsesError] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [statusUpdatingById, setStatusUpdatingById] = useState({});
  const [refreshKey, setRefreshKey] = useState(0);
  const selectedPage = responsePageByForm[selectedFormId] || 0;
  const selectedOffset = selectedPage * RESPONSE_PAGE_SIZE;

  useEffect(() => {
    if (!builderProjectId || !selectedFormId) {
      setResponsesLoading(false);
      setResponsesError("");
      return undefined;
    }

    let cancelled = false;
    setResponsesLoading(true);
    setResponsesError("");

    fetchBuilderFormSubmissionsPage(builderProjectId, {
      form_id: selectedFormId,
      limit: RESPONSE_PAGE_SIZE,
      offset: selectedOffset,
      user_id: user?.id,
    })
      .then(({ submissions, pagination }) => {
        if (cancelled) return;
        setBackendResponsesByForm((current) => ({
          ...current,
          [selectedFormId]: submissions.map(normalizeBackendResponse),
        }));
        setBackendPaginationByForm((current) => ({
          ...current,
          [selectedFormId]: pagination,
        }));
      })
      .catch((error) => {
        if (cancelled) return;
        setResponsesError(getResponseLoadMessage(error, t));
      })
      .finally(() => {
        if (!cancelled) setResponsesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [builderProjectId, selectedFormId, selectedOffset, refreshKey, t, user?.id]);

  const refreshResponses = () => {
    if (!builderProjectId || !selectedFormId || responsesLoading) return;
    setRefreshKey((current) => current + 1);
  };

  const setSelectedPage = (page) => {
    if (!builderProjectId || !selectedFormId || responsesLoading) return;
    setResponsePageByForm((current) => ({
      ...current,
      [selectedFormId]: Math.max(0, page),
    }));
  };

  const getDisplayResponsesForForm = (form) => {
    if (!form) return [];
    if (builderProjectId && backendResponsesByForm[form.id]) {
      return backendResponsesByForm[form.id];
    }

    if (builderProjectId) return [];

    return form.responses || [];
  };

  const totalResponses = allForms.reduce(
    (total, form) => total + getDisplayResponsesForForm(form).length,
    0
  );

  const formsWithResponses = allForms.filter(
    (form) => getDisplayResponsesForForm(form).length > 0
  ).length;

  const fields = selectedForm ? getFormFields(selectedForm) : [];
  const responses = getDisplayResponsesForForm(selectedForm);
  const displayedResponses =
    statusFilter === "All"
      ? responses
      : responses.filter((response) => normalizeStatus(response.status) === normalizeStatus(statusFilter));
  const selectedPagination = backendPaginationByForm[selectedFormId];
  const isQuiz = selectedForm?.mode === "quiz";
  const requiredFields = fields.filter((field) => field.required);
  const optionalFields = Math.max(0, fields.length - requiredFields.length);
  const latestResponse = selectedPage === 0 ? responses[0] : null;
  const hasBackendPagination = Boolean(builderProjectId && selectedFormId);
  const hasNextPage = hasBackendPagination && Boolean(selectedPagination?.has_more);
  const hasPreviousPage = hasBackendPagination && selectedPage > 0;
  const answeredCells = displayedResponses.reduce(
    (total, response) =>
      total +
      fields.filter((field) => {
        const value = response.answers?.[field.id];
        return value !== undefined && value !== null && value !== "" && (!Array.isArray(value) || value.length > 0);
      }).length,
    0
  );
  const completionRate =
    displayedResponses.length && fields.length
      ? Math.round((answeredCells / (displayedResponses.length * fields.length)) * 100)
      : 0;

  const connectedCollection = selectedForm?.connectedCollectionId
    ? project.collections?.find(
        (collection) => collection.id === selectedForm.connectedCollectionId
      )
    : null;

  const updateSubmissionStatus = async (submissionId, status) => {
    if (!builderProjectId || !selectedFormId || !submissionId) return;

    setStatusUpdatingById((current) => ({ ...current, [submissionId]: true }));

    try {
      const updatedSubmission = await updateBuilderFormSubmissionStatus(
        builderProjectId,
        submissionId,
        status,
        user?.id
      );
      const normalizedSubmission = normalizeBackendResponse(updatedSubmission);

      setBackendResponsesByForm((current) => ({
        ...current,
        [selectedFormId]: (current[selectedFormId] || []).map((submission) =>
          submission.id === submissionId ? normalizedSubmission : submission
        ),
      }));
    } catch (error) {
      showToast?.(error?.message || t.updateStatusFailed);
    } finally {
      setStatusUpdatingById((current) => ({ ...current, [submissionId]: false }));
    }
  };

  const copyResults = () => {
    if (!selectedForm) return;

    const payload = {
      form: selectedForm.title,
      totalResponses: displayedResponses.length,
      statusFilter,
      exportedAt: new Date().toISOString(),
      responses: displayedResponses,
    };

    try {
      navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      showToast(t.copied);
    } catch {
      console.log(payload);
      showToast(t.printed);
    }
  };

  return (
    <div className="workspace-page responses-results-page" dir={isArabic ? "rtl" : "ltr"}>
      <div className="workspace-header responses-results-header">
        <div>
          <span className="workspace-kicker">{t.kicker}</span>
          <h2>{t.title}</h2>
          <p>{t.subtitle}</p>
        </div>

        <div className="responses-header-actions">
          <button type="button" onClick={copyResults}>
            {t.copy}
          </button>

          <button
            type="button"
            className="primary-action"
            onClick={() => {
              if (selectedForm) selectForm(selectedForm.id);
              window.location.href = "/page-builder";
            }}
          >
            {t.openBuilder}
          </button>
        </div>
      </div>

      <section className="results-summary-grid">
        <article>
          <span>{t.forms}</span>
          <strong>{allForms.length}</strong>
        </article>

        <article>
          <span>{t.submissions}</span>
          <strong>{totalResponses}</strong>
        </article>

        <article>
          <span>{t.questions}</span>
          <strong>{fields.length}</strong>
        </article>

        <article>
          <span>{t.completion}</span>
          <strong>{completionRate}%</strong>
        </article>
      </section>

      <div className="results-layout">
        <aside className="results-form-list">
          <div className="results-panel-title">
            <h3>{t.forms}</h3>
            <p>{t.selectForm}</p>
          </div>

          <div className="results-form-list-scroll">
            {allForms.map((form) => {
              const isActive = selectedForm?.id === form.id;
              const count = getDisplayResponsesForForm(form).length;
              const formFields = getFormFields(form);

              return (
                <button
                  key={form.id}
                  type="button"
                  className={isActive ? "active" : ""}
                  onClick={() => selectForm(form.id)}
                >
                  <strong>{form.title}</strong>
                  <span>
                    {count} {count === 1 ? t.submission : t.submissionsLower} /{" "}
                    {formFields.length} {formFields.length === 1 ? t.field : t.fields}
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <main className="results-table-card">
          {selectedForm ? (
            <>
              <div className="results-table-header">
                <div>
                  <span className="workspace-kicker">{t.selectedForm}</span>
                  <h3>{selectedForm.title}</h3>
                  <p>
                    {connectedCollection
                      ? `${t.savingTo} ${connectedCollection.name}`
                      : t.savedOnly}
                  </p>
                </div>

                <div className="responses-table-controls">
                  <label className="responses-status-filter">
                    <span>{t.statusFilter}</span>
                    <select
                      value={statusFilter}
                      onChange={(event) => setStatusFilter(event.target.value)}
                    >
                      {STATUS_FILTER_OPTIONS.map((status) => (
                        <option key={status} value={status}>
                          {status === "All" ? t.allStatuses : status}
                        </option>
                      ))}
                    </select>
                  </label>

                  {hasBackendPagination && (
                    <div className="responses-pagination-controls">
                      <button
                        type="button"
                        onClick={() => setSelectedPage(selectedPage - 1)}
                        disabled={!hasPreviousPage || responsesLoading}
                      >
                        {t.previous}
                      </button>
                      <span>
                        {t.page} {selectedPage + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => setSelectedPage(selectedPage + 1)}
                        disabled={!hasNextPage || responsesLoading}
                      >
                        {t.next}
                      </button>
                    </div>
                  )}

                  {hasBackendPagination && (
                    <button
                      type="button"
                      className="responses-refresh-button"
                      onClick={refreshResponses}
                      disabled={responsesLoading}
                    >
                      {responsesLoading ? t.refreshing : t.refresh}
                    </button>
                  )}

                  <div className="results-count-pill">
                    {displayedResponses.length} {displayedResponses.length === 1 ? t.response : t.responses}
                  </div>
                </div>
              </div>

              <div className="form-info-grid">
                <article>
                  <span>{t.required}</span>
                  <strong>{requiredFields.length}</strong>
                </article>
                <article>
                  <span>{t.optional}</span>
                  <strong>{optionalFields}</strong>
                </article>
                <article>
                  <span>{t.formsWithData}</span>
                  <strong>{formsWithResponses}</strong>
                </article>
                <article>
                  <span>{t.latest}</span>
                  <strong>
                    {latestResponse?.createdAt
                      ? new Date(latestResponse.createdAt).toLocaleDateString()
                      : t.none}
                  </strong>
                </article>
              </div>

              <div className="results-table-wrap">
                <table className="results-data-table">
                  <thead>
                    <tr>
                      <th>{t.reviewStatus}</th>
                      <th>{t.created}</th>
                      {isQuiz && <th>Score</th>}
                      {fields.map((field) => (
                        <th key={field.id}>{field.label}</th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {responsesLoading ? (
                      <tr>
                        <td colSpan={fields.length + 2 + (isQuiz ? 1 : 0)}>
                          <div className="results-empty-state">
                            <strong>{t.loadingTitle}</strong>
                            <p>{t.loadingText}</p>
                          </div>
                        </td>
                      </tr>
                    ) : responsesError ? (
                      <tr>
                        <td colSpan={fields.length + 2 + (isQuiz ? 1 : 0)}>
                          <div className="results-empty-state">
                            <strong>{t.errorTitle}</strong>
                            <p>{responsesError}</p>
                          </div>
                        </td>
                      </tr>
                    ) : displayedResponses.length > 0 ? (
                      displayedResponses.map((response) => (
                        <tr key={response.id}>
                          <td>
                            {response.backendSubmission ? (
                              <select
                                className="response-status-select"
                                value={response.status || t.newStatus}
                                disabled={Boolean(statusUpdatingById[response.id])}
                                onChange={(event) => updateSubmissionStatus(response.id, event.target.value)}
                              >
                                {SUBMISSION_STATUSES.map((status) => (
                                  <option key={status} value={status}>
                                    {status}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <span className="status-pill">
                                {response.status || t.newStatus}
                              </span>
                            )}
                          </td>

                          <td>
                            {response.createdAt
                              ? new Date(response.createdAt).toLocaleString()
                              : "-"}
                          </td>

                          {isQuiz && (
                            <td>
                              {response.quiz?.score === null || response.quiz?.score === undefined
                                ? "-"
                                : `${response.quiz.score}%`}
                            </td>
                          )}

                          {fields.map((field) => (
                            <td key={field.id}>
                              {formatSavedValue(response.answers?.[field.id])}
                            </td>
                          ))}
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={fields.length + 2 + (isQuiz ? 1 : 0)}>
                          <div className="results-empty-state">
                            <strong>{responses.length > 0 ? t.filteredEmptyTitle : t.emptyTitle}</strong>
                            <p>{responses.length > 0 ? t.filteredEmptyText : t.emptyText}</p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="results-empty-state large">
              <strong>{t.noForm}</strong>
              <p>{t.noFormText}</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}


