import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Boxes,
  CheckCircle2,
  FolderTree,
  LoaderCircle,
  Package,
  Pencil,
  Plus,
  Search,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  deleteEcommerceItem,
  fetchEcommerceCatalog,
  saveEcommerceItem,
} from "../../services/ecommerceApi";

const SECTION_CONFIG = {
  tags: {
    icon: Tag,
    title: "Tags",
    singular: "tag",
    description: "Create reusable labels that make products easier to organize and discover.",
  },
  categories: {
    icon: FolderTree,
    title: "Categories",
    singular: "category",
    description: "Build a clear catalog structure with parent categories and subcategories.",
  },
  products: {
    icon: Package,
    title: "Products",
    singular: "product",
    description: "Manage complete product records, translated content, pricing, inventory, and SEO.",
  },
};

const blankTranslations = () => ({
  en: { name: "", description: "" },
  ar: { name: "", description: "" },
});

function blankForm(section) {
  const shared = { slug: "", status: section === "products" ? "draft" : "active", translations: blankTranslations() };
  if (section === "tags") return shared;
  if (section === "categories") return { ...shared, parent_id: "", sort_order: 0 };
  return {
    ...shared,
    sku: "",
    barcode: "",
    category_id: "",
    tag_ids: [],
    product_type: "physical",
    brand: "",
    price: "0.00",
    compare_at_price: "",
    cost_price: "",
    currency: "USD",
    track_inventory: true,
    inventory_quantity: 0,
    low_stock_threshold: 5,
    allow_backorder: false,
    images: "",
    weight: "",
    weight_unit: "kg",
    requires_shipping: true,
    taxable: true,
    seo_title: "",
    seo_description: "",
  };
}

function itemToForm(section, item) {
  if (!item) return blankForm(section);
  const shared = {
    ...blankForm(section),
    ...item,
    translations: {
      en: { ...blankTranslations().en, ...(item.translations?.en || {}) },
      ar: { ...blankTranslations().ar, ...(item.translations?.ar || {}) },
    },
  };
  if (section === "products") {
    shared.images = Array.isArray(item.images) ? item.images.join("\n") : "";
    shared.tag_ids = Array.isArray(item.tag_ids) ? item.tag_ids : [];
  }
  return shared;
}

function translatedName(item, language = "en") {
  return item?.translations?.[language]?.name || item?.translations?.en?.name || item?.translations?.ar?.name || item?.slug || "Untitled";
}

function payloadFromForm(section, form) {
  const shared = {
    slug: form.slug.trim() || null,
    status: form.status,
    translations: {
      en: {
        name: form.translations.en.name.trim(),
        description: form.translations.en.description.trim(),
      },
      ar: {
        name: form.translations.ar.name.trim(),
        description: form.translations.ar.description.trim(),
      },
    },
  };
  if (section === "tags") return shared;
  if (section === "categories") {
    return { ...shared, parent_id: form.parent_id || null, sort_order: Number(form.sort_order || 0) };
  }
  return {
    ...shared,
    sku: form.sku.trim(),
    barcode: form.barcode.trim() || null,
    category_id: form.category_id || null,
    tag_ids: form.tag_ids,
    product_type: form.product_type,
    brand: form.brand.trim(),
    price: Number(form.price || 0),
    compare_at_price: form.compare_at_price === "" ? null : Number(form.compare_at_price),
    cost_price: form.cost_price === "" ? null : Number(form.cost_price),
    currency: form.currency.trim().toUpperCase(),
    track_inventory: form.track_inventory,
    inventory_quantity: Number(form.inventory_quantity || 0),
    low_stock_threshold: Number(form.low_stock_threshold || 0),
    allow_backorder: form.allow_backorder,
    images: form.images.split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
    weight: form.weight === "" ? null : Number(form.weight),
    weight_unit: form.weight_unit,
    requires_shipping: form.requires_shipping,
    taxable: form.taxable,
    seo_title: form.seo_title.trim(),
    seo_description: form.seo_description.trim(),
  };
}

