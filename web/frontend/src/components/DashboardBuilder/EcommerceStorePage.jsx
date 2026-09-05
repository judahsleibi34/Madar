import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw, Settings } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";

const STOREFRONT_ORIGIN = String(
  import.meta.env.VITE_STOREFRONT_URL || import.meta.env.VITE_PUBLIC_APP_URL || "https://madarportal.com"
).replace(/\/$/, "");

export default function EcommerceStorePage() {
  const location = useLocation();
  const draftPreview = new URLSearchParams(location.search).get("preview") === "draft";
  const [website, setWebsite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [frameVersion, setFrameVersion] = useState(0);
  const [frameReady, setFrameReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchWebsiteSettings()
      .then((result) => {
        if (!cancelled) setWebsite(result || null);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError?.message || "Could not load website settings.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
    <main className="ecommerce-store-admin">
      <header className="ecommerce-store-admin-header app-page-intro">
        <div>
          <h1>{draftPreview ? "Draft preview" : "Published store"}</h1>
          <p>{draftPreview ? "This private browser preview uses your unpublished design draft. Nothing here is live yet." : "Review the customer experience currently available in production."}</p>
        </div>
        {liveUrl && (
          <div className="ecommerce-store-admin-actions">
            <button type="button" onClick={() => { setFrameReady(false); setFrameVersion((value) => value + 1); }}>
              <RefreshCw size={16} aria-hidden="true" />
              Refresh
            </button>
            <a href={openUrl} target="_blank" rel="noreferrer">
              <ExternalLink size={16} aria-hidden="true" />
              {draftPreview ? "Open preview" : "Open production store"}
            </a>
          </div>
        )}
      </header>

      {loading && <div className="ecommerce-store-page-skeleton" role="status" aria-label="Loading store preview"><i /><i /><i /></div>}
      {!loading && error && (
        <div className="ecommerce-store-admin-state is-error">
          <h2>Store preview unavailable</h2>
          <p>{error}</p>
        </div>
      )}
      {!loading && !error && !subdomain && (
        <div className="ecommerce-store-admin-state">
          <Settings size={30} aria-hidden="true" />
          <h2>Set your store address first</h2>
          <p>Choose a public store address in Settings before opening the live store.</p>
          <Link to="/settings">Open store settings</Link>
        </div>
      )}
      {!loading && !error && subdomain && (
        <section className="ecommerce-store-frame-shell">
          {!frameReady && <div className="ecommerce-store-frame-loading" role="status" aria-label="Loading storefront"><i /><i /><i /><i /></div>}
          <iframe
            key={frameVersion}
            src={previewPath}
            title={draftPreview ? "Draft online store preview" : "Published online store"}
            className="ecommerce-store-frame"
            onLoad={() => setFrameReady(true)}
          />
        </section>
      )}
    </main>
  );
}
