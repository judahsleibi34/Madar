import {
  AlertTriangle,
  Check,
  Copy,
  Eye,
  Globe2,
  MessageCircle,
} from "lucide-react";

export default function PageBuilderPublishTab({
  project,
  openPreviewPage,
  openFormPreviewPage,
}) {
  const activePage = project.pages?.find((page) => page.id === project.activePageId) || project.pages?.[0];
  const activeForm = project.forms?.find((form) => form.id === project.activeFormId) || project.forms?.[0];
  const hasForm = Boolean(activeForm);
  const publicPath = activePage?.slug || "/";
  const publicLink = `${window.location.origin}/site/${project.siteChrome?.subdomain || project.id}${publicPath === "/" ? "" : publicPath}`;
  const formPreviewLink = activeForm
    ? `${window.location.origin}/page-builder/form-preview/${activeForm.id}`
    : "";
  const formFields = (activeForm?.sections || []).flatMap((section) => section.fields || []);
  const isBilingual = activeForm?.languageMode === "bilingual";
  const bilingualComplete = !isBilingual || Boolean(
    activeForm?.localized?.title?.en &&
    activeForm?.localized?.title?.ar &&
    formFields.every((field) => field.localized?.label?.en && field.localized?.label?.ar)
  );
  const checklist = [
    { label: "Site page has a title", done: Boolean(activePage?.name) },
    { label: "Builder has an active form", done: hasForm },
    { label: "Active form has a title", done: Boolean(activeForm?.title || activeForm?.localized?.title?.en || activeForm?.localized?.title?.ar) },
    { label: "Active form has at least one question", done: formFields.length > 0 },
    { label: "Required form fields have labels", done: formFields.filter((field) => field.required).every((field) => field.label || field.localized?.label?.en || field.localized?.label?.ar) },
    { label: "Active bilingual form content is complete", done: bilingualComplete, optional: !isBilingual },
    { label: "Public site preview is ready to check", done: Boolean(activePage) },
  ];

  const copyPublicLink = async () => {
    await navigator.clipboard?.writeText(publicLink);
  };

  const copyFormPreviewLink = async () => {
    if (!formPreviewLink) return;
    await navigator.clipboard?.writeText(formPreviewLink);
  };

  const whatsAppUrl = `https://wa.me/?text=${encodeURIComponent(publicLink)}`;
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(publicLink)}`;
  const formWhatsAppUrl = `https://wa.me/?text=${encodeURIComponent(formPreviewLink)}`;
  const formQrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(formPreviewLink)}`;

  return (
    <div className="workspace-page publish-workspace">
      <div className="workspace-header publish-site-header">
        <div>
          <span className="publish-scope-pill">
            <Globe2 size={15} aria-hidden="true" />
            Builder site
          </span>
          <h2>Publish site</h2>
          <p>This publishes the full builder website. Individual form preview and placement stay in the Forms workspace.</p>
        </div>
      </div>

      <div className="publish-grid publish-dashboard-grid">
        <div className="publish-operations-column">
          <section className="publish-card publish-status-card">
            <h3>Site status</h3>
            <div className="publish-status-list">
              <p>
                <span>Builder project</span>
                <strong>{project.name}</strong>
              </p>
              <p>
                <span>Site state</span>
                <strong>{project.status}</strong>
              </p>
              <p>
                <span>Last saved</span>
                <strong>{project.publish?.lastSavedAt || "Not saved yet"}</strong>
              </p>
              <p>
                <span>Last published</span>
                <strong>{project.publish?.lastPublishedAt || "Not published yet"}</strong>
              </p>
            </div>
          </section>

          <section className="publish-card">
            <h3>Site publish checklist</h3>
            <ul className="publish-checklist">
              {checklist.map((item) => (
                <li key={item.label} className={item.done ? "done" : ""}>
                  <span>
                    {item.done ? (
                      <Check size={15} aria-hidden="true" />
                    ) : (
                      <AlertTriangle size={14} aria-hidden="true" />
                    )}
                  </span>
                  {item.label}
                  {item.optional ? " (only for bilingual forms)" : ""}
                </li>
              ))}
            </ul>
          </section>

        </div>

        <div className="publish-links-column">
          <section className="publish-card publish-link-card">
            <div className="publish-card-heading">
              <h3>Public site link</h3>
              <span>Website</span>
            </div>
            <div className="publish-link-content">
              <div className="publish-link-main">
                <div className="publish-link-box">
                  <input value={publicLink} readOnly />
                  <button type="button" onClick={copyPublicLink}>
                    <Copy size={15} aria-hidden="true" />
                    Copy link
                  </button>
                </div>
                <div className="publish-share-row">
                  <a href={whatsAppUrl} target="_blank" rel="noreferrer">
                    <MessageCircle size={15} aria-hidden="true" />
                    Share on WhatsApp
                  </a>
                  <button type="button" onClick={openPreviewPage}>
                    <Eye size={15} aria-hidden="true" />
                    Preview site
                  </button>
                </div>
              </div>
              <div className="publish-qr-preview">
                <img src={qrUrl} alt="QR code preview for public site link" />
                <span>QR preview</span>
              </div>
            </div>
          </section>

          <section className="publish-card publish-link-card">
            <div className="publish-card-heading">
              <h3>Active form preview link</h3>
              <span>Form</span>
            </div>
            {activeForm ? (
              <div className="publish-link-content">
                <div className="publish-link-main">
                  <p className="publish-card-note">
                    Form: <strong>{activeForm.title || "Untitled form"}</strong>
                  </p>
                  <div className="publish-link-box">
                    <input value={formPreviewLink} readOnly />
                    <button type="button" onClick={copyFormPreviewLink}>
                      <Copy size={15} aria-hidden="true" />
                      Copy link
                    </button>
                  </div>
                  <div className="publish-share-row">
                    <a href={formWhatsAppUrl} target="_blank" rel="noreferrer">
                      <MessageCircle size={15} aria-hidden="true" />
                      Share form
                    </a>
                    <button type="button" onClick={() => openFormPreviewPage?.(activeForm.id)}>
                      <Eye size={15} aria-hidden="true" />
                      Preview form
                    </button>
                  </div>
                </div>
                <div className="publish-qr-preview">
                  <img src={formQrUrl} alt="QR code preview for active form link" />
                  <span>Form QR preview</span>
                </div>
              </div>
            ) : (
              <div className="publish-empty-note">
                <AlertTriangle size={16} aria-hidden="true" />
                Create a form before sharing a form preview link.
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
