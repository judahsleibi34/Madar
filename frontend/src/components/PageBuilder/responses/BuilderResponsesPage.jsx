import { useState } from "react";
import { getResponsesContent } from "../../../content/pageBuilder";
import ResponsesDataBrowser from "./components/ResponsesDataBrowser";
import ResponsesHeader from "./components/ResponsesHeader";
import ResponsesSidebar from "./components/ResponsesSidebar";
import ResponsesSummary from "./components/ResponsesSummary";
import ResponsesTable from "./components/ResponsesTable";
import { useBuilderResponsesData } from "./hooks/useBuilderResponsesData";

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
  });
  const isQuiz = data.selectedForm?.mode === "quiz";
  const connectedCollection = data.selectedForm?.connectedCollectionId
    ? project.collections?.find(
        (collection) => collection.id === data.selectedForm.connectedCollectionId
      )
    : null;
  const activeFieldFilters = data.selectedFieldIds?.length || 0;
  const activeStatusFilters = data.selectedStatuses?.length || 0;

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
          {data.selectedForm ? (
            <>
              <div className="results-table-header">
                <div>
                  <span className="workspace-kicker">{t.selectedForm}</span>
                  <h2>{data.selectedForm.title}</h2>
                  <p>
                    {connectedCollection
                      ? `${t.savingTo} ${connectedCollection.name}`
                      : t.savedOnly}
                  </p>
                </div>

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
              </div>

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
              />

              <ResponsesTable
                t={t}
                fields={data.fields}
                displayedResponses={data.displayedResponses}
                responses={data.responses}
                responsesLoading={data.responsesLoading}
                responsesError={data.responsesError}
                selectedResponse={data.selectedResponse}
                setSelectedResponseId={data.setSelectedResponseId}
                statusUpdatingById={data.statusUpdatingById}
                updateSubmissionStatus={data.updateSubmissionStatus}
                formatSavedValue={formatSavedValue}
                isQuiz={isQuiz}
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
