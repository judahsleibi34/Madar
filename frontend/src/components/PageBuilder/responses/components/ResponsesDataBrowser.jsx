export default function ResponsesDataBrowser({
  t,
  fields,
  displayedResponses,
  responses,
  responsesLoading,
  responsesError,
  selectedResponse,
  selectedOffset,
  setSelectedResponseId,
  formatSavedValue,
  isQuiz,
}) {
  return (
    <section className="responses-data-browser">
      <div className="responses-list-panel">
        <div className="responses-browser-heading">
          <div>
            <h2>{t.submissionList}</h2>
            <p>{t.submissionListText}</p>
          </div>
          <span>{displayedResponses.length}</span>
        </div>

        <div className="responses-card-list">
          {responsesLoading ? (
            <div className="responses-card-empty">
              <strong>{t.loadingTitle}</strong>
              <p>{t.loadingText}</p>
            </div>
          ) : responsesError ? (
            <div className="responses-card-empty">
              <strong>{t.errorTitle}</strong>
              <p>{responsesError}</p>
            </div>
          ) : displayedResponses.length > 0 ? (
            displayedResponses.map((response, index) => {
              const primaryField = fields.find((field) => response.answers?.[field.id]);
              const primaryValue = primaryField
                ? formatSavedValue(response.answers?.[primaryField.id])
                : t.noAnswerPreview;

              return (
                <button
                  key={response.id}
                  type="button"
                  className={selectedResponse?.id === response.id ? "active" : ""}
                  onClick={() => setSelectedResponseId(response.id)}
                >
                  <span className="responses-card-index">#{selectedOffset + index + 1}</span>
                  <strong>{primaryValue || t.noAnswerPreview}</strong>
                  <small>
                    {response.createdAt ? new Date(response.createdAt).toLocaleString() : t.noDate}
                  </small>
                  <em>{response.status || t.newStatus}</em>
                </button>
              );
            })
          ) : (
            <div className="responses-card-empty">
              <strong>{responses.length > 0 ? t.filteredEmptyTitle : t.emptyTitle}</strong>
              <p>{responses.length > 0 ? t.filteredEmptyText : t.emptyText}</p>
            </div>
          )}
        </div>
      </div>

      <div className="responses-detail-panel">
        <div className="responses-browser-heading">
          <div>
            <h2>{t.submissionDetails}</h2>
            <p>{t.submissionDetailsText}</p>
          </div>
          {selectedResponse && <span>{selectedResponse.status || t.newStatus}</span>}
        </div>

        {selectedResponse ? (
          <>
            <div className="responses-detail-meta">
              <article>
                <span>{t.created}</span>
                <strong>
                  {selectedResponse.createdAt
                    ? new Date(selectedResponse.createdAt).toLocaleString()
                    : t.noDate}
                </strong>
              </article>
              {isQuiz && (
                <article>
                  <span>{t.score}</span>
                  <strong>
                    {selectedResponse.quiz?.score === null ||
                    selectedResponse.quiz?.score === undefined
                      ? "-"
                      : `${selectedResponse.quiz.score}%`}
                  </strong>
                </article>
              )}
            </div>

            <div className="responses-answer-grid">
              {fields.map((field) => {
                const value = formatSavedValue(selectedResponse.answers?.[field.id]);

                return (
                  <article key={field.id}>
                    <span>{field.label}</span>
                    <strong>{value || "-"}</strong>
                  </article>
                );
              })}
            </div>
          </>
        ) : (
          <div className="responses-card-empty">
            <strong>{t.noSelectedSubmission}</strong>
            <p>{t.noSelectedSubmissionText}</p>
          </div>
        )}
      </div>
    </section>
  );
}
