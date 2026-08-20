import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Download, ExternalLink, FileText, X } from "lucide-react";

const getExtension = (fileName = "", src = "") => {
  const candidate = String(fileName || src).split(/[?#]/, 1)[0];
  const extension = candidate.includes(".") ? candidate.split(".").pop() : "";
  return String(extension || "").toLowerCase();
};

const viewerThemeProperties = [
  "--theme-primary",
  "--theme-primary-hover",
  "--theme-primary-soft",
  "--theme-primary-rgb",
  "--theme-text",
  "--theme-text-soft",
  "--theme-text-inverse",
  "--theme-surface",
  "--theme-surface-muted",
  "--theme-border",
  "--theme-border-strong",
  "--theme-font-family",
];

export default function DocumentViewerElement({
  src,
  fileName,
  mimeType,
  title = "View document",
  description = "Open this file in a focused viewer.",
  interactive = false,
  ...rootProps
}) {
  const [open, setOpen] = useState(false);
  const [viewerTheme, setViewerTheme] = useState({});
  const rootRef = useRef(null);
  const extension = getExtension(fileName, src);
  const isPdf = mimeType === "application/pdf" || extension === "pdf";
  const typeLabel = isPdf ? "PDF" : extension === "docx" ? "DOCX" : extension === "doc" ? "DOC" : "FILE";
  const displayName = fileName || (src ? `Document.${extension || "file"}` : "No file uploaded");

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const openViewer = (event) => {
    if (!interactive) return;
    event.stopPropagation();
    if (!src) return;
    const computedStyle = window.getComputedStyle(rootRef.current);
    setViewerTheme(Object.fromEntries(
      viewerThemeProperties.map((property) => [property, computedStyle.getPropertyValue(property)])
    ));
    setOpen(true);
  };

  return (
    <>
      <div {...rootProps} ref={rootRef}>
        <div className="document-element-card">
          <span className="document-element-icon" aria-hidden="true"><FileText size={24} /></span>
          <span className="document-element-copy">
            <strong>{title || displayName}</strong>
            <span>{src ? description : "Upload a PDF or Word document"}</span>
            <small><b>{typeLabel}</b>{src ? displayName : "PDF, DOC, or DOCX"}</small>
          </span>
          {src ? (
            <button
              type="button"
              className="document-open-trigger"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={openViewer}
            >
              Open
              <ExternalLink size={16} aria-hidden="true" />
            </button>
          ) : (
            <span
              className="document-upload-required"
              title="Select this element, then choose Upload file in the Inspector."
            >
              Upload first
            </span>
          )}
        </div>
      </div>

      {open && typeof document !== "undefined" && createPortal(
        <div className="document-viewer-backdrop" style={viewerTheme} onMouseDown={(event) => {
          if (event.target === event.currentTarget) setOpen(false);
        }}>
          <section className="document-viewer-modal" role="dialog" aria-modal="true" aria-label={title || displayName}>
            <header>
              <span className="document-viewer-heading">
                <span className="document-element-icon" aria-hidden="true"><FileText size={22} /></span>
                <span><strong>{title || displayName}</strong><small>{displayName}</small></span>
              </span>
              <span className="document-viewer-actions">
                <a href={src} target="_blank" rel="noreferrer" title="Open in a new tab"><ExternalLink size={18} /><span>Open</span></a>
                <a href={src} download={fileName || true} title="Download file"><Download size={18} /><span>Download</span></a>
                <button type="button" autoFocus onClick={() => setOpen(false)} aria-label="Close document viewer"><X size={20} /></button>
              </span>
            </header>
            <div className="document-viewer-content">
              {isPdf ? (
                <iframe src={src} title={title || displayName} loading="lazy" />
              ) : (
                <div className="document-viewer-word-fallback">
                  <span className="document-element-icon" aria-hidden="true"><FileText size={34} /></span>
                  <strong>{displayName}</strong>
                  <p>Open the document with Word or another compatible application.</p>
                  <a href={src} target="_blank" rel="noreferrer"><ExternalLink size={17} />Open document</a>
                </div>
              )}
            </div>
          </section>
        </div>,
        document.body
      )}
    </>
  );
}
