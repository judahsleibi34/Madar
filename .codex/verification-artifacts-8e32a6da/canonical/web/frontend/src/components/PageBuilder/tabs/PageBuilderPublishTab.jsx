import {
  AlertTriangle,
  Copy,
  Eye,
  MessageCircle,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";
import { getPublishContent } from "../../../content/pageBuilder";
import {
  getProductionAppOrigin,
  getProductionFormUrl,
  sanitizeSubdomain,
} from "../core/PageBuilder.routing";

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
  liveSitePath = "",
  hasConfiguredSubdomain = false,
  openWebsiteSettings,
  openPublicFormPage,
  publishedFormIds = null,
  onPreviewSite,
  isLiveProject = false,
  onMakeLive,
  isMakingLive = false,
  lang = "en",
}) {
  const [publicQrVersion, setPublicQrVersion] = useState(1);
  const [formQrVersions, setFormQrVersions] = useState({});
  const content = getPublishContent(lang);
  const forms = Array.isArray(project.forms) ? project.forms : [];
  const publishSubdomain = sanitizeSubdomain(project?.publish?.subdomain || "");
  const hasPublicSubdomain = Boolean(publishSubdomain || hasConfiguredSubdomain);
  const configuredLiveSitePath = publishSubdomain ? `/site/${publishSubdomain}/` : "";
  const isPublished = project.status === "published";
  const isFormPublished = (form) => (
    Array.isArray(publishedFormIds) ? publishedFormIds.includes(form.id) : isPublished
  );
  const resolvedLiveSitePath = isPublished ? liveSitePath || configuredLiveSitePath : "";
  const productionAppOrigin = getProductionAppOrigin();
  const publicLink = resolvedLiveSitePath
    ? `${productionAppOrigin}${resolvedLiveSitePath}`
    : "";
  const publicLinkPlaceholder = hasPublicSubdomain
    ? content.siteNotPublished
    : content.noPublicLink;
  const formLinkPlaceholder = !hasPublicSubdomain
    ? content.noPublishedFormLink
    : content.formNotPublished;

  const copyPublicLink = async () => {
    if (!publicLink) return;
    await navigator.clipboard?.writeText(publicLink);
  };

  const copyPublishedFormLink = async (publishedFormLink) => {
    if (!publishedFormLink) return;
    await navigator.clipboard?.writeText(publishedFormLink);
  };

  const whatsAppUrl = publicLink ? `https://wa.me/?text=${encodeURIComponent(publicLink)}` : "";
  const qrUrl = buildQrUrl(publicLink, publicQrVersion);
  const formDestinations = forms.map((form) => {
    const isLive = isFormPublished(form);
    const link = isLive && publishSubdomain ? getProductionFormUrl(project, form.id) : "";
    return {
      form,
      isLive,
      link,
      whatsAppUrl: link ? `https://wa.me/?text=${encodeURIComponent(link)}` : "",
      qrUrl: buildQrUrl(link, formQrVersions[form.id] || 1),
    };
  });

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
      {!hasConfiguredSubdomain && (
        <section className="publish-subdomain-warning" role="alert">
          <AlertTriangle size={22} aria-hidden="true" />
          <div>
            <strong>Choose your standard hosted address first</strong>
            <p>Page-builder plans include a path such as madarportal.com/site/business-name. A branded business-name.madarportal.com address is a separate paid add-on.</p>
          </div>
          <button type="button" className="primary-action" onClick={openWebsiteSettings}>
            Add hosted address
          </button>
        </section>
      )}

      <header className="workspace-header publish-site-header">
        <div>
          <h2>{content.title}</h2>
          <p>{content.description}</p>
        </div>
      </header>

      <div className="publish-console">
        <section className="publish-panel publish-status-panel">
          <div className="publish-panel-title">
            <h3>{content.statusTitle}</h3>
            <strong>{isPublished ? "Live" : "Draft"}</strong>
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
          {isPublished && !isLiveProject && onMakeLive && (
            <div className="publish-status-footer">
              <div className="publish-status-actions">
                <button
                  type="button"
                  className="primary-action"
                  disabled={isMakingLive}
                  onClick={onMakeLive}
                >
                  {isMakingLive ? "Making live..." : "Make this the live project"}
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="publish-panel publish-link-panel">
          <div className="publish-panel-title">
            <h3>{content.publicLinkTitle}</h3>
            <strong>{content.websiteLabel}</strong>
          </div>
          <div className="publish-link-card-body">
            <div className="publish-link-main">
                <div className="publish-form-meta">
                  <p className="publish-card-note">
                    Website: <strong>{project.name}</strong>
                  </p>
                  <span className={"publish-form-state" + (publicLink ? " is-live" : "")}>
                    {publicLink ? "Live" : "Not published"}
                  </span>
                </div>
                <div className="publish-link-box">
                  <input
                    className={publicLink ? "" : "publish-link-note-input"}
                    value={publicLink}
                    readOnly
                    placeholder={publicLinkPlaceholder}
                  />
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
                  onClick={onPreviewSite}
                  disabled={!onPreviewSite}
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
                  <div className="publish-empty-note">{publicLinkPlaceholder}</div>
                )}
                <span>{content.qrPreview}</span>
                <div className="publish-qr-actions">
                  <button type="button" onClick={() => setPublicQrVersion((value) => value + 1)}>
                    <RefreshCw size={14} aria-hidden="true" />
                    Refresh
                  </button>
                  <button type="button" onClick={() => copyQrImage(qrUrl)}>
                    <Copy size={14} aria-hidden="true" />
                    Copy
                  </button>
                </div>
              </div>
            </div>
          </section>

        <section className="publish-panel publish-link-panel publish-forms-panel">
          <div className="publish-panel-title">
            <h3>{content.formLinkTitle}</h3>
            <strong>{content.formLabel}</strong>
          </div>
          {formDestinations.length ? (
            <div className="publish-form-list">
              {formDestinations.map(({
                form,
                isLive,
                link,
                whatsAppUrl: formWhatsAppUrl,
                qrUrl: formQrUrl,
              }) => (
                <article
                  key={form.id}
                  className={"publish-form-card" + (isLive ? " is-live" : " is-unpublished")}
                >
                  <div className="publish-link-card-body">
                    <div className="publish-link-main">
                      <div className="publish-form-meta">
                        <p className="publish-card-note">
                          {content.formPrefix} <strong>{form.title || content.untitledForm}</strong>
                        </p>
                        <span className={"publish-form-state" + (isLive ? " is-live" : "")}>
                          {isLive ? "Live" : "Not published"}
                        </span>
                      </div>
                      <div className="publish-link-box">
                        <input
                          className={link ? "" : "publish-link-note-input"}
                          value={link}
                          readOnly
                          placeholder={formLinkPlaceholder}
                        />
                        <button
                          type="button"
                          onClick={() => copyPublishedFormLink(link)}
                          disabled={!link}
                        >
                          <Copy size={15} aria-hidden="true" />
                          {content.copyLink}
                        </button>
                      </div>
                      <div className="publish-link-actions">
                        <a
                          href={formWhatsAppUrl || undefined}
                          target="_blank"
                          rel="noreferrer"
                          aria-disabled={!link}
                        >
                          <MessageCircle size={15} aria-hidden="true" />
                          {content.shareForm}
                        </a>
                        <button
                          type="button"
                          disabled={!link || !openPublicFormPage}
                          onClick={() => openPublicFormPage?.(form.id)}
                        >
                          <Eye size={15} aria-hidden="true" />
                          {content.previewForm}
                        </button>
                      </div>
                    </div>
                    <div className="publish-qr-preview">
                      {formQrUrl ? (
                        <img
                          key={formQrUrl}
                          src={formQrUrl}
                          alt={content.formQrAlt + ": " + (form.title || content.untitledForm)}
                        />
                      ) : (
                        <div className="publish-empty-note">{formLinkPlaceholder}</div>
                      )}
                      <span>{content.formQrPreview}</span>
                      <div className="publish-qr-actions">
                        <button
                          type="button"
                          disabled={!formQrUrl}
                          onClick={() => setFormQrVersions((versions) => ({
                            ...versions,
                            [form.id]: (versions[form.id] || 1) + 1,
                          }))}
                        >
                          <RefreshCw size={14} aria-hidden="true" />
                          Refresh
                        </button>
                        <button
                          type="button"
                          disabled={!formQrUrl}
                          onClick={() => copyQrImage(formQrUrl)}
                        >
                          <Copy size={14} aria-hidden="true" />
                          Copy
                        </button>
                      </div>
                    </div>
                  </div>
                </article>
              ))}
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
