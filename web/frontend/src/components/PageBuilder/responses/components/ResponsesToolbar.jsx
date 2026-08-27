import { useEffect, useRef, useState } from "react";
import ResponseSettingsPanel from "./ResponseSettingsPanel";

const RESPONSE_VIEWS = [
  ["completed", "completedTab"],
  ["incomplete", "incompleteTab"],
];

export default function ResponsesToolbar({
  t,
  responseView,
  setResponseView,
  data,
  updateActiveForm,
  showToast,
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsMenuRef = useRef(null);

  useEffect(() => {
    if (!settingsOpen) return undefined;

    const closeOnOutsideClick = (event) => {
      if (!settingsMenuRef.current?.contains(event.target)) {
        setSettingsOpen(false);
      }
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setSettingsOpen(false);
    };

    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [settingsOpen]);

  return (
    <section className="responses-workspace-toolbar" aria-label={t.responseTools}>
      <div className="responses-view-tabs" role="tablist" aria-label={t.responseViews}>
        {RESPONSE_VIEWS.map(([view, label]) => (
          <button
            key={view}
            type="button"
            role="tab"
            aria-selected={responseView === view}
            tabIndex={responseView === view ? 0 : -1}
            className={responseView === view ? "active" : ""}
            onClick={() => setResponseView(view)}
          >
            {t[label]}
          </button>
        ))}
      </div>

      {data.selectedForm ? (
        <div className="responses-table-controls">
          {data.hasBackendPagination ? (
            <div className="responses-pagination-controls">
              <button
                type="button"
                onClick={() => data.setSelectedPage(data.selectedPage - 1)}
                disabled={!data.hasPreviousPage || data.responsesLoading}
              >
                {t.previous}
              </button>
              <span>
                {t.page} {data.selectedPage + 1}
              </span>
              <button
                type="button"
                onClick={() => data.setSelectedPage(data.selectedPage + 1)}
                disabled={!data.hasNextPage || data.responsesLoading}
              >
                {t.next}
              </button>
            </div>
          ) : null}

          {data.hasBackendPagination ? (
            <button
              type="button"
              className="responses-refresh-button"
              onClick={data.refreshResponses}
              disabled={data.responsesLoading}
            >
              {data.responsesLoading ? t.refreshing : t.refresh}
            </button>
          ) : null}

          <div className="results-count-pill">
            {data.displayedResponses.length}{" "}
            {data.displayedResponses.length === 1 ? t.match : t.matches}
          </div>
        </div>
      ) : null}

      <div className="responses-settings-menu" ref={settingsMenuRef}>
        <button
          type="button"
          className="responses-settings-trigger"
          aria-label={t.settingsTab}
          aria-expanded={settingsOpen}
          aria-haspopup="dialog"
          disabled={!data.selectedForm}
          onClick={() => setSettingsOpen((open) => !open)}
        >
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </button>

        {settingsOpen && data.selectedForm ? (
          <div className="responses-settings-popover" role="dialog" aria-label={t.draftSettingsTitle}>
            <ResponseSettingsPanel
              form={data.selectedForm}
              t={t}
              updateActiveForm={updateActiveForm}
              showToast={showToast}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
