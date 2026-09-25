import PageHeaderSkeleton from "../common/PageHeaderSkeleton";
import { getEcommerceCacheScope, readEcommerceAdminCacheSnapshot } from "./utils/ecommerceAdminCache";
import EcommerceRouteSkeleton from "./EcommerceRouteSkeleton";
import { StorePreviewSkeleton } from "./CommerceLoadingLayouts";
import EcommerceToast from "./EcommerceToast";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw, Settings } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";
import { useCommerceI18n } from "../../utils/commerceI18n";
import { buildCanonicalTenantUrl } from "../../utils/hostedAddress";

export default function EcommerceStorePage({ user }) {
  const cacheScope = getEcommerceCacheScope(user);
  const location = useLocation();
  const { t, locale, direction } = useCommerceI18n();
  const draftPreview = new URLSearchParams(location.search).get("preview") === "draft";
  const snapshot = readEcommerceAdminCacheSnapshot(cacheScope, "website-settings");
  const [website, setWebsite] = useState(() => snapshot?.data || null);
  const [loading, setLoading] = useState(() => !snapshot);
  const [error, setError] = useState("");
  const [toast, setToast] = useState(null);
  const [frameVersion, setFrameVersion] = useState(0);
  const [frameReady, setFrameReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchWebsiteSettings(cacheScope)
      .then((result) => {
        if (!cancelled) setWebsite(result || null);
      })
      .catch(() => {
        if (!cancelled) {
          setError(t("admin.loadSettingsError"));
          setToast({ type: "error", title: t("admin.loadSettingsError"), message: t("admin.tryAgain") });
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
  const publishedPreviewPath = subdomain ? `/ecommerce-preview/${encodeURIComponent(subdomain)}` : "";
  const draftPath = publishedPreviewPath ? `${publishedPreviewPath}?preview=draft` : "";
  const liveUrl = useMemo(
    () => (
      subdomain
        ? buildCanonicalTenantUrl(subdomain, "/shop")
        : ""
    ),
    [subdomain]
  );
  const previewPath = draftPreview ? draftPath : publishedPreviewPath;
  const openUrl = draftPreview ? draftPath : liveUrl;

  if (loading) return <EcommerceRouteSkeleton pathname="/ecommerce/store" label={t("admin.loadingStorePreview")} direction={direction} lang={locale} />;

  return (
    <main className="ecommerce-store-admin" dir={direction} lang={locale}>
      {(!error && subdomain && !frameReady) ? <PageHeaderSkeleton className="ecommerce-store-admin-header app-page-intro" actions /> : (<header className="ecommerce-store-admin-header app-page-intro">
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
      </header>)}

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
        <section className="ecommerce-store-frame-shell" aria-busy={!frameReady}>
          {!frameReady && <StorePreviewSkeleton className="ecommerce-store-frame-loading" label={t("admin.loadingStorefront")} />}
          <iframe
            key={frameVersion}
            src={previewPath}
            title={draftPreview ? t("admin.draftStoreTitle") : t("admin.publishedStoreTitle")}
            className="ecommerce-store-frame"
            onLoad={() => { setFrameReady(true); if (frameVersion > 0) setToast({ type: "success", title: t("feedback.previewRefreshed"), message: t("feedback.previewRefreshedBody") }); }}
            onError={() => { setFrameReady(true); setToast({ type: "error", title: t("admin.previewUnavailable"), message: t("admin.tryAgain") }); }}
          />
        </section>
      )}
      <EcommerceToast {...toast} dir={direction} onDismiss={() => setToast(null)} />
    </main>
  );
}
