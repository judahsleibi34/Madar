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

  const copyResults = () => {
    if (!data.selectedForm) return;

    const payload = {
      form: data.selectedForm.title,
      totalResponses: data.displayedResponses.length,
      selectedStatuses: data.selectedStatuses,
      selectedFields: data.selectedFieldIds,
      exportedAt: new Date().toISOString(),
      responses: data.displayedResponses,
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
      <ResponsesHeader
        t={t}
        selectedForm={data.selectedForm}
        selectForm={selectForm}
        copyResults={copyResults}
      />

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
          clearSelectedFields={data.clearSelectedFields}
          dynamicStatusOptions={data.dynamicStatusOptions}
          selectedStatusSet={data.selectedStatusSet}
          toggleSelectedStatus={data.toggleSelectedStatus}
          clearSelectedStatuses={data.clearSelectedStatuses}
          clearFilters={data.clearFilters}
          hasFilters={data.hasFilters}
        />

        <main className="results-table-card">
          {data.selectedForm ? (
            <>
              <div className="results-table-header">
                <div>
                  <span className="workspace-kicker">{t.selectedForm}</span>
                  <h3>{data.selectedForm.title}</h3>
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
