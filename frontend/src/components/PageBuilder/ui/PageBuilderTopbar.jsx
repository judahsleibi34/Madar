export default function PageBuilderTopbar({
  project,
  displayName,
  activeHelper,
  preview,
  copy,
  onPreviewClick,
}) {
  return (
    <header className="builder-topbar">
      <div className="builder-brand">
        <h1>{displayName || project.name}</h1>
        <p>{activeHelper}</p>
      </div>

      {preview ? (
        <div className="builder-topbar-actions preview-header-actions">
          <button
            type="button"
            className="primary-action preview-header-exit"
            onClick={onPreviewClick}
          >
            {copy?.exitPreview || "Exit preview"}
          </button>
        </div>
      ) : null}
    </header>
  );
}