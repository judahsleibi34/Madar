import { useEffect, useMemo, useState } from "react";
import { LoaderCircle, RotateCcw, Save, ShoppingBag } from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import { fetchEcommerceTheme, saveEcommerceTheme } from "../../services/ecommerceApi";
import { readEcommerceThemeCacheSnapshot } from "./utils/ecommerceCatalogCache";

const DEFAULT_THEME = {
  accent: "#2463eb",
  ["back" + "ground"]: "#ffffff",
  surface: "#f7f8fa",
  text: "#151821",
  muted: "#697181",
};

const COLOR_FIELDS = [
  ["accent", "Main color", "Buttons, links, and highlights"],
  ["background", "Page background", "The main store background"],
  ["surface", "Cards and sections", "Product cards and soft panels"],
  ["text", "Main text", "Headings and important information"],
  ["muted", "Secondary text", "Descriptions and supporting information"],
];

const isHexColor = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ""));

export default function EcommerceThemePage({ user }) {
  const cacheScope = user?.id ? `user-${user.id}` : "authenticated";
  const cachedTheme = useMemo(() => readEcommerceThemeCacheSnapshot(cacheScope), [cacheScope]);
  const [theme, setTheme] = useState(() => ({ ...DEFAULT_THEME, ...(cachedTheme?.theme || {}) }));
  const [loading, setLoading] = useState(() => !cachedTheme);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceTheme({ scope: cacheScope, force: Boolean(cachedTheme?.isStale) })
      .then((result) => {
        if (!cancelled) setTheme({ ...DEFAULT_THEME, ...(result?.theme || {}) });
      })
      .catch((error) => {
        if (!cancelled) setToast({ id: Date.now(), type: "error", title: "Could not load store colors", message: error.message || "Try again in a moment." });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [cacheScope, cachedTheme?.isStale]);

  const valid = useMemo(() => COLOR_FIELDS.every(([key]) => isHexColor(theme[key])), [theme]);
  const previewStyle = {
    "--preview-accent": theme.accent,
    "--preview-background": theme.background,
    "--preview-surface": theme.surface,
    "--preview-text": theme.text,
    "--preview-muted": theme.muted,
  };

  const updateColor = (key, value) => setTheme((current) => ({ ...current, [key]: value.toLowerCase() }));

  const save = async () => {
    if (!valid) {
      setToast({ id: Date.now(), type: "error", title: "Check the colors", message: "Each color needs a complete six-digit value, such as #2463eb." });
      return;
    }
    setSaving(true);
    try {
      const result = await saveEcommerceTheme(theme, { scope: cacheScope });
      setTheme({ ...DEFAULT_THEME, ...(result?.theme || theme) });
      setToast({ id: Date.now(), type: "success", title: "Store colors saved", message: "The new colors now appear on your published shop." });
    } catch (error) {
      setToast({ id: Date.now(), type: "error", title: "Could not save store colors", message: error.message || "Try again in a moment." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="ecommerce-theme-page">
      <header className="ecommerce-page-header">
        <div>
          <span className="ecommerce-page-kicker">Ecommerce</span>
          <h1>Store theme</h1>
          <p>Choose the colors customers see across your published shop.</p>
        </div>
        <button type="button" className="ecommerce-primary-button" disabled={saving || loading} onClick={save}>
          {saving ? <LoaderCircle size={18} className="is-spinning" /> : <Save size={18} />}
          {saving ? "Saving…" : "Save colors"}
        </button>
      </header>

      {loading ? (
        <div className="ecommerce-loading"><LoaderCircle size={26} className="is-spinning" />Loading store colors…</div>
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

          <aside className="ecommerce-theme-preview" style={previewStyle} aria-label="Store color preview">
            <div className="ecommerce-theme-preview-label"><span>Live preview</span><small>Updates as you choose colors</small></div>
            <div className="ecommerce-theme-preview-window">
              <header><strong>Your store</strong><nav>Home&nbsp;&nbsp; Products&nbsp;&nbsp; Categories&nbsp;&nbsp; Contact</nav><ShoppingBag size={18} /></header>
              <section><p>New collection</p><h2>Products made for you.</h2><span>Discover your latest products and customer favorites.</span><button type="button">Shop now</button></section>
              <div className="ecommerce-theme-preview-products">
                <article><i /><small>Featured product</small><strong>Product name</strong></article>
                <article><i /><small>New arrival</small><strong>Product name</strong></article>
              </div>
            </div>
          </aside>
        </div>
      )}

      <AuthToast key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
