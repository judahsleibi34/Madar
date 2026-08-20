import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw, Settings, ShoppingBag } from "lucide-react";
import { Link } from "react-router-dom";

import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";

export default function EcommerceStorePage() {
  const [website, setWebsite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [frameVersion, setFrameVersion] = useState(0);

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
    () => (livePath ? new URL(livePath, window.location.origin).toString() : ""),
    [livePath]
  );

  return (
    <main className="ecommerce-store-admin">
      <header className="ecommerce-store-admin-header">
        <div>
          <span className="ecommerce-store-admin-kicker">
            <ShoppingBag size={16} aria-hidden="true" />
            Ecommerce
          </span>
          <h1>Live Store</h1>
          <p>This is the exact storefront your visitors see. Active catalog changes appear here automatically.</p>
        </div>
        {liveUrl && (
          <div className="ecommerce-store-admin-actions">
            <button type="button" onClick={() => setFrameVersion((value) => value + 1)}>
              <RefreshCw size={16} aria-hidden="true" />
              Refresh
            </button>
            <a href={liveUrl} target="_blank" rel="noreferrer">
              <ExternalLink size={16} aria-hidden="true" />
              Open live store
            </a>
          </div>
        )}
      </header>

      {loading && <div className="ecommerce-store-admin-state">Loading your live store…</div>}
      {!loading && error && (
        <div className="ecommerce-store-admin-state is-error">
          <h2>Store preview unavailable</h2>
          <p>{error}</p>
        </div>
      )}
      {!loading && !error && !subdomain && (
        <div className="ecommerce-store-admin-state">
          <Settings size={30} aria-hidden="true" />
          <h2>Configure your public website first</h2>
          <p>Add a subdomain and publish a website project before opening the live store.</p>
          <Link to="/settings">Open website settings</Link>
        </div>
      )}
      {!loading && !error && subdomain && (
        <section className="ecommerce-store-frame-shell">
          <div className="ecommerce-store-frame-bar">
            <span className="ecommerce-store-frame-dot" />
            <span className="ecommerce-store-frame-dot" />
            <span className="ecommerce-store-frame-dot" />
            <code>{liveUrl}</code>
          </div>
          <iframe
            key={frameVersion}
            src={livePath}
            title="Live ecommerce store"
            className="ecommerce-store-frame"
          />
        </section>
      )}
    </main>
  );
}
