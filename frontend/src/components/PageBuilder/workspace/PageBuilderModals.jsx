import PageDeleteConfirmModal from "../modals/PageDeleteConfirmModal";

export default function PageBuilderModals({
  activeTab,
  applyStarter,
  closeStarterModal,
  confirmDeletePendingUser,
  confirmDeleteSelectedElement,
  elementPendingDelete,
  getStarterDisplay,
  modal,
  previewOverlapWarnings,
  setElementPendingDelete,
  setPreviewOverlapWarnings,
  setUserPendingDelete,
  starterSystems,
  templateCopy,
  templateLang,
  userPendingDelete,
}) {
  return (
    <>
      {elementPendingDelete && (
        <PageDeleteConfirmModal
          title="Delete this element?"
          message={
            <>
              <strong>"{elementPendingDelete.name}"</strong> will be removed from the page. This cannot be undone.
            </>
          }
          cancelLabel="Keep element"
          confirmLabel="Delete element"
          onCancel={() => setElementPendingDelete(null)}
          onConfirm={confirmDeleteSelectedElement}
        />
      )}

      {userPendingDelete && (
        <PageDeleteConfirmModal
          title="Delete this user?"
          message={
            <>
              <strong>"{userPendingDelete.name || userPendingDelete.email}"</strong> will be removed from this builder project. This cannot be undone.
            </>
          }
          cancelLabel="Keep user"
          confirmLabel="Delete user"
          onCancel={() => setUserPendingDelete(null)}
          onConfirm={confirmDeletePendingUser}
        />
      )}

      {previewOverlapWarnings.length > 0 && (
        <div
          className="builder-modal-backdrop"
          onClick={() => setPreviewOverlapWarnings([])}
        >
          <section
            className="builder-modal overlap-warning-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="overlap-warning-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <span className="modal-eyebrow">Layout check</span>
                <h2 id="overlap-warning-title">
                  Almost ready to preview
                </h2>
                <p>
                  I found {previewOverlapWarnings.length} place
                  {previewOverlapWarnings.length === 1 ? "" : "s"} where elements are sitting on top of each other. Move one of them a little, then preview again.
                </p>
              </div>
              <button type="button" onClick={() => setPreviewOverlapWarnings([])}>
                Close
              </button>
            </div>

            <div className="overlap-warning-list">
              {previewOverlapWarnings.slice(0, 5).map((warning, index) => (
                <article
                  className="overlap-warning-item"
                  key={`${warning.page}_${warning.section}_${warning.viewport}_${warning.first}_${warning.second}_${index}`}
                >
                  <div className="overlap-warning-item-top">
                    <span>{warning.viewport}</span>
                    <small>{warning.page} / {warning.section}</small>
                  </div>
                  <strong>{warning.first} is covering {warning.second}</strong>
                  <p>Move or resize one of these components so both are readable.</p>
                </article>
              ))}
            </div>

            {previewOverlapWarnings.length > 5 && (
              <p className="overlap-warning-more">
                Plus {previewOverlapWarnings.length - 5} more overlap
                {previewOverlapWarnings.length - 5 === 1 ? "" : "s"}.
              </p>
            )}

            <div className="overlap-warning-actions">
              <button type="button" onClick={() => setPreviewOverlapWarnings([])}>
                Fix layout
              </button>
            </div>
          </section>
        </div>
      )}

      {modal === "starter" && activeTab === "design" && (
        <div className="builder-modal-backdrop" onClick={closeStarterModal}>
          <div
            className="builder-modal wide template-picker-modal"
            dir={templateLang === "ar" ? "rtl" : "ltr"}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <span className="modal-eyebrow">{templateCopy.eyebrow}</span>
                <h2>{templateCopy.title}</h2>
                <p>{templateCopy.description}</p>
              </div>
              <button type="button" onClick={closeStarterModal}>{templateCopy.close}</button>
            </div>
            <div className="starter-grid">
              {starterSystems.map((starter) => {
                const displayStarter = getStarterDisplay(starter);

                return (
                  <button type="button" className="starter-card" key={starter.id} onClick={() => applyStarter(starter.id)}>
                    {displayStarter.category && <span>{displayStarter.category}</span>}
                    <strong>{displayStarter.title}</strong>
                    <p>{displayStarter.subtitle}</p>
                    {Array.isArray(displayStarter.tags) && displayStarter.tags.length > 0 && (
                      <em>
                        {displayStarter.tags.map((tag) => (
                          <i key={tag}>{tag}</i>
                        ))}
                      </em>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
