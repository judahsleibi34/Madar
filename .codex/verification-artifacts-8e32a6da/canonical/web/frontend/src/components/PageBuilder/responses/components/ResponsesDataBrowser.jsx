import { useState } from "react";
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
  incompleteView = false,
  resumeUrl = "",
  onOpenSpreadsheet,
  recordMutation = "",
  onUpdateRecord,
  onDeleteRecord,
  showToast,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftAnswers, setDraftAnswers] = useState({});


  const updateDraftValue = (field, event) => {
    const currentValue = selectedResponse?.answers?.[field.id];
    const nextValue = typeof currentValue === "boolean"
      ? event.target.checked
      : event.target.value;
    setDraftAnswers((current) => ({ ...current, [field.id]: nextValue }));
  };

  const saveRecord = async () => {
    const answers = { ...draftAnswers };
    try {
      fields.forEach((field) => {
        const originalValue = selectedResponse?.answers?.[field.id];
        const editedValue = answers[field.id];
        if (typeof originalValue === "number" && editedValue !== "") {
          const parsed = Number(editedValue);
          if (!Number.isFinite(parsed)) throw new Error();
          answers[field.id] = parsed;
        } else if (
          originalValue !== null &&
          typeof originalValue === "object" &&
          typeof editedValue === "string"
        ) {
          answers[field.id] = editedValue.trim() ? JSON.parse(editedValue) : null;
        }
      });
    } catch {
      showToast?.(t.invalidStructuredValue);
      return;
    }

    if (await onUpdateRecord?.(selectedResponse.id, answers)) {
      setIsEditing(false);
    }
  };

  const deleteRecord = async () => {
    if (!window.confirm(t.deleteRecordConfirm)) return;
    await onDeleteRecord?.(selectedResponse.id);
  };

  return (
    <section className="responses-data-browser">
      <div className="responses-list-panel">
        <div className="responses-browser-heading">
          <div>
            <h2>{t.submissionList}</h2>
            <p>{t.submissionListText}</p>
          </div>
          <div className="responses-browser-actions">
            <button
              type="button"
              className="responses-spreadsheet-button"
              onClick={onOpenSpreadsheet}
            >
              {t.reviewInExcel}
            </button>
            <span className="responses-browser-count">{displayedResponses.length}</span>
          </div>
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
                  onClick={() => {
                    setSelectedResponseId(response.id);
                    setDraftAnswers(response.answers || {});
                    setIsEditing(false);
                  }}
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
          {selectedResponse && (
            <div className="responses-record-actions">
              <span className="responses-record-status">
                {selectedResponse.status || t.newStatus}
              </span>
              {!isEditing && (
                <>
                  <button type="button" onClick={() => {
                    setDraftAnswers(selectedResponse.answers || {});
                    setIsEditing(true);
                  }}>
                    {t.editRecord}
                  </button>
                  <button
                    type="button"
                    className="danger"
                    disabled={Boolean(recordMutation)}
                    onClick={deleteRecord}
                  >
                    {recordMutation === "deleting" ? t.deletingRecord : t.deleteRecord}
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {selectedResponse ? (
          <>
            {incompleteView && (
              <div className="responses-resume-action">
                {resumeUrl ? (
                  <a href={resumeUrl} target="_blank" rel="noreferrer">{t.resumeDraft}</a>
                ) : (
                  <span>{t.resumeUnavailable}</span>
                )}
              </div>
            )}
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

            <div className={`responses-answer-grid${isEditing ? " editing" : ""}`}>
              {fields.map((field) => {
                const value = formatSavedValue(selectedResponse.answers?.[field.id]);
                const originalValue = selectedResponse.answers?.[field.id];
                const editorValue = draftAnswers[field.id];

                return (
                  <article key={field.id}>
                    <span>{field.label}</span>
                    {isEditing ? (
                      typeof originalValue === "boolean" ? (
                        <label className="responses-record-checkbox">
                          <input
                            type="checkbox"
                            checked={Boolean(editorValue)}
                            onChange={(event) => updateDraftValue(field, event)}
                          />
                          <span>{editorValue ? t.yes : t.no}</span>
                        </label>
                      ) : (
                        <textarea
                          rows={originalValue && typeof originalValue === "object" ? 4 : 2}
                          value={originalValue && typeof originalValue === "object"
                            ? (typeof editorValue === "string" ? editorValue : JSON.stringify(editorValue, null, 2))
                            : String(editorValue ?? "")}
                          onChange={(event) => updateDraftValue(field, event)}
                        />
                      )
                    ) : (
                      <strong>{value || "-"}</strong>
                    )}
                  </article>
                );
              })}
            </div>
            {isEditing && (
              <div className="responses-record-editor-footer">
                <button type="button" onClick={() => {
                  setDraftAnswers(selectedResponse.answers || {});
                  setIsEditing(false);
                }} disabled={Boolean(recordMutation)}>
                  {t.cancel}
                </button>
                <button type="button" className="primary" onClick={saveRecord} disabled={Boolean(recordMutation)}>
                  {recordMutation === "updating" ? t.savingChanges : t.saveChanges}
                </button>
              </div>
            )}
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
