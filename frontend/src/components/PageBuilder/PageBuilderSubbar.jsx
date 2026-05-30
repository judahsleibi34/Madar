export default function PageBuilderSubbar({
  preview,
  hideWorkspaceTabs,
  viewports,
  viewport,
  setViewport,
  renderWorkspaceNavigator,
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