function TranslationFields({ form, setForm, descriptions = false }) {
  const update = (locale, field, value) => {
    setForm((current) => ({
      ...current,
      translations: {
        ...current.translations,
        [locale]: { ...current.translations[locale], [field]: value },
      },
    }));
  };

  return (
    <fieldset className="ecommerce-form-section">
      <legend>Translations</legend>
      <div className="ecommerce-translation-grid">
        {[
          ["en", "English", "ltr"],
          ["ar", "Arabic", "rtl"],
        ].map(([locale, label, direction]) => (
          <div className="ecommerce-translation-card" key={locale} dir={direction}>
            <strong>{label}</strong>
            <label>
              Name
              <input
                value={form.translations[locale].name}
                onChange={(event) => update(locale, "name", event.target.value)}
                maxLength={200}
                required={locale === "en"}
              />
            </label>
            {descriptions && (
              <label>
                Description
                <textarea
                  value={form.translations[locale].description}
                  onChange={(event) => update(locale, "description", event.target.value)}
                  rows={4}
                  maxLength={10000}
                />
              </label>
            )}
          </div>
        ))}
      </div>
    </fieldset>
  );
}

function CommonFields({ form, setForm }) {
  return (
    <div className="ecommerce-field-grid">
      <label>
        Slug
        <input value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} placeholder="generated-from-name" />
      </label>
      <label>
        Status
        <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
      </label>
    </div>
  );
}

function ProductFields({ form, setForm, catalog }) {
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const selectedTagIds = Array.isArray(form.tag_ids) ? form.tag_ids : [];
  const toggleTag = (tagId) => update(
    "tag_ids",
    selectedTagIds.includes(tagId) ? selectedTagIds.filter((id) => id !== tagId) : [...selectedTagIds, tagId],
  );

  return (
    <>
      <fieldset className="ecommerce-form-section">
        <legend>Identity and organization</legend>
        <div className="ecommerce-field-grid ecommerce-field-grid--three">
          <label>SKU<input value={form.sku} onChange={(event) => update("sku", event.target.value)} required /></label>
          <label>Barcode<input value={form.barcode} onChange={(event) => update("barcode", event.target.value)} /></label>
          <label>Brand<input value={form.brand} onChange={(event) => update("brand", event.target.value)} /></label>
          <label>Product type<select value={form.product_type} onChange={(event) => update("product_type", event.target.value)}><option value="physical">Physical</option><option value="digital">Digital</option><option value="service">Service</option></select></label>
          <label>Category<select value={form.category_id} onChange={(event) => update("category_id", event.target.value)}><option value="">Uncategorized</option>{catalog.categories.map((category) => <option key={category.id} value={category.id}>{translatedName(category)}</option>)}</select></label>
          <label>Status<select value={form.status} onChange={(event) => update("status", event.target.value)}><option value="draft">Draft</option><option value="active">Active</option><option value="archived">Archived</option></select></label>
        </div>
        {catalog.tags.length > 0 && (
          <div className="ecommerce-tag-picker">
            <span>Tags</span>
            <div>{catalog.tags.map((tag) => <label key={tag.id}><input type="checkbox" checked={selectedTagIds.includes(tag.id)} onChange={() => toggleTag(tag.id)} />{translatedName(tag)}</label>)}</div>
          </div>
        )}
      </fieldset>

      <fieldset className="ecommerce-form-section">
        <legend>Pricing</legend>
        <div className="ecommerce-field-grid ecommerce-field-grid--four">
          <label>Price<input type="number" min="0" step="0.01" value={form.price} onChange={(event) => update("price", event.target.value)} required /></label>
          <label>Compare-at price<input type="number" min="0" step="0.01" value={form.compare_at_price} onChange={(event) => update("compare_at_price", event.target.value)} /></label>
          <label>Cost price<input type="number" min="0" step="0.01" value={form.cost_price} onChange={(event) => update("cost_price", event.target.value)} /></label>
          <label>Currency<input value={form.currency} onChange={(event) => update("currency", event.target.value)} maxLength={3} required /></label>
        </div>
      </fieldset>

      <fieldset className="ecommerce-form-section">
        <legend>Inventory</legend>
        <div className="ecommerce-field-grid ecommerce-field-grid--three">
          <label>Quantity<input type="number" min="0" value={form.inventory_quantity} onChange={(event) => update("inventory_quantity", event.target.value)} /></label>
          <label>Low-stock threshold<input type="number" min="0" value={form.low_stock_threshold} onChange={(event) => update("low_stock_threshold", event.target.value)} /></label>
          <label className="ecommerce-check"><input type="checkbox" checked={form.track_inventory} onChange={(event) => update("track_inventory", event.target.checked)} />Track inventory</label>
          <label className="ecommerce-check"><input type="checkbox" checked={form.allow_backorder} onChange={(event) => update("allow_backorder", event.target.checked)} />Allow backorders</label>
        </div>
      </fieldset>

      <fieldset className="ecommerce-form-section">
        <legend>Media, shipping, and tax</legend>
        <label>Image URLs (one per line)<textarea rows={3} value={form.images} onChange={(event) => update("images", event.target.value)} placeholder="https://example.com/product.jpg" /></label>
        <div className="ecommerce-field-grid ecommerce-field-grid--four">
          <label>Weight<input type="number" min="0" step="0.001" value={form.weight} onChange={(event) => update("weight", event.target.value)} /></label>
          <label>Unit<select value={form.weight_unit} onChange={(event) => update("weight_unit", event.target.value)}><option value="kg">kg</option><option value="g">g</option><option value="lb">lb</option><option value="oz">oz</option></select></label>
          <label className="ecommerce-check"><input type="checkbox" checked={form.requires_shipping} onChange={(event) => update("requires_shipping", event.target.checked)} />Requires shipping</label>
          <label className="ecommerce-check"><input type="checkbox" checked={form.taxable} onChange={(event) => update("taxable", event.target.checked)} />Taxable</label>
        </div>
      </fieldset>

      <fieldset className="ecommerce-form-section">
        <legend>SEO</legend>
        <label>SEO title<input value={form.seo_title} onChange={(event) => update("seo_title", event.target.value)} maxLength={200} /></label>
        <label>SEO description<textarea rows={3} value={form.seo_description} onChange={(event) => update("seo_description", event.target.value)} maxLength={500} /></label>
      </fieldset>
    </>
  );
}

