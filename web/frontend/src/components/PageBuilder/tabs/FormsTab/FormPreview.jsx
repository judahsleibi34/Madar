export default function FormPreview({
  activeForm,
  copy,
  placements,
  renderConnectedForm,
}) {
  return (
    <aside className="forms-live-preview-panel" aria-label="Form preview">
      <div className="forms-live-preview-header">
        <strong>{activeForm.title || copy.labels.untitledForm}</strong>
      </div>
      <div className={`forms-live-preview-page ${placements.length > 0 ? "is-embedded" : ""}`}>
        {renderConnectedForm?.(activeForm.id, { allowInteraction: false })}
      </div>
    </aside>
  );
}
