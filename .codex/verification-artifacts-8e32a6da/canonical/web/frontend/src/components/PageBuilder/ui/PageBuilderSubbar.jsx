export default function PageBuilderSubbar({
  preview,
  hideWorkspaceTabs,
  historyControls,
  viewports,
  viewport,
  setViewport,
  renderWorkspaceNavigator,
  artboardCameraControls,
}) {
  if (!preview && !hideWorkspaceTabs) {
    return (
      <div className="builder-subbar">
        <div className="builder-subbar-inner">
          {renderWorkspaceNavigator()}
          <div className="builder-subbar-actions">
            {historyControls}
            {artboardCameraControls}
          </div>
        </div>
      </div>
    );
  }

  if (preview) {
    return (
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
    );
  }

  return null;
}