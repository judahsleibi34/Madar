import { useEffect, useMemo, useState } from "react";
import { ExternalLink, LoaderCircle, Save, Share2 } from "lucide-react";

import PageHeaderSkeleton from "../common/PageHeaderSkeleton";
import EcommerceToast from "./EcommerceToast";
import { SocialLinksSkeleton } from "./CommerceLoadingLayouts";
import { fetchEcommerceSocialLinks, saveEcommerceSocialLinks } from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";

const SOCIAL_NETWORKS = [
  ["facebook", "Facebook", "https://facebook.com/your-page"],
  ["instagram", "Instagram", "https://instagram.com/your-account"],
  ["tiktok", "TikTok", "https://tiktok.com/@your-account"],
  ["snapchat", "Snapchat", "https://snapchat.com/add/your-account"],
];

const EMPTY_LINKS = Object.fromEntries(SOCIAL_NETWORKS.map(([key]) => [key, ""]));

const isSecureUrl = (value) => {
  if (!value) return true;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && Boolean(parsed.hostname) && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
};

export default function EcommerceSocialLinksPage() {
  const { t, locale, direction } = useCommerceI18n();
  const [links, setLinks] = useState(EMPTY_LINKS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceSocialLinks()
      .then((result) => {
        if (!cancelled) setLinks({ ...EMPTY_LINKS, ...(result?.social_links || {}) });
      })
      .catch(() => {
        if (!cancelled) setToast({ id: Date.now(), type: "error", title: t("admin.socialLinksLoadError"), message: t("admin.tryAgain") });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [t]);

  const invalidFields = useMemo(
    () => new Set(SOCIAL_NETWORKS.filter(([key]) => !isSecureUrl(links[key])).map(([key]) => key)),
    [links]
  );

  const save = async (event) => {
    event.preventDefault();
    if (invalidFields.size) {
      setToast({ id: Date.now(), type: "error", title: t("admin.socialLinksInvalid"), message: t("admin.socialLinksHttps") });
      return;
    }
    setSaving(true);
    try {
      const payload = Object.fromEntries(SOCIAL_NETWORKS.map(([key]) => [key, String(links[key] || "").trim()]));
      const result = await saveEcommerceSocialLinks(payload);
      setLinks({ ...EMPTY_LINKS, ...(result?.social_links || payload) });
      setToast({ id: Date.now(), type: "success", title: t("admin.socialLinksSaved"), message: t("admin.socialLinksSavedBody") });
    } catch {
      setToast({ id: Date.now(), type: "error", title: t("admin.socialLinksSaveError"), message: t("admin.tryAgain") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="ecommerce-page ecommerce-operations-page ecommerce-social-page" dir={direction} lang={locale}>
      {loading ? <PageHeaderSkeleton className="ecommerce-page-header app-page-intro" /> : (
        <header className="ecommerce-page-header app-page-intro">
          <div>
            <h1>{t("admin.socialLinksTitle")}</h1>
            <p>{t("admin.socialLinksSubtitle")}</p>
          </div>
        </header>
      )}

      {loading ? <SocialLinksSkeleton label={t("admin.socialLinksLoading")} /> : (
        <form className="ecommerce-social-card" onSubmit={save} noValidate>
          <div className="ecommerce-social-card-heading">
            <span><Share2 size={20} aria-hidden="true" /></span>
            <div><h2>{t("admin.socialProfiles")}</h2><p>{t("admin.socialLinksHelp")}</p></div>
          </div>
          <div className="ecommerce-social-grid">
            {SOCIAL_NETWORKS.map(([key, name, placeholder]) => (
              <label className="ecommerce-social-field" key={key}>
                <span><b aria-hidden="true">{name.slice(0, 1)}</b><strong>{name}</strong></span>
                <div>
                  <input
                    type="url"
                    dir="ltr"
                    inputMode="url"
                    value={links[key]}
                    className={invalidFields.has(key) ? "is-invalid" : ""}
                    placeholder={placeholder}
                    aria-invalid={invalidFields.has(key)}
                    onChange={(event) => setLinks((current) => ({ ...current, [key]: event.target.value }))}
                  />
                  {links[key] && isSecureUrl(links[key]) && <a href={links[key]} target="_blank" rel="noopener noreferrer" aria-label={t("admin.openSocialLink", { network: name })}><ExternalLink size={16} /></a>}
                </div>
              </label>
            ))}
          </div>
          <p className="ecommerce-social-security-note">{t("admin.socialLinksHttps")}</p>
          <footer>
            <button type="submit" className="ecommerce-primary-button" disabled={saving}>
              {saving ? <LoaderCircle size={18} className="is-spinning" /> : <Save size={18} />}
              {saving ? t("admin.saving") : t("admin.saveSocialLinks")}
            </button>
          </footer>
        </form>
      )}
      <EcommerceToast dir={direction} key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
