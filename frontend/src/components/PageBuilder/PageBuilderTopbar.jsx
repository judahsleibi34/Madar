export default function PageBuilderTopbar({
  project,
  displayName,
  activeHelper,
  hideWorkspaceTabs,
  preview,
  demoMode,
  copy = {},
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
        <h1>{displayName || project.name}</h1>
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
            {copy.templates || "Templates"}
          </button>

          <button
            type="button"
            className={activeTopbarAction === "preview" ? "action-active" : ""}
            onClick={() => {
              setActiveTopbarAction("preview");
              setPreview((value) => !value);
            }}
          >
            {preview ? copy.exitPreview || "Exit Preview" : copy.preview || "Preview"}
          </button>

          {!demoMode && (
            <>
              <button
                type="button"
                className={activeTopbarAction === "save" ? "action-active" : ""}
                onClick={saveProject}
              >
                {copy.save || "Save"}
              </button>

              <button
                type="button"
                className={`primary-action go-live-action ${
                  activeTopbarAction === "publish" ? "action-active" : ""
                }`}
                onClick={publishProject}
              >
                {copy.goLive || "Go Live"}
              </button>
            </>
          )}
        </div>
      )}
    </header>
  );
}
