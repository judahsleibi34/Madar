export default function PageBuilderTopbar({
  project,
  activeHelper,
  hideWorkspaceTabs,
  preview,
  demoMode,
  activeTopbarAction,
  setActiveTopbarAction,
  setModal,
  setPreview,
  saveProject,
  publishProject,
}) {
  return (
    <header className="builder-topbar">
      <div className="builder-brand">
        <h1>{project.name}</h1>
        <p>{activeHelper}</p>
      </div>

      {!hideWorkspaceTabs && (
        <div className="builder-topbar-actions">
          <button
            type="button"
            className={activeTopbarAction === "templates" ? "action-active" : ""}
            onClick={() => {
              setActiveTopbarAction("templates");
              setModal("starter");
            }}
          >
            Templates
          </button>

          <button
            type="button"
            className={activeTopbarAction === "preview" ? "action-active" : ""}
            onClick={() => {
              setActiveTopbarAction("preview");
              setPreview((value) => !value);
            }}
          >
            {preview ? "Exit Preview" : "Preview"}
          </button>

          {!demoMode && (
            <>
              <button
                type="button"
                className={activeTopbarAction === "save" ? "action-active" : ""}
                onClick={saveProject}
              >
                Save
              </button>

              <button
                type="button"
                className={`primary-action go-live-action ${
                  activeTopbarAction === "publish" ? "action-active" : ""
                }`}
                onClick={publishProject}
              >
                Go Live
              </button>
            </>
          )}
        </div>
      )}
    </header>
  );
}
