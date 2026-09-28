import { useEffect, useMemo, useState } from "react";
import { ExternalLink, LoaderCircle, Save, Share2 } from "lucide-react";

import PageHeaderSkeleton from "../common/PageHeaderSkeleton";
import EcommerceToast from "./EcommerceToast";
import { SocialLinksSkeleton } from "./CommerceLoadingLayouts";
import { fetchEcommerceSocialLinks, saveEcommerceSocialLinks } from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";
import { getEcommerceCacheScope } from "./utils/ecommerceAdminCache";

const SOCIAL_NETWORKS = [
  ["facebook", "Facebook", "https://facebook.com/your-page"],
  ["instagram", "Instagram", "https://instagram.com/your-account"],
  ["tiktok", "TikTok", "https://tiktok.com/@your-account"],
  ["snapchat", "Snapchat", "your-account"],
];

const EMPTY_LINKS = Object.fromEntries(SOCIAL_NETWORKS.map(([key]) => [key, ""]));
const SNAPCHAT_PROFILE_PREFIX = "https://www.snapchat.com/add/";
const SNAPCHAT_USERNAME_PATTERN = /^[A-Za-z][A-Za-z0-9._-]{1,13}[A-Za-z0-9]$/;

function SocialNetworkIcon({ network }) {
  if (network === "instagram") {
    return <svg className="is-stroke" data-network-icon={network} viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="17" height="17" rx="5" /><circle cx="12" cy="12" r="4" /><circle className="is-filled" cx="17.5" cy="6.5" r="1" /></svg>;
  }
  if (network === "tiktok") {
    return <svg data-network-icon={network} viewBox="0 0 24 24" aria-hidden="true"><path d="M14.2 3h3.4c.3 2.1 1.5 3.4 3.4 3.8v3.5a8.2 8.2 0 0 1-3.4-1v6.1A6.4 6.4 0 1 1 12 9v3.6a2.9 2.9 0 1 0 2.2 2.8V3Z" /></svg>;
  }
  if (network === "snapchat") {
    return <svg data-network-icon={network} viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2c3 0 4.8 2.3 4.8 5.2 0 1 .1 1.8.4 2.5.4.9 1.1 1.2 2.1 1.6.7.3.8 1.2.1 1.6-.8.4-1.5.7-2.1 1.1-.4.3-.3 1 .1 1.3.4.3.9.5 1.4.7-.8.8-1.8 1.1-2.9 1.1-.7 0-1.4.8-1.9 1.4-.5.6-1.2 1.1-2 1.1s-1.5-.5-2-1.1c-.5-.6-1.2-1.4-1.9-1.4-1.1 0-2.1-.3-2.9-1.1.5-.2 1-.4 1.4-.7.4-.3.5-1 .1-1.3-.6-.4-1.3-.7-2.1-1.1-.7-.4-.6-1.3.1-1.6 1-.4 1.7-.7 2.1-1.6.3-.7.4-1.5.4-2.5C7.2 5.5 9 3.2 12 3.2Z" /></svg>;
  }
  return <svg data-network-icon="facebook" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 8h3V4h-3c-3.3 0-5 2-5 5v3H6v4h3v8h4v-8h3l1-4h-4V9c0-.7.3-1 1-1Z" /></svg>;
}

const snapchatUsernameFromValue = (value) => {
  const cleaned = String(value || "").trim().replace(/^@/, "");
  if (!cleaned) return "";
  try {
    const parsed = new URL(cleaned);
    const hostname = parsed.hostname.toLowerCase().replace(/^www\./, "");
    const parts = parsed.pathname.split("/").filter(Boolean);
    if (hostname === "snapchat.com" && parts[0]?.toLowerCase() === "add" && parts[1]) {
      return decodeURIComponent(parts[1]).replace(/^@/, "");
    }
  } catch {
    // A plain Snapchat username is the preferred editor value.
  }
  return cleaned;
};

const socialEditorValue = (key, value) => key === "snapchat" ? snapchatUsernameFromValue(value) : String(value || "");
const socialDestination = (key, value) => key === "snapchat"
  ? (value ? `${SNAPCHAT_PROFILE_PREFIX}${encodeURIComponent(value)}` : "")
  : String(value || "").trim();

const isSecureUrl = (value) => {
  if (!value) return true;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && Boolean(parsed.hostname) && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
};

const isValidSocialValue = (key, value) => key === "snapchat"
  ? (!value || SNAPCHAT_USERNAME_PATTERN.test(value))
  : isSecureUrl(value);

export default function EcommerceSocialLinksPage({ user }) {
  const { t, locale, direction } = useCommerceI18n();
  const cacheScope = getEcommerceCacheScope(user);
  const [links, setLinks] = useState(EMPTY_LINKS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceSocialLinks({ scope: cacheScope })
      .then((result) => {
        if (!cancelled) {
          const saved = result?.social_links || {};
          setLinks(Object.fromEntries(SOCIAL_NETWORKS.map(([key]) => [key, socialEditorValue(key, saved[key])])));
        }
      })
      .catch(() => {
        if (!cancelled) setToast({ id: Date.now(), type: "error", title: t("admin.socialLinksLoadError"), message: t("admin.tryAgain") });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [cacheScope, t]);

  const invalidFields = useMemo(
    () => new Set(SOCIAL_NETWORKS.filter(([key]) => !isValidSocialValue(key, links[key])).map(([key]) => key)),
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
      const payload = Object.fromEntries(SOCIAL_NETWORKS.map(([key]) => [key, socialDestination(key, String(links[key] || "").trim())]));
      const result = await saveEcommerceSocialLinks(payload, { scope: cacheScope });
      const saved = result?.social_links || payload;
      setLinks(Object.fromEntries(SOCIAL_NETWORKS.map(([key]) => [key, socialEditorValue(key, saved[key])])));
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
                <span>
                  <b aria-hidden="true"><SocialNetworkIcon network={key} /></b>
                  <strong>{key === "snapchat" ? t("admin.snapchatUsername") : name}</strong>
                </span>
                <div>
                  <input
                    type={key === "snapchat" ? "text" : "url"}
                    dir="ltr"
                    inputMode={key === "snapchat" ? "text" : "url"}
                    value={links[key]}
                    className={invalidFields.has(key) ? "is-invalid" : ""}
                    placeholder={placeholder}
                    aria-invalid={invalidFields.has(key)}
                    onChange={(event) => setLinks((current) => ({ ...current, [key]: socialEditorValue(key, event.target.value) }))}
                  />
                  {links[key] && isValidSocialValue(key, links[key]) && <a href={socialDestination(key, links[key])} target="_blank" rel="noopener noreferrer" aria-label={t("admin.openSocialLink", { network: name })}><ExternalLink size={16} /></a>}
                </div>
                {key === "snapchat" && <small>{t("admin.snapchatUsernameHelp")}</small>}
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
