import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getResponsesContent } from "../../../content/pageBuilder";
import ResponsesDataBrowser from "./components/ResponsesDataBrowser";
import ResponsesHeader from "./components/ResponsesHeader";
import ResponsesSidebar from "./components/ResponsesSidebar";
import ResponsesSummary from "./components/ResponsesSummary";
import ResponsesTable from "./components/ResponsesTable";
import ResponsesToolbar from "./components/ResponsesToolbar";
import { useBuilderResponsesData } from "./hooks/useBuilderResponsesData";
import { openResponsesSpreadsheetTab } from "./utils/openResponsesSpreadsheetTab";
import {
  getResponseView,
  getResponseViewPath,
  hasResponseViewPath,
} from "./utils/responsesViewRouting";
import "../../../styles/admin/PageBuilder/incomplete-drafts.css";
import "../../../styles/admin/PageBuilder/responses-spreadsheet-actions.css";
import "../../../styles/admin/PageBuilder/response-record-actions.css";
import "../../../styles/admin/PageBuilder/responses-settings-menu.css";
export default function BuilderResponsesPage({
  lang = "en",
  user = null,
  project,
  builderProjectId = "",
  activeForm,
  selectForm,
  getFormFields,
  updateActiveForm,
  formatSavedValue,
  showToast,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const responseView = getResponseView(location.pathname, location.search);

  const setResponseView = (nextView) => {
    navigate(getResponseViewPath(location.pathname, nextView));
  };

  useEffect(() => {
    if (!hasResponseViewPath(location.pathname)) {
      navigate(getResponseViewPath(location.pathname, responseView), { replace: true });
    }
  }, [location.pathname, navigate, responseView]);
  const [assistantQuestion, setAssistantQuestion] = useState("");
  const [assistantReply, setAssistantReply] = useState("");
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = getResponsesContent(activeLang);
  const data = useBuilderResponsesData({
    project,
    builderProjectId,
    activeForm,
    getFormFields,
    formatSavedValue,
    showToast,
    user,
    t,
    responseView: responseView === "incomplete" ? "incomplete" : "completed",
  });
  const isQuiz = data.selectedForm?.mode === "quiz";
  const connectedCollection = data.selectedForm?.connectedCollectionId
    ? project.collections?.find(
        (collection) => collection.id === data.selectedForm.connectedCollectionId
      )
    : null;
  const activeFieldFilters = data.selectedFieldIds?.length || 0;
  const activeStatusFilters = data.selectedStatuses?.length || 0;
  const resumeSubdomain = project?.publish?.subdomain || "";
  const resumeUrl = responseView === "incomplete" && data.selectedResponse?.resumeToken && resumeSubdomain
    ? `/forms/${encodeURIComponent(resumeSubdomain)}/${encodeURIComponent(data.selectedFormId)}?resume=${encodeURIComponent(data.selectedResponse.resumeToken)}`
    : "";

  const openSpreadsheetPreview = () => {
    if (!data.selectedForm) {
      showToast?.(t.noForm);
      return;
    }

    const opened = openResponsesSpreadsheetTab({
      form: data.selectedForm,
      fields: data.fields,
      responses: data.displayedResponses,
      formatSavedValue,
      isQuiz,
      labels: t,
    });

    if (!opened) {
      showToast?.(t.spreadsheetPopupBlocked);
    }
  };

  const runResponseAssistant = () => {
    if (!data.selectedForm) {
      setAssistantReply(t.assistantEmpty);
      return;
    }

    if (data.responses.length === 0) {
      setAssistantReply(t.assistantNoResponses);
      return;
    }

    const newestAnswer = data.latestResponse?.createdAt
      ? new Date(data.latestResponse.createdAt).toLocaleDateString()
      : t.none;
    const filterSummary = data.hasFilters
      ? `${activeFieldFilters} field filters, ${activeStatusFilters} status filters`
      : t.none;

    setAssistantReply(
      `${data.selectedForm.title}: ${data.displayedResponses.length} ${t.matches} from ${data.responses.length} ${t.submissionsLower}. ${t.completion}: ${data.completionRate}%. ${t.latest}: ${newestAnswer}. ${t.searchIn}: ${filterSummary}.`
    );
  };

  return (
    <div className="workspace-page responses-results-page" dir={isArabic ? "rtl" : "ltr"}>
      <ResponsesHeader t={t} />

      <ResponsesSummary
        t={t}
        allForms={data.allForms}
        totalResponses={data.totalResponses}
        fields={data.fields}
        completionRate={data.completionRate}
      />

      <div className="results-layout">
        <ResponsesSidebar
          t={t}
          allForms={data.allForms}
          selectedForm={data.selectedForm}
          selectForm={selectForm}
          getDisplayResponsesForForm={data.getDisplayResponsesForForm}
          getFormFields={getFormFields}
          searchQuery={data.searchQuery}
          setSearchQuery={data.setSearchQuery}
          fields={data.fields}
          selectedFieldSet={data.selectedFieldSet}
          toggleSelectedField={data.toggleSelectedField}
          dynamicStatusOptions={data.dynamicStatusOptions}
          selectedStatusSet={data.selectedStatusSet}
          toggleSelectedStatus={data.toggleSelectedStatus}
          clearFilters={data.clearFilters}
          hasFilters={data.hasFilters}
        />

        <main className="results-table-card">
          {responseView === "__legacy" && <section
            className="responses-workspace-toolbar"
            aria-labelledby="responses-settings-title"
          >
            {data.selectedForm ? (
              <div className="responses-workspace-title">
                <h2 id="responses-settings-title">{t.responseViews}</h2>
                <p>
                  {data.selectedForm.title} · {connectedCollection
                    ? `${t.savingTo} ${connectedCollection.name}`
                    : t.savedOnly}
                </p>
              </div>
            ) : (
              <div aria-hidden="true" />
            )}

            <div className="responses-view-tabs" role="tablist" aria-label={t.responseViews}>
            <button
              type="button"
              role="tab"
              aria-selected={responseView === "completed"}
              tabIndex={responseView === "completed" ? 0 : -1}
              className={responseView === "completed" ? "active" : ""}
              onClick={() => setResponseView("completed")}
            >
              {t.completedTab}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={responseView === "incomplete"}
              tabIndex={responseView === "incomplete" ? 0 : -1}
              className={responseView === "incomplete" ? "active" : ""}
              onClick={() => setResponseView("incomplete")}
            >
              {t.incompleteTab}
            </button>
            </div>

            {data.selectedForm ? (
                <div className="responses-table-controls">
                  {data.hasBackendPagination && (
                    <div className="responses-pagination-controls">
                      <button
                        type="button"
                        onClick={() => data.setSelectedPage(data.selectedPage - 1)}
                        disabled={!data.hasPreviousPage || data.responsesLoading}
                      >
                        {t.previous}
                      </button>
                      <span>
                        {t.page} {data.selectedPage + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => data.setSelectedPage(data.selectedPage + 1)}
                        disabled={!data.hasNextPage || data.responsesLoading}
                      >
                        {t.next}
                      </button>
                    </div>
                  )}

                  {data.hasBackendPagination && (
                    <button
                      type="button"
                      className="responses-refresh-button"
                      onClick={data.refreshResponses}
                      disabled={data.responsesLoading}
                    >
                      {data.responsesLoading ? t.refreshing : t.refresh}
                    </button>
                  )}

                  <div className="results-count-pill">
                    {data.displayedResponses.length}{" "}
                    {data.displayedResponses.length === 1 ? t.match : t.matches}
                  </div>
                </div>
            ) : (
              <div aria-hidden="true" />
            )}
          </section>}

          <ResponsesToolbar
            t={t}
            responseView={responseView}
            setResponseView={setResponseView}
            data={data}
            updateActiveForm={updateActiveForm}
            showToast={showToast}
          />

          {data.selectedForm ? (
              <>
              <div className="form-info-grid">
                <article>
                  <span>{t.required}</span>
                  <strong>{data.requiredFields.length}</strong>
                </article>
                <article>
                  <span>{t.optional}</span>
                  <strong>{data.optionalFields}</strong>
                </article>
                <article>
                  <span>{t.formsWithData}</span>
                  <strong>{data.formsWithResponses}</strong>
                </article>
                <article>
                  <span>{t.latest}</span>
                  <strong>
                    {data.latestResponse?.createdAt
                      ? new Date(data.latestResponse.createdAt).toLocaleDateString()
                      : t.none}
                  </strong>
                </article>
              </div>

              <ResponsesDataBrowser
                t={t}
                fields={data.fields}
                displayedResponses={data.displayedResponses}
                responses={data.responses}
                responsesLoading={data.responsesLoading}
                responsesError={data.responsesError}
                selectedResponse={data.selectedResponse}
                selectedOffset={data.selectedOffset}
                setSelectedResponseId={data.setSelectedResponseId}
                formatSavedValue={formatSavedValue}
                isQuiz={isQuiz}
                incompleteView={responseView === "incomplete"}
                resumeUrl={resumeUrl}
                onOpenSpreadsheet={openSpreadsheetPreview}
                recordMutation={data.recordMutatingById[data.selectedResponse?.id] || ""}
                onUpdateRecord={data.updateResponseRecord}
                onDeleteRecord={data.deleteResponseRecord}
                showToast={showToast}
              />

              <ResponsesTable
                t={t}
                fields={data.fields}
                displayedResponses={data.displayedResponses}
                recordMutation={data.recordMutatingById[data.selectedResponse?.id] || ""}
                onUpdateRecord={data.updateResponseRecord}
                onDeleteRecord={data.deleteResponseRecord}
                showToast={showToast}
                responses={data.responses}
                responsesLoading={data.responsesLoading}
                responsesError={data.responsesError}
                selectedResponse={data.selectedResponse}
                setSelectedResponseId={data.setSelectedResponseId}
                statusUpdatingById={data.statusUpdatingById}
                updateSubmissionStatus={data.updateSubmissionStatus}
                formatSavedValue={formatSavedValue}
                isQuiz={isQuiz}
                incompleteView={responseView === "incomplete"}
              />

              <section className="responses-assistant-panel daw-card daw-assistant-card">
                <div className="daw-section-heading">
                  <span>{t.assistantKicker}</span>
                  <h2>{t.assistantTitle}</h2>
                  <p>{t.assistantText}</p>
                </div>

                <div className="responses-assistant-chat">
                  <label>
                    <span>{t.assistantKicker}</span>
                    <textarea
                      rows={3}
                      value={assistantQuestion}
                      placeholder={t.assistantPlaceholder}
                      onChange={(event) => setAssistantQuestion(event.target.value)}
                      onKeyDown={(event) => {
                        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                          runResponseAssistant();
                        }
                      }}
                    />
                  </label>
                  <button
                    type="button"
                    className="daw-primary"
                    onClick={runResponseAssistant}
                    disabled={!data.selectedForm}
                  >
                    {t.assistantAsk}
                  </button>
                </div>

                {assistantReply ? (
                  <div className="responses-assistant-reply" aria-live="polite">
                    {assistantReply}
                  </div>
                ) : null}
              </section>
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
