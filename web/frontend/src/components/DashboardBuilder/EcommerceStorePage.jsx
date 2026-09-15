import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw, Settings } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";
import { useCommerceI18n } from "../../utils/commerceI18n";

const STOREFRONT_ORIGIN = String(
  import.meta.env.VITE_STOREFRONT_URL || import.meta.env.VITE_PUBLIC_APP_URL || "https://madarportal.com"
).replace(/\/$/, "");

export default function EcommerceStorePage({ user }) {
  const location = useLocation();
  const { t, locale, direction } = useCommerceI18n();
  const draftPreview = new URLSearchParams(location.search).get("preview") === "draft";
  const [website, setWebsite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [frameVersion, setFrameVersion] = useState(0);
  const [frameReady, setFrameReady] = useState(false);
  const cacheScope = user?.tenant_id || user?.id ? `commerce-${user?.tenant_id || user?.id}` : "authenticated";

  useEffect(() => {
    let cancelled = false;
    fetchWebsiteSettings(cacheScope)
      .then((result) => {
        if (!cancelled) setWebsite(result || null);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError?.message || t("admin.loadSettingsError"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cacheScope, t]);

  const subdomain = String(website?.subdomain || "").trim();
  const livePath = subdomain
    ? `/site/${encodeURIComponent(subdomain)}/shop`
    : "";
  const liveUrl = useMemo(
    () => (
      subdomain
        ? new URL(`/site/${encodeURIComponent(subdomain)}/shop`, STOREFRONT_ORIGIN).toString()
        : ""
    ),
    [subdomain]
  );
  const previewPath = livePath ? `${livePath}${draftPreview ? "?preview=draft" : ""}` : "";
  const openUrl = draftPreview ? previewPath : liveUrl;

  return (
    <main className="ecommerce-store-admin" dir={direction} lang={locale}>
      <header className="ecommerce-store-admin-header app-page-intro">
        <div>
          <h1>{draftPreview ? t("admin.draftPreview") : t("admin.publishedStore")}</h1>
          <p>{draftPreview ? t("admin.draftPreviewBody") : t("admin.publishedStoreBody")}</p>
        </div>
        {liveUrl && (
          <div className="ecommerce-store-admin-actions">
            <button type="button" onClick={() => { setFrameReady(false); setFrameVersion((value) => value + 1); }}>
              <RefreshCw size={16} aria-hidden="true" />
              {t("common.retry")}
            </button>
            <a href={openUrl} target="_blank" rel="noreferrer">
              <ExternalLink size={16} aria-hidden="true" />
              {draftPreview ? t("admin.openPreview") : t("admin.openPublishedStore")}
            </a>
          </div>
        )}
      </header>

      {loading && <div className="ecommerce-store-page-skeleton" role="status" aria-label={t("admin.loadingStorePreview")}><i /><i /><i /></div>}
      {!loading && error && (
        <div className="ecommerce-store-admin-state is-error">
          <h2>{t("admin.previewUnavailable")}</h2>
          <p>{error}</p>
        </div>
      )}
      {!loading && !error && !subdomain && (
        <div className="ecommerce-store-admin-state">
          <Settings size={30} aria-hidden="true" />
          <h2>{t("admin.setAddressFirst")}</h2>
          <p>{t("admin.chooseAddressBeforeLive")}</p>
          <Link to="/settings">{t("admin.openStoreSettings")}</Link>
        </div>
      )}
      {!loading && !error && subdomain && (
        <section className="ecommerce-store-frame-shell">
          {!frameReady && <div className="ecommerce-store-frame-loading" role="status" aria-label={t("admin.loadingStorefront")}><i /><i /><i /><i /></div>}
          <iframe
            key={frameVersion}
            src={previewPath}
            title={draftPreview ? t("admin.draftStoreTitle") : t("admin.publishedStoreTitle")}
            className="ecommerce-store-frame"
            onLoad={() => setFrameReady(true)}
          />
        </section>
      )}
    </main>
  );
}
