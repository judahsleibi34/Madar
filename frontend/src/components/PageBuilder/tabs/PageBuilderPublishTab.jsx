import {
  AlertTriangle,
  Copy,
  Eye,
  Globe2,
  MessageCircle,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";
import { getPublishContent } from "../../../content/pageBuilder";
import { sanitizeSubdomain } from "../core/PageBuilder.routing";

const qrPresets = [
  { color: "111827", qzone: 1, ecc: "M" },
  { color: "7F1D1D", qzone: 2, ecc: "Q" },
  { color: "1F2937", qzone: 3, ecc: "H" },
  { color: "0F3D3E", qzone: 2, ecc: "M" },
];

const buildQrUrl = (data, version) => {
  if (!data) return "";

  const preset = qrPresets[version % qrPresets.length];
  const params = new URLSearchParams({
    size: "180x180",
    data,
    color: preset.color,
    bgcolor: "FFFFFF",
    qzone: String(preset.qzone),
    ecc: preset.ecc,
    cache: String(version),
  });

  return `https://api.qrserver.com/v1/create-qr-code/?${params.toString()}`;
};

export default function PageBuilderPublishTab({
  project,
  persistProjectNow,
  publishProject,
  liveSitePath = "",
  openFormPreviewPage,
  lang = "en",
}) {
  const [publicQrVersion, setPublicQrVersion] = useState(1);
  const [formQrVersion, setFormQrVersion] = useState(1);
  const [isPublishing, setIsPublishing] = useState(false);
  const content = getPublishContent(lang);
  const activeForm = project.forms?.find((form) => form.id === project.activeFormId) || project.forms?.[0];
  const publishSubdomain = sanitizeSubdomain(project?.publish?.subdomain || "");
  const configuredLiveSitePath = publishSubdomain ? `/site/${publishSubdomain}/` : "";
  const resolvedLiveSitePath = liveSitePath || configuredLiveSitePath;
  const publicLink = resolvedLiveSitePath
    ? `${window.location.origin}${resolvedLiveSitePath}`
    : "";
  const formPreviewLink = activeForm
    ? `${window.location.origin}/page-builder/form-preview/${activeForm.id}`
    : "";

  const copyPublicLink = async () => {
    if (!publicLink) return;
    await navigator.clipboard?.writeText(publicLink);
  };

  const copyFormPreviewLink = async () => {
    if (!formPreviewLink) return;
    await navigator.clipboard?.writeText(formPreviewLink);
  };

  const handlePublish = async () => {
    if (!publishProject || isPublishing) return;

    setIsPublishing(true);

    try {
      await publishProject();
    } finally {
      setIsPublishing(false);
    }
  };

  const whatsAppUrl = publicLink ? `https://wa.me/?text=${encodeURIComponent(publicLink)}` : "";
  const qrUrl = buildQrUrl(publicLink, publicQrVersion);
  const formWhatsAppUrl = `https://wa.me/?text=${encodeURIComponent(formPreviewLink)}`;
  const formQrUrl = buildQrUrl(formPreviewLink, formQrVersion);

  const copyQrImage = async (qrImageUrl) => {
    if (!qrImageUrl) return;

    try {
      const response = await fetch(qrImageUrl);
      const blob = await response.blob();

      if (navigator.clipboard?.write && window.ClipboardItem) {
        await navigator.clipboard.write([
          new ClipboardItem({ [blob.type || "image/png"]: blob }),
        ]);
        return;
      }
    } catch {
      if (import.meta.env.DEV) {
        console.warn("Could not copy QR image, copying QR URL instead.");
      }
    }

    await navigator.clipboard?.writeText(qrImageUrl);
  };

  return (
    <div className="workspace-page publish-workspace">
      <div className="workspace-header publish-site-header">
        <div>
          <h2>{content.title}</h2>
          <p>{content.description}</p>
        </div>
      </div>

      <div className="publish-console">
        <section className="publish-panel publish-status-panel">
          <div className="publish-panel-title">
            <span>01</span>
            <h3>{content.statusTitle}</h3>
          </div>
          <div className="publish-actions">
            <button
              type="button"
              className="primary-action"
              onClick={handlePublish}
              disabled={!publishProject || isPublishing}
            >
              <Globe2 size={15} aria-hidden="true" />
              {isPublishing ? content.publishingSite : content.publishSite}
            </button>
          </div>
          <dl className="publish-status-list">
            <div>
              <dt>{content.projectLabel}</dt>
              <dd>{project.name}</dd>
            </div>
            <div>
              <dt>{content.stateLabel}</dt>
              <dd>{project.status}</dd>
            </div>
            <div>
              <dt>{content.lastSavedLabel}</dt>
              <dd>{project.publish?.lastSavedAt || content.notSaved}</dd>
            </div>
            <div>
              <dt>{content.lastPublishedLabel}</dt>
              <dd>{project.publish?.lastPublishedAt || content.notPublished}</dd>
            </div>
          </dl>
        </section>

        <section className="publish-panel publish-link-panel">
          <div className="publish-panel-title">
            <span>02</span>
            <h3>{content.publicLinkTitle}</h3>
            <strong>{content.websiteLabel}</strong>
          </div>
          <div className="publish-link-card-body">
            <div className="publish-link-main">
                <div className="publish-link-box">
                  <input value={publicLink} readOnly placeholder={content.noPublicLink} />
                  <button type="button" onClick={copyPublicLink} disabled={!publicLink}>
                  <Copy size={15} aria-hidden="true" />
                    {content.copyLink}
                  </button>
                </div>
                <div className="publish-link-actions">
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
                {qrUrl ? (
                  <img key={qrUrl} src={qrUrl} alt={content.publicQrAlt} />
                ) : (
                  <div className="publish-empty-note">{content.noPublicLink}</div>
                )}
                <span>{content.qrPreview}</span>
                <div className="publish-qr-actions">
                  <button type="button" onClick={() => setPublicQrVersion((value) => value + 1)}>
                    <RefreshCw size={14} aria-hidden="true" />
                    New QR
                  </button>
                  <button type="button" onClick={() => copyQrImage(qrUrl)}>
                    <Copy size={14} aria-hidden="true" />
                    Copy QR
                  </button>
                </div>
              </div>
            </div>
          </section>

        <section className="publish-panel publish-link-panel">
          <div className="publish-panel-title">
            <span>03</span>
            <h3>{content.formLinkTitle}</h3>
            <strong>{content.formLabel}</strong>
          </div>
          {activeForm ? (
            <div className="publish-link-card-body">
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
                <div className="publish-link-actions">
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
                  <img key={formQrUrl} src={formQrUrl} alt={content.formQrAlt} />
                  <span>{content.formQrPreview}</span>
                  <div className="publish-qr-actions">
                    <button type="button" onClick={() => setFormQrVersion((value) => value + 1)}>
                      <RefreshCw size={14} aria-hidden="true" />
                      New QR
                    </button>
                    <button type="button" onClick={() => copyQrImage(formQrUrl)}>
                      <Copy size={14} aria-hidden="true" />
                      Copy QR
                    </button>
                  </div>
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
  );
}
