import Field from './Field';

export default function DataSourceStep({
  sourceMode,
  setSourceMode,
  availableForms,
  selectedForm,
  setSelectedFormId,
  selectedFile,
  setSelectedFile,
  externalUrl,
  setExternalUrl,
  importFormResponses,
  uploadFile,
  loadExternalSource,
  selectForm,
  setActiveTab,
  isLoading,
  t,
}) {
  return (
    <section className="daw-card daw-section-card">
      <div className="daw-section-heading">
        <span>{t.source}</span>
        <h3>{t.sourceTitle}</h3>
        <p>{t.sourceSubtitle}</p>
      </div>

      <div className="daw-source-tabs">
        <button
          type="button"
          className={sourceMode === "forms" ? "active" : ""}
          onClick={() => setSourceMode("forms")}
        >
          {t.forms}
        </button>

        <button
          type="button"
          className={sourceMode === "upload" ? "active" : ""}
          onClick={() => setSourceMode("upload")}
        >
          {t.upload}
        </button>

        <button
          type="button"
          className={sourceMode === "external" ? "active" : ""}
          onClick={() => setSourceMode("external")}
        >
          {t.external}
        </button>
      </div>

      {sourceMode === "forms" ? (
        <div className="daw-source-body">
          <div>
            <h4>{t.fromWebsite}</h4>
            <p>{t.fromWebsiteHint}</p>
          </div>

          <Field label={t.form}>
            <select
              value={selectedForm?.id || ""}
              onChange={(event) => setSelectedFormId(event.target.value)}
            >
              {availableForms.map((form) => (
                <option key={form.id} value={form.id}>
                  {form.title} ({form.responses?.length || 0} {t.responses})
                </option>
              ))}
            </select>
          </Field>

          <div className="daw-button-row">
            <button
              type="button"
              className="daw-primary"
              disabled={isLoading || !selectedForm}
              onClick={importFormResponses}
            >
              {isLoading ? t.working : t.importResponses}
            </button>

            <button
              type="button"
              onClick={() => {
                if (selectedForm) selectForm?.(selectedForm.id);
                setActiveTab?.("responses");
              }}
            >
              {t.viewResponses}
            </button>
          </div>
        </div>
      ) : sourceMode === "upload" ? (
        <div className="daw-source-body">
          <div>
            <h4>{t.uploadTitle}</h4>
            <p>{t.uploadHint}</p>
          </div>

          <label
            className="daw-file-dropzone"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              setSelectedFile(event.dataTransfer.files?.[0] || null);
            }}
          >
            <input
              type="file"
              accept=".csv,.xls,.xlsx"
              onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
            />

            <strong>{selectedFile ? selectedFile.name : t.chooseFile}</strong>
            <span>{selectedFile ? t.readyToLoad : t.uploadHint}</span>
          </label>

          <div className="daw-button-row">
            <button
              type="button"
              className="daw-primary"
              disabled={isLoading || !selectedFile}
              onClick={() => uploadFile(selectedFile)}
            >
              {isLoading ? t.working : t.loadFile}
            </button>
          </div>
        </div>
      ) : (
        <div className="daw-source-body">
          <div>
            <h4>{t.externalTitle}</h4>
            <p>{t.externalHint}</p>
          </div>

          <Field label={t.dataLink}>
            <input
              type="url"
              value={externalUrl}
              placeholder="https://example.com/data.csv"
              onChange={(event) => setExternalUrl(event.target.value)}
            />
            <small>{t.sheetsNote}</small>
          </Field>

          <div className="daw-button-row">
            <button
              type="button"
              className="daw-primary"
              disabled={isLoading || !externalUrl.trim()}
              onClick={loadExternalSource}
            >
              {isLoading ? t.working : t.loadLink}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
