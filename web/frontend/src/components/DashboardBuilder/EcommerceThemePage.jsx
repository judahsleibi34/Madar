import { useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, LoaderCircle, RotateCcw, Rocket } from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import { fetchEcommerceTheme, saveEcommerceTheme } from "../../services/ecommerceApi";
import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";
import { readEcommerceThemeCacheSnapshot } from "./utils/ecommerceCatalogCache";
import { MADAR_STORE_THEME, normalizeStoreTheme } from "../../utils/ecommerceTheme";

const DEFAULT_THEME = MADAR_STORE_THEME;

const COLOR_FIELDS = [
  ["accent", "Main color", "Buttons, links, and highlights"],
  ["background", "Page background", "The main store background"],
  ["surface", "Cards and sections", "Product cards and soft panels"],
  ["text", "Main text", "Headings and important information"],
  ["muted", "Secondary text", "Descriptions and supporting information"],
];

const isHexColor = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ""));
const THEME_PREVIEW_KEY = "madar-online-store-theme-preview";

export default function EcommerceThemePage({ user }) {
  const cacheScope = user?.id ? `user-${user.id}` : "authenticated";
  const cachedTheme = useMemo(() => readEcommerceThemeCacheSnapshot(cacheScope), [cacheScope]);
  const [theme, setTheme] = useState(() => normalizeStoreTheme(cachedTheme?.theme));
  const [loading, setLoading] = useState(() => !cachedTheme);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [website, setWebsite] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [frameReady, setFrameReady] = useState(false);
  const previewFrameRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceTheme({ scope: cacheScope, force: Boolean(cachedTheme?.isStale) })
      .then((result) => {
        if (!cancelled) setTheme(normalizeStoreTheme(result?.theme));
      })
      .catch((error) => {
        if (!cancelled) setToast({ id: Date.now(), type: "error", title: "Could not load store colors", message: error.message || "Try again in a moment." });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [cacheScope, cachedTheme?.isStale]);

  useEffect(() => {
    let cancelled = false;
    fetchWebsiteSettings()
      .then((result) => { if (!cancelled) setWebsite(result || null); })
      .catch(() => { if (!cancelled) setWebsite(null); })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const valid = useMemo(() => COLOR_FIELDS.every(([key]) => isHexColor(theme[key])), [theme]);
  const subdomain = String(website?.subdomain || "").trim();
  const previewPath = subdomain ? `/site/${encodeURIComponent(subdomain)}/shop?preview=draft` : "";

  const updateColor = (key, value) => setTheme((current) => ({ ...current, [key]: value.toLowerCase() }));

  const preview = () => {
    if (!valid) {
      setToast({ id: Date.now(), type: "error", title: "Check the colors", message: "Fix invalid color values before opening the draft preview." });
      return;
    }
    if (!previewPath) {
      setToast({ id: Date.now(), type: "error", title: "Store address needed", message: "Choose a store address in Settings before opening the preview." });
      return;
    }
    window.open(previewPath, "_blank", "noopener,noreferrer");
  };

  useEffect(() => {
    if (!valid) return;
    localStorage.setItem(THEME_PREVIEW_KEY, JSON.stringify(theme));
    previewFrameRef.current?.contentWindow?.postMessage({ type: "madar-online-store-theme-preview", theme }, window.location.origin);
  }, [theme, valid]);

  const save = async () => {
    if (!valid) {
      setToast({ id: Date.now(), type: "error", title: "Check the colors", message: "Each color needs a complete six-digit value, such as #852c21." });
      return;
    }
    setSaving(true);
    try {
      const result = await saveEcommerceTheme(theme, { scope: cacheScope });
      setTheme({ ...DEFAULT_THEME, ...(result?.theme || theme) });
      localStorage.removeItem(THEME_PREVIEW_KEY);
      setToast({ id: Date.now(), type: "success", title: "Store design published", message: "The new colors are now live in your online store." });
    } catch (error) {
      setToast({ id: Date.now(), type: "error", title: "Could not save store colors", message: error.message || "Try again in a moment." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="ecommerce-theme-page">
      <header className="ecommerce-page-header app-page-intro">
        <div>
          <h1>Store design</h1>
          <p>Design safely, preview the draft locally, then publish only when it is ready.</p>
        </div>
        <div className="ecommerce-page-actions">
          <button type="button" className="ecommerce-secondary-button" disabled={saving || loading || !previewPath} onClick={preview}><ExternalLink size={18} />Open full preview</button>
          <button type="button" className="ecommerce-primary-button" disabled={saving || loading} onClick={save}>
          {saving ? <LoaderCircle size={18} className="is-spinning" /> : <Rocket size={18} />}
          {saving ? "Publishing…" : "Publish changes"}
          </button>
        </div>
      </header>

      {loading ? (
        <div className="ecommerce-theme-skeleton" role="status" aria-label="Loading store design"><i /><i /><i /><i /><i /><i /></div>
      ) : (
        <div className="ecommerce-theme-layout">
          <section className="ecommerce-theme-controls" aria-label="Store colors">
            <div className="ecommerce-theme-color-list">
              {COLOR_FIELDS.map(([key, label, description]) => (
                <label className="ecommerce-theme-color-row" key={key}>
                  <input type="color" value={isHexColor(theme[key]) ? theme[key] : DEFAULT_THEME[key]} onChange={(event) => updateColor(key, event.target.value)} aria-label={`${label} color picker`} />
                  <span><strong>{label}</strong><small>{description}</small></span>
                  <input className={!isHexColor(theme[key]) ? "is-invalid" : ""} value={theme[key]} maxLength={7} spellCheck="false" aria-label={label} onChange={(event) => updateColor(key, event.target.value)} />
                </label>
              ))}
            </div>

            <button type="button" className="ecommerce-theme-reset" onClick={() => setTheme(DEFAULT_THEME)}><RotateCcw size={16} />Restore original colors</button>
          </section>

          <aside className="ecommerce-theme-preview" aria-label="Exact storefront preview">
            <div className="ecommerce-theme-preview-label"><span>Customer preview</span><small>Exact storefront · updates while you edit</small></div>
            <div className="ecommerce-theme-live-shell">
              {(previewLoading || (previewPath && !frameReady)) && <div className="ecommerce-theme-frame-skeleton" role="status" aria-label="Loading exact storefront preview"><i /><i /><i /><i /></div>}
              {!previewLoading && !previewPath && <div className="ecommerce-theme-preview-empty"><strong>Set your store address to preview</strong><span>Open Settings and choose a public address for your online store.</span></div>}
              {previewPath && <iframe ref={previewFrameRef} src={previewPath} title="Exact draft storefront preview" onLoad={() => { setFrameReady(true); previewFrameRef.current?.contentWindow?.postMessage({ type: "madar-online-store-theme-preview", theme }, window.location.origin); }} />}
            </div>
          </aside>
        </div>
      )}

      <AuthToast key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
