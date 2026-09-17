export default function PageBuilderTopbar({
  project,
  displayName,
  activeHelper,
  activeTab,
  preview,
  copy,
  onPreviewClick,
}) {
  const hasNestedPageTitle = ["responses", "data", "reservations"].includes(activeTab);
  const ProjectTitle = hasNestedPageTitle ? "span" : "h1";

  return (
    <header className="builder-topbar">
      <div className="builder-brand">
        <ProjectTitle className={hasNestedPageTitle ? "builder-brand-name" : undefined}>
          {displayName || project.name}
        </ProjectTitle>
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