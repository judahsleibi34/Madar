export default function PageBuilderPageInspector({
  page,
  hasRoutingIssue,
  onSetDefault,
  onUpdate,
}) {
  if (!page) return <p className="builder-note">Select or create a page to edit its settings.</p>;

  return (
    <div className="inspector-group" data-testid="page-inspector">
      <h3>Page Settings</h3>
      <label>
        Page name
        <input value={page.name || ""} onChange={(event) => onUpdate({ name: event.target.value })} />
      </label>
      <label>
        Navigation label
        <input
          value={page.navigationLabel || ""}
          placeholder={page.name || "Page name"}
          onChange={(event) => onUpdate({ navigationLabel: event.target.value })}
        />
      </label>
      <label className="inspector-toggle-row">
        <input
          type="checkbox"
          checked={page.isDefault === true}
          onChange={(event) => onSetDefault(event.target.checked)}
        />
        <span>Use as homepage</span>
      </label>
      {hasRoutingIssue && (
        <p className="builder-note" role="alert">Rename this page to create a valid, unique address.</p>
      )}
      <label className="inspector-toggle-row">
        <input
          type="checkbox"
          checked={page.showInNavigation !== false}
          onChange={(event) => onUpdate({ showInNavigation: event.target.checked })}
        />
        <span>Show this page in the header</span>
      </label>
      <p className="builder-note">Header visibility is controlled here. Footer page links are configured separately.</p>
    </div>
  );
}
