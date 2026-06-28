export default function PageBuilderSubbar({
  preview,
  hideWorkspaceTabs,
  viewports,
  viewport,
  setViewport,
  renderWorkspaceNavigator,
  copy,
  onPreviewClick,
}) {
  if (!preview && !hideWorkspaceTabs) {
    return (
      <div className="builder-subbar">
        {renderWorkspaceNavigator()}
      </div>
    );
  }

  if (preview) {
    return (
      <>
        <button
          type="button"
          className="preview-floating-exit"
          onClick={onPreviewClick}
        >
          {copy?.exitPreview || "Exit preview"}
        </button>

        <div className="preview-device-toolbar">
          <div className="viewport-switcher">
            {Object.keys(viewports).map((item) => (
              <button
                type="button"
                key={item}
                className={viewport === item ? "active" : ""}
                onClick={() => setViewport(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      </>
    );
  }

  return null;
}
