import {
  AlertTriangle,
  Check,
  Copy,
  Eye,
  Globe2,
  MessageCircle,
} from "lucide-react";
import { getPublishContent } from "../../../content/pageBuilder";

export default function PageBuilderPublishTab({
  project,
  persistProjectNow,
  liveSitePath = "",
  openFormPreviewPage,
  lang = "en",
}) {
  const content = getPublishContent(lang);
  const activePage = project.pages?.find((page) => page.id === project.activePageId) || project.pages?.[0];
  const activeForm = project.forms?.find((form) => form.id === project.activeFormId) || project.forms?.[0];
  const hasForm = Boolean(activeForm);
  const publicLink = liveSitePath ? `${window.location.origin}${liveSitePath}` : "";
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
    { label: content.checklist.pageTitle, done: Boolean(activePage?.name) },
    { label: content.checklist.activeForm, done: hasForm },
    { label: content.checklist.formTitle, done: Boolean(activeForm?.title || activeForm?.localized?.title?.en || activeForm?.localized?.title?.ar) },
    { label: content.checklist.formQuestion, done: formFields.length > 0 },
    { label: content.checklist.requiredLabels, done: formFields.filter((field) => field.required).every((field) => field.label || field.localized?.label?.en || field.localized?.label?.ar) },
    { label: content.checklist.bilingualComplete, done: bilingualComplete, optional: !isBilingual },
    { label: content.checklist.previewReady, done: Boolean(activePage) },
  ];

  const copyPublicLink = async () => {
    if (!publicLink) return;
    await navigator.clipboard?.writeText(publicLink);
  };

  const copyFormPreviewLink = async () => {
    if (!formPreviewLink) return;
    await navigator.clipboard?.writeText(formPreviewLink);
  };

  const whatsAppUrl = publicLink ? `https://wa.me/?text=${encodeURIComponent(publicLink)}` : "";
  const qrUrl = publicLink ? `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(publicLink)}` : "";
  const formWhatsAppUrl = `https://wa.me/?text=${encodeURIComponent(formPreviewLink)}`;
  const formQrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(formPreviewLink)}`;

  return (
    <div className="workspace-page publish-workspace">
      <div className="workspace-header publish-site-header">
        <div>
          <span className="publish-scope-pill">
            <Globe2 size={15} aria-hidden="true" />
            {content.scope}
          </span>
          <h2>{content.title}</h2>
          <p>{content.description}</p>
        </div>
      </div>

      <div className="publish-grid publish-dashboard-grid">
        <div className="publish-operations-column">
          <section className="publish-card publish-status-card">
            <h3>{content.statusTitle}</h3>
            <div className="publish-status-list">
              <p>
                <span>{content.projectLabel}</span>
                <strong>{project.name}</strong>
              </p>
              <p>
                <span>{content.stateLabel}</span>
                <strong>{project.status}</strong>
              </p>
              <p>
                <span>{content.lastSavedLabel}</span>
                <strong>{project.publish?.lastSavedAt || content.notSaved}</strong>
              </p>
              <p>
                <span>{content.lastPublishedLabel}</span>
                <strong>{project.publish?.lastPublishedAt || content.notPublished}</strong>
              </p>
            </div>
          </section>

          <section className="publish-card">
            <h3>{content.checklistTitle}</h3>
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
                  {item.optional ? content.bilingualOptional : ""}
                </li>
              ))}
            </ul>
          </section>

        </div>

        <div className="publish-links-column">
          <section className="publish-card publish-link-card">
            <div className="publish-card-heading">
              <h3>{content.publicLinkTitle}</h3>
              <span>{content.websiteLabel}</span>
            </div>
            <div className="publish-link-content">
              <div className="publish-link-main">
                <div className="publish-link-box">
                  <input value={publicLink} readOnly placeholder={content.notPublished} />
                  <button type="button" onClick={copyPublicLink} disabled={!publicLink}>
                    <Copy size={15} aria-hidden="true" />
                    {content.copyLink}
                  </button>
                </div>
                <div className="publish-share-row">
                  <a href={whatsAppUrl || undefined} target="_blank" rel="noreferrer" aria-disabled={!publicLink}>
                    <MessageCircle size={15} aria-hidden="true" />
                    {content.shareWhatsApp}
                  </a>
                  <button
                    type="button"
                    onClick={() => {
                      persistProjectNow?.(project);
                      if (publicLink) {
                        window.open(publicLink, "_blank", "noopener,noreferrer");
                      }
                    }}
                    disabled={!publicLink}
                  >
                    <Eye size={15} aria-hidden="true" />
                    {content.previewSite}
                  </button>
                </div>
              </div>
              <div className="publish-qr-preview">
                <img src={qrUrl} alt={content.publicQrAlt} />
                <span>{content.qrPreview}</span>
              </div>
            </div>
          </section>

          <section className="publish-card publish-link-card">
            <div className="publish-card-heading">
              <h3>{content.formLinkTitle}</h3>
              <span>{content.formLabel}</span>
            </div>
            {activeForm ? (
              <div className="publish-link-content">
                <div className="publish-link-main">
                  <p className="publish-card-note">
                    {content.formPrefix} <strong>{activeForm.title || content.untitledForm}</strong>
                  </p>
                  <div className="publish-link-box">
                    <input value={formPreviewLink} readOnly />
                    <button type="button" onClick={copyFormPreviewLink}>
                      <Copy size={15} aria-hidden="true" />
                      {content.copyLink}
                    </button>
                  </div>
                  <div className="publish-share-row">
                    <a href={formWhatsAppUrl} target="_blank" rel="noreferrer">
                      <MessageCircle size={15} aria-hidden="true" />
                      {content.shareForm}
                    </a>
                    <button type="button" onClick={() => openFormPreviewPage?.(activeForm.id)}>
                      <Eye size={15} aria-hidden="true" />
                      {content.previewForm}
                    </button>
                  </div>
                </div>
                <div className="publish-qr-preview">
                  <img src={formQrUrl} alt={content.formQrAlt} />
                  <span>{content.formQrPreview}</span>
                </div>
              </div>
            ) : (
              <div className="publish-empty-note">
                <AlertTriangle size={16} aria-hidden="true" />
                {content.noFormToShare}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