export default function EcommercePage({ section = "products", user }) {
  const { i18n } = useTranslation(["dashboard"]);
  const config = SECTION_CONFIG[section] || SECTION_CONFIG.products;
  const Icon = config.icon;
  const language = i18n?.resolvedLanguage?.split("-")[0] || "en";
  const cacheScope = user?.id ? `user-${user.id}` : "authenticated";
  const [catalog, setCatalog] = useState({ tags: [], categories: [], products: [] });
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(() => blankForm(section));
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadCatalog = useCallback(async () => {
    setStatus("loading");
    setError("");
    try {
      const data = await fetchEcommerceCatalog({ scope: cacheScope });
      setCatalog({ tags: data?.tags || [], categories: data?.categories || [], products: data?.products || [] });
      setStatus("ready");
    } catch (loadError) {
      setError(loadError.message || "Could not load the catalog.");
      setStatus("error");
    }
  }, [cacheScope]);

  useEffect(() => {
    const timer = window.setTimeout(loadCatalog, 0);
    return () => window.clearTimeout(timer);
  }, [loadCatalog]);

  const items = useMemo(() => catalog[section] || [], [catalog, section]);
  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((item) => [translatedName(item, language), item.slug, item.sku, item.brand].filter(Boolean).some((value) => String(value).toLowerCase().includes(needle)));
  }, [items, language, query]);

  const openCreate = () => {
    setEditing(null);
    setForm(blankForm(section));
    setError("");
    setFormOpen(true);
  };
  const openEdit = (item) => {
    setEditing(item);
    setForm(itemToForm(section, item));
    setError("");
    setFormOpen(true);
  };
  const closeForm = () => { if (!saving) setFormOpen(false); };

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await saveEcommerceItem(
        section,
        editing?.id,
        payloadFromForm(section, form),
        { scope: cacheScope },
      );
      setFormOpen(false);
      await loadCatalog();
    } catch (saveError) {
      setError(saveError.message || "Could not save this item.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item) => {
    if (!window.confirm(`Delete ${translatedName(item, language)}?`)) return;
    setError("");
    try {
      await deleteEcommerceItem(section, item.id, { scope: cacheScope });
      await loadCatalog();
    } catch (deleteError) {
      setError(deleteError.message || "Could not delete this item.");
    }
  };

  const activeCount = items.filter((item) => item.status === "active").length;
  const draftCount = items.filter((item) => item.status === "draft").length;

  return (
    <section className="ecommerce-page" aria-labelledby={`ecommerce-${section}-title`}>
      <header className="ecommerce-page-header">
        <div>
          <span className="ecommerce-page-kicker">Ecommerce</span>
          <h1 id={`ecommerce-${section}-title`}>{config.title}</h1>
          <p>{config.description}</p>
        </div>
        <button type="button" className="ecommerce-primary-button" onClick={openCreate}><Plus size={18} />Add {config.singular}</button>
      </header>

      {error && <div className="ecommerce-error" role="alert">{error}</div>}

      <div className="ecommerce-summary-grid" aria-label="Catalog overview">
        {[[`Total ${config.title.toLowerCase()}`, items.length, Icon], ["Active", activeCount, CheckCircle2], ["Drafts", draftCount, Boxes]].map(([label, value, SummaryIcon]) => (
          <article className="ecommerce-summary-card" key={label}><span className="ecommerce-summary-icon"><SummaryIcon size={20} /></span><div><strong>{value}</strong><span>{label}</span></div></article>
        ))}
      </div>

      <section className="ecommerce-list-card" aria-labelledby={`ecommerce-${section}-list-title`}>
        <header className="ecommerce-list-header">
          <div><span>Ecommerce</span><h2 id={`ecommerce-${section}-list-title`}>{config.title}</h2></div>
          <label className="ecommerce-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${config.title.toLowerCase()}`} /></label>
        </header>

        {status === "loading" ? (
          <div className="ecommerce-loading"><LoaderCircle size={26} className="is-spinning" />Loading catalog…</div>
        ) : filteredItems.length === 0 ? (
          <div className="ecommerce-empty-state"><span><Icon size={27} /></span><h3>{query ? "No matching results" : `No ${config.title.toLowerCase()} yet`}</h3><p>{query ? "Try a different search." : `Select “Add ${config.singular}” to create the first one.`}</p></div>
        ) : (
          <div className="ecommerce-record-list">
            {filteredItems.map((item) => {
              const parent = section === "categories" ? catalog.categories.find((candidate) => candidate.id === item.parent_id) : null;
              const category = section === "products" ? catalog.categories.find((candidate) => candidate.id === item.category_id) : null;
              return (
                <article className="ecommerce-record" key={item.id}>
                  <span className="ecommerce-record-icon"><Icon size={18} /></span>
                  <div className="ecommerce-record-main"><strong>{translatedName(item, language)}</strong><span>{section === "products" ? `${item.sku} · ${item.currency} ${Number(item.price || 0).toFixed(2)}` : item.slug}</span></div>
                  <div className="ecommerce-record-meta">{parent ? `Under ${translatedName(parent, language)}` : category ? translatedName(category, language) : section === "categories" ? "Top level" : ""}</div>
                  <span className={`ecommerce-status is-${item.status}`}>{item.status}</span>
                  <div className="ecommerce-record-actions"><button type="button" onClick={() => openEdit(item)} aria-label={`Edit ${translatedName(item, language)}`}><Pencil size={16} /></button><button type="button" onClick={() => remove(item)} aria-label={`Delete ${translatedName(item, language)}`}><Trash2 size={16} /></button></div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {formOpen && (
        <div className="ecommerce-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeForm(); }}>
          <section className="ecommerce-modal" role="dialog" aria-modal="true" aria-labelledby="ecommerce-form-title">
            <header><div><span>{editing ? "Edit" : "Create"}</span><h2 id="ecommerce-form-title">{editing ? `Edit ${config.singular}` : `New ${config.singular}`}</h2></div><button type="button" onClick={closeForm} aria-label="Close"><X size={20} /></button></header>
            <form onSubmit={submit}>
              <TranslationFields form={form} setForm={setForm} descriptions={section !== "tags"} />
              {section === "tags" && <CommonFields form={form} setForm={setForm} />}
              {section === "categories" && <><CommonFields form={form} setForm={setForm} /><fieldset className="ecommerce-form-section"><legend>Hierarchy</legend><div className="ecommerce-field-grid"><label>Parent category<select value={form.parent_id || ""} onChange={(event) => setForm({ ...form, parent_id: event.target.value })}><option value="">Top level</option>{catalog.categories.filter((category) => category.id !== editing?.id).map((category) => <option key={category.id} value={category.id}>{translatedName(category, language)}</option>)}</select></label><label>Sort order<input type="number" min="0" value={form.sort_order} onChange={(event) => setForm({ ...form, sort_order: event.target.value })} /></label></div></fieldset></>}
              {section === "products" && <><div className="ecommerce-field-grid"><label>Slug<input value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} placeholder="generated-from-name" /></label></div><ProductFields form={form} setForm={setForm} catalog={catalog} /></>}
              {error && <div className="ecommerce-error" role="alert">{error}</div>}
              <footer><button type="button" className="ecommerce-secondary-button" onClick={closeForm}>Cancel</button><button type="submit" className="ecommerce-primary-button" disabled={saving}>{saving && <LoaderCircle size={17} className="is-spinning" />}{saving ? "Saving…" : "Save"}</button></footer>
            </form>
          </section>
        </div>
      )}
    </section>
  );
}
