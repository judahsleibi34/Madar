export default function PageBuilderPageInspector({
  page,
  hasRoutingIssue,
  loadingImagePreviewUrl,
  hasCustomLoadingImage,
  assetUploadBusy,
  onLoadingImageUpload,
  onResetLoadingImage,
  onSetDefault,
  onUpdate,
}) {
  if (!page) return <p className="builder-note">Select or create a page to edit its settings.</p>;

  return (
    <>
      <div className="inspector-group" data-testid="page-inspector">
        <h3>Page Settings</h3>
        <label>
          Page name
          <input
            value={page.name || ""}
            onChange={(event) => onUpdate({ name: event.target.value })}
            onBlur={(event) => onUpdate({ name: event.target.value.trim() || "Untitled page" })}
          />
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

      <div className="inspector-group loading-screen-inspector" data-testid="loading-screen-inspector">
        <h3>Loading Screen</h3>
        <p className="builder-note">Shown while the published site is loading. This setting applies to every page.</p>
        <div className="loading-image-preview" aria-label="Loading image preview">
          {loadingImagePreviewUrl ? (
            <img src={loadingImagePreviewUrl} alt="Current loading screen" />
          ) : (
            <span aria-hidden="true">No image</span>
          )}
        </div>
        <div className="loading-image-actions">
          <label className="upload-image-button">
            {assetUploadBusy ? "Uploading..." : hasCustomLoadingImage ? "Replace image" : "Choose image"}
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              disabled={assetUploadBusy}
              onChange={onLoadingImageUpload}
            />
          </label>
          {hasCustomLoadingImage && (
            <button type="button" className="danger-lite" disabled={assetUploadBusy} onClick={onResetLoadingImage}>
              Use site logo
            </button>
          )}
        </div>
        <p className="builder-note">PNG, JPG, or WebP up to 5 MB. If unset, the site logo is used.</p>
      </div>
    </>
  );
}