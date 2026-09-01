import PageDeleteConfirmModal from "../modals/PageDeleteConfirmModal";
import { AlertTriangle, Rocket } from "lucide-react";

export default function PageBuilderModals({
  activeTab,
  applyStarter,
  confirmDeletePendingPage,
  closeStarterModal,
  confirmDeletePendingUser,
  confirmDeleteSelectedElement,
  elementPendingDelete,
  getStarterDisplay,
  modal,
  pagePendingDelete,
  previewOverlapWarnings,
  publishOverlapWarnings,
  confirmPublishWithOverlaps,
  setElementPendingDelete,
  setPagePendingDelete,
  setPreviewOverlapWarnings,
  setPublishOverlapWarnings,
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
          title="Remove website access?"
          message={
            <>
              <strong>"{userPendingDelete.name || userPendingDelete.email}"</strong> will no longer be able to sign in to this subdomain. Their global account will not be deleted.
            </>
          }
          cancelLabel="Keep user"
          confirmLabel="Remove access"
          onCancel={() => setUserPendingDelete(null)}
          onConfirm={confirmDeletePendingUser}
        />
      )}

      {pagePendingDelete && (
        <PageDeleteConfirmModal
          title="Delete this page?"
          message={
            <>
              <strong>"{pagePendingDelete.name}"</strong> and its blocks will be removed from this builder project. Other pages will stay.
            </>
          }
          cancelLabel="Keep page"
          confirmLabel="Delete page"
          onCancel={() => setPagePendingDelete(null)}
          onConfirm={confirmDeletePendingPage}
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

      {publishOverlapWarnings.length > 0 && (
        <div
          className="builder-modal-backdrop"
          onClick={() => setPublishOverlapWarnings([])}
        >
          <section
            className="builder-modal overlap-warning-modal publish-overlap-modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="publish-overlap-warning-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div className="publish-overlap-icon" aria-hidden="true">
                <AlertTriangle size={24} />
              </div>
              <div>
                <h2 id="publish-overlap-warning-title">Check your layout before going live</h2>
                <p>
                  {publishOverlapWarnings.length} area{publishOverlapWarnings.length === 1 ? "" : "s"} may be hard to read. You can fix the layout now or publish it as it is.
                </p>
              </div>
              <button
                type="button"
                className="publish-overlap-close"
                aria-label="Close"
                onClick={() => setPublishOverlapWarnings([])}
              >
                ×
              </button>
            </div>

            <div className="overlap-warning-list">
              {publishOverlapWarnings.slice(0, 5).map((warning, index) => (
                <article
                  className="overlap-warning-item"
                  key={`${warning.page}_${warning.section}_${warning.viewport}_${warning.first}_${warning.second}_${index}`}
                >
                  <div className="overlap-warning-item-top">
                    <span>{warning.viewport}</span>
                    <small>{warning.page} / {warning.section}</small>
                  </div>
                  <strong>{warning.first} overlaps {warning.second}</strong>
                  <p>Move or resize either item so both are easy to read.</p>
                </article>
              ))}
            </div>

            {publishOverlapWarnings.length > 5 && (
              <p className="overlap-warning-more">
                Plus {publishOverlapWarnings.length - 5} more overlap
                {publishOverlapWarnings.length - 5 === 1 ? "" : "s"}.
              </p>
            )}

            <div className="overlap-warning-actions">
              <button type="button" className="publish-overlap-fix" onClick={() => setPublishOverlapWarnings([])}>
                Fix layout
              </button>
              <button type="button" className="publish-overlap-live" onClick={confirmPublishWithOverlaps}>
                <Rocket size={16} aria-hidden="true" />
                Go Live as is
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
