export default function BuilderResponsesPage({
  project,
  activeForm,
  selectForm,
  getFormFields,
  formatSavedValue,
  showToast,
}) {
  const selectedForm = activeForm || project.forms?.[0];

  const allForms = project.forms || [];

  const totalResponses = allForms.reduce(
    (total, form) => total + (form.responses || []).length,
    0
  );

  const formsWithResponses = allForms.filter(
    (form) => (form.responses || []).length > 0
  ).length;

  const fields = selectedForm ? getFormFields(selectedForm) : [];
  const responses = selectedForm?.responses || [];
  const requiredFields = fields.filter((field) => field.required);
  const optionalFields = Math.max(0, fields.length - requiredFields.length);
  const latestResponse = responses[0];
  const answeredCells = responses.reduce(
    (total, response) =>
      total +
      fields.filter((field) => {
        const value = response.answers?.[field.id];
        return value !== undefined && value !== null && value !== "" && (!Array.isArray(value) || value.length > 0);
      }).length,
    0
  );
  const completionRate =
    responses.length && fields.length
      ? Math.round((answeredCells / (responses.length * fields.length)) * 100)
      : 0;

  const connectedCollection = selectedForm?.connectedCollectionId
    ? project.collections.find(
        (collection) => collection.id === selectedForm.connectedCollectionId
      )
    : null;

  const copyResults = () => {
    if (!selectedForm) return;

    const payload = {
      form: selectedForm.title,
      totalResponses: responses.length,
      exportedAt: new Date().toISOString(),
      responses,
    };

    try {
      navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      showToast("Results copied.");
    } catch {
      console.log(payload);
      showToast("Results printed to console.");
    }
  };

  return (
    <div className="workspace-page responses-results-page">
      <div className="workspace-header responses-results-header">
        <div>
          <span className="workspace-kicker">Form information</span>
          <h2>Form Results</h2>
          <p>
            View each form, its questions, and the answers submitted by users.
          </p>
        </div>

        <div className="responses-header-actions">
          <button type="button" onClick={copyResults}>
            Copy results
          </button>

          <button
            type="button"
            className="primary-action"
            onClick={() => {
              if (selectedForm) selectForm(selectedForm.id);
              window.location.href = "/page-builder";
            }}
          >
            Open builder
          </button>
        </div>
      </div>

      <section className="results-summary-grid">
        <article>
          <span>Forms</span>
          <strong>{allForms.length}</strong>
        </article>

        <article>
          <span>Submissions</span>
          <strong>{totalResponses}</strong>
        </article>

        <article>
          <span>Questions in selected form</span>
          <strong>{fields.length}</strong>
        </article>

        <article>
          <span>Completion</span>
          <strong>{completionRate}%</strong>
        </article>
      </section>

      <div className="results-layout">
        <aside className="results-form-list">
          <div className="results-panel-title">
            <h3>Forms</h3>
            <p>Select a form to inspect its submissions.</p>
          </div>

          <div className="results-form-list-scroll">
            {allForms.map((form) => {
              const isActive = selectedForm?.id === form.id;
              const count = form.responses?.length || 0;
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
                    {count} submission{count === 1 ? "" : "s"} /{" "}
                    {formFields.length} field
                    {formFields.length === 1 ? "" : "s"}
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
                  <span className="workspace-kicker">Selected form</span>
                  <h3>{selectedForm.title}</h3>
                  <p>
                    {connectedCollection
                      ? `Saving to ${connectedCollection.name}`
                      : "Saved as form submissions only"}
                  </p>
                </div>

                <div className="results-count-pill">
                  {responses.length} response{responses.length === 1 ? "" : "s"}
                </div>
              </div>

              <div className="form-info-grid">
                <article>
                  <span>Required questions</span>
                  <strong>{requiredFields.length}</strong>
                </article>
                <article>
                  <span>Optional questions</span>
                  <strong>{optionalFields}</strong>
                </article>
                <article>
                  <span>Forms with data</span>
                  <strong>{formsWithResponses}</strong>
                </article>
                <article>
                  <span>Latest submission</span>
                  <strong>
                    {latestResponse?.createdAt
                      ? new Date(latestResponse.createdAt).toLocaleDateString()
                      : "None"}
                  </strong>
                </article>
              </div>

              <div className="results-table-wrap">
                <table className="results-data-table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Created</th>
                      {fields.map((field) => (
                        <th key={field.id}>{field.label}</th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {responses.length > 0 ? (
                      responses.map((response) => (
                        <tr key={response.id}>
                          <td>
                            <span className="status-pill">
                              {response.status || "New"}
                            </span>
                          </td>

                          <td>
                            {response.createdAt
                              ? new Date(response.createdAt).toLocaleString()
                              : "-"}
                          </td>

                          {fields.map((field) => (
                            <td key={field.id}>
                              {formatSavedValue(response.answers?.[field.id])}
                            </td>
                          ))}
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={fields.length + 2}>
                          <div className="results-empty-state">
                            <strong>No submissions yet</strong>
                            <p>
                              When users submit this form, their answers will
                              appear here as rows in this table.
                            </p>
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
              <strong>No form selected</strong>
              <p>Create a form first, then submitted answers will appear here.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}


