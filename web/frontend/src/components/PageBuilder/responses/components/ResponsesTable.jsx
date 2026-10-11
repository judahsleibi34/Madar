import { SUBMISSION_STATUSES } from "../constants";

export default function ResponsesTable({
  t,
  fields,
  displayedResponses,
  responses,
  responsesLoading,
  responsesError,
  selectedResponse,
  setSelectedResponseId,
  statusUpdatingById,
  updateSubmissionStatus,
  formatSavedValue,
  isQuiz,
  incompleteView = false,
  caption,
  renderAnswer,
  extraHeaders = [],
  renderExtraCells,
  trailingHeaders = [],
  renderTrailingCells,
}) {
  const columnCount = fields.length + extraHeaders.length + trailingHeaders.length + 3 + (isQuiz ? 1 : 0);

  return (
    <div className="results-table-wrap">
      <table className="results-data-table">
        {caption && <caption>{caption}</caption>}
        <thead>
          <tr>
            <th>{t.reviewStatus}</th>
            <th>{t.created}</th>
            <th>{t.submittedBy}</th>
            {isQuiz && <th>{t.score}</th>}
            {extraHeaders.map(label => <th key={label}>{label}</th>)}
            {fields.map((field) => (
              <th key={field.id}>{field.label}</th>
            ))}
            {trailingHeaders.map(label => <th key={label}>{label}</th>)}
          </tr>
        </thead>

        <tbody>
          {responsesLoading ? (
            <tr>
              <td colSpan={columnCount}>
                <div className="results-empty-state">
                  <strong>{t.loadingTitle}</strong>
                  <p>{t.loadingText}</p>
                </div>
              </td>
            </tr>
          ) : responsesError ? (
            <tr>
              <td colSpan={columnCount}>
                <div className="results-empty-state">
                  <strong>{t.errorTitle}</strong>
                  <p>{responsesError}</p>
                </div>
              </td>
            </tr>
          ) : displayedResponses.length > 0 ? (
            displayedResponses.map((response) => (
              <tr
                key={response.id}
                className={selectedResponse?.id === response.id ? "selected" : ""}
                onClick={() => setSelectedResponseId(response.id)}
              >
                <td>
                  {response.backendSubmission && !incompleteView ? (
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
                    <span className="status-pill">{response.status || t.newStatus}</span>
                  )}
                </td>

                <td>{response.createdAt ? new Date(response.createdAt).toLocaleString() : "-"}</td>
                <td>
                  <span className="response-submitter">
                    <strong>{response.submittedBy?.name || t.guestSubmitter}</strong>
                    {response.submittedBy?.email ? <small>{response.submittedBy.email}</small> : null}
                    <small>{response.submittedBy?.role || t.guestRole}</small>
                  </span>
                </td>
                {isQuiz && (
                  <td>
                    {response.quiz?.score === null || response.quiz?.score === undefined
                      ? "-"
                      : `${response.quiz.score}%`}
                  </td>
                )}

                {renderExtraCells?.(response)}
                {fields.map((field) => (
                  <td key={field.id}>{renderAnswer ? renderAnswer(field, response.answers?.[field.id], response) : formatSavedValue(response.answers?.[field.id])}</td>
                ))}
                {renderTrailingCells?.(response)}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={columnCount}>
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
  );
}
