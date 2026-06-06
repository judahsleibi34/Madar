export default function PageBuilderPublishTab({
  project,
  saveProject,
  loadProject,
  exportProject,
  publishProject,
}) {
  return (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Publish</h2>
          <p>Save and publish this project through the backend. A local cache is kept for recovery.</p>
        </div>
      </div>

      <div className="publish-grid">
        <section className="publish-card">
          <h3>Status</h3>
          <p>
            Project: <strong>{project.name}</strong>
          </p>
          <p>
            State: <strong>{project.status}</strong>
          </p>
          <p>
            Last saved:{" "}
            <strong>{project.publish?.lastSavedAt || "Not saved yet"}</strong>
          </p>
          <p>
            Last published:{" "}
            <strong>{project.publish?.lastPublishedAt || "Not published yet"}</strong>
          </p>
        </section>

        <section className="publish-card">
          <h3>Actions</h3>

          <div className="publish-actions">
            <button type="button" onClick={saveProject}>
              Save
            </button>

            <button type="button" onClick={loadProject}>
              Load project
            </button>

            <button type="button" onClick={exportProject}>
              Copy JSON export
            </button>

            <button
              type="button"
              className="primary-action go-live-action"
              onClick={publishProject}
            >
              Go Live
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}