import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Boxes,
  CheckCircle2,
  FolderTree,
  ImagePlus,
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

import AuthToast from "../AuthPages/AuthToast";

import {
  deleteEcommerceItem,
  fetchEcommerceCatalog,
  saveEcommerceItem,
  uploadEcommerceProductImage,
} from "../../services/ecommerceApi";
import { resolveMediaUrl } from "../../utils/media";
import { readEcommerceCatalogCacheSnapshot } from "./utils/ecommerceCatalogCache";

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
    description: "Manage product details, pricing, inventory, and images in one place.",
  },
};

const blankTranslations = () => ({
  en: { name: "", description: "" },
  ar: { name: "", description: "" },
});

function blankForm(section) {
  const shared = { slug: "", status: "", translations: blankTranslations() };
  if (section === "tags") return shared;
  if (section === "categories") return { ...shared, parent_id: "", sort_order: "" };
  return {
    ...shared,
    sku: "",
    barcode: "",
    category_id: "",
    tag_ids: [],
    product_type: "",
    brand: "",
    price: "",
    discount_price: "",
    currency: "",
    track_inventory: false,
    inventory_quantity: "",
    low_stock_threshold: "",
    allow_backorder: false,
    images: [],
    weight: "",
    weight_unit: "",
    requires_shipping: false,
    taxable: false,
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
    shared.images = Array.isArray(item.images) ? item.images.slice(0, 4) : [];
    shared.tag_ids = Array.isArray(item.tag_ids) ? item.tag_ids : [];
    const hasDiscount = item.compare_at_price !== null && item.compare_at_price !== undefined && item.compare_at_price !== "";
    shared.price = hasDiscount ? item.compare_at_price : (item.price ?? "");
    shared.discount_price = hasDiscount ? (item.price ?? "") : "";
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
  const discountedPrice = form.discount_price === "" ? null : Number(form.discount_price);
  return {
    ...shared,
    sku: form.sku.trim(),
    barcode: form.barcode.trim() || null,
    category_id: form.category_id || null,
    tag_ids: form.tag_ids,
    product_type: form.product_type,
    brand: form.brand.trim(),
    price: discountedPrice ?? Number(form.price || 0),
    compare_at_price: discountedPrice === null ? null : Number(form.price || 0),
    cost_price: form.cost_price == null || form.cost_price === "" ? null : Number(form.cost_price),
    currency: form.currency.trim().toUpperCase(),
    track_inventory: form.track_inventory,
    inventory_quantity: Number(form.inventory_quantity || 0),
    low_stock_threshold: Number(form.low_stock_threshold || 0),
    allow_backorder: form.allow_backorder,
    images: Array.isArray(form.images) ? form.images.slice(0, 4) : [],
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
        <input value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} required />
      </label>
      <label>
        Status
        <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })} required><option value="" disabled>Choose status</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option><option value="inactive">Inactive</option>
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

  const [imageUploadBusy, setImageUploadBusy] = useState(false);
  const [imageUploadError, setImageUploadError] = useState("");
  const [imageDragActive, setImageDragActive] = useState(false);
  const productImages = Array.isArray(form.images) ? form.images : [];

  const addProductImages = async (fileList) => {
    const files = Array.from(fileList || []);
    setImageUploadError("");
    if (!files.length) return;
    if (files.length > 4 - productImages.length) {
      setImageUploadError(`You can add ${4 - productImages.length} more image${4 - productImages.length === 1 ? "" : "s"}.`);
      return;
    }
    if (files.some((file) => !["image/png", "image/jpeg", "image/webp"].includes(file.type))) {
      setImageUploadError("Choose PNG, JPG, or WebP images only.");
      return;
    }
    setImageUploadBusy(true);
    try {
      for (const file of files) {
        const imageUrl = await uploadEcommerceProductImage(file);
        if (!imageUrl) throw new Error("The image upload did not return a usable image.");
        setForm((current) => ({
          ...current,
          images: [...(Array.isArray(current.images) ? current.images : []), imageUrl].slice(0, 4),
        }));
      }
    } catch (uploadError) {
      setImageUploadError(uploadError.message || "Could not upload this image.");
    } finally {
      setImageUploadBusy(false);
    }
  };

  const uploadProductImages = (event) => {
    const input = event.currentTarget;
    const files = input.files;
    input.value = "";
    void addProductImages(files);
  };

  const dropProductImages = (event) => {
    event.preventDefault();
    setImageDragActive(false);
    if (!imageUploadBusy && productImages.length < 4) void addProductImages(event.dataTransfer.files);
  };
  const removeProductImage = (imageUrl) => {
    setForm((current) => ({
      ...current,
      images: (Array.isArray(current.images) ? current.images : []).filter((value) => value !== imageUrl),
    }));
    setImageUploadError("");
  };

  return (
    <>
      <fieldset className="ecommerce-form-section">
        <legend>Identity and organization</legend>
        <div className="ecommerce-field-grid ecommerce-field-grid--three">
          <label>
            <span className="ecommerce-field-label">SKU <span className="ecommerce-field-optional">Automatic</span></span>
            <input aria-label="SKU" aria-describedby="product-sku-help" value={form.sku} onChange={(event) => update("sku", event.target.value)} />
            <small id="product-sku-help" className="ecommerce-field-help">Leave empty and Madar will generate a unique product code.</small>
          </label>
          <label>
            <span className="ecommerce-field-label">Barcode <span className="ecommerce-field-optional">Optional</span></span>
            <input aria-label="Barcode" aria-describedby="product-barcode-help" value={form.barcode} onChange={(event) => update("barcode", event.target.value)} />
            <small id="product-barcode-help" className="ecommerce-field-help">Enter the printed barcode only when the product has one.</small>
          </label>
          <label>Brand<input value={form.brand} onChange={(event) => update("brand", event.target.value)} /></label>
          <label>Product type<select value={form.product_type} onChange={(event) => update("product_type", event.target.value)} required><option value="" disabled>Choose product type</option><option value="physical">Physical</option><option value="digital">Digital</option><option value="service">Service</option></select></label>
          <label>Category<select value={form.category_id} onChange={(event) => update("category_id", event.target.value)}><option value="">Uncategorized</option>{catalog.categories.map((category) => <option key={category.id} value={category.id}>{translatedName(category)}</option>)}</select></label>
          <label>Status<select value={form.status} onChange={(event) => update("status", event.target.value)} required><option value="" disabled>Choose status</option><option value="draft">Draft</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="archived">Archived</option></select></label>
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
        <div className="ecommerce-field-grid ecommerce-field-grid--three">
          <label>Regular price<input type="number" min="0" step="0.01" value={form.price} onChange={(event) => update("price", event.target.value)} required /></label>
          <label><span className="ecommerce-field-label">Discounted price <span className="ecommerce-field-optional">Optional</span></span><input type="number" min="0" max={form.price || undefined} step="0.01" value={form.discount_price} onChange={(event) => update("discount_price", event.target.value)} /><small className="ecommerce-field-help">Leave empty when the product is not on sale.</small></label>
          <label>Currency<select value={form.currency} onChange={(event) => update("currency", event.target.value)} required><option value="" disabled>Choose currency</option><option value="ILS">Israeli shekel (ILS)</option><option value="USD">US dollar (USD)</option><option value="JOD">Jordanian dinar (JOD)</option><option value="EUR">Euro (EUR)</option></select></label>
        </div>
      </fieldset>

      <fieldset className="ecommerce-form-section">
        <legend>Inventory</legend>
        <div className="ecommerce-field-grid ecommerce-field-grid--three">
          <label>Current stock<input type="number" min="0" value={form.inventory_quantity} required onChange={(event) => update("inventory_quantity", event.target.value)} /><small className="ecommerce-field-help">How many items are available now.</small></label>
          <label>Warn me when stock reaches<input type="number" min="0" value={form.low_stock_threshold} required onChange={(event) => update("low_stock_threshold", event.target.value)} /><small className="ecommerce-field-help">Madar will show a low-stock warning at this number or below.</small></label>
          <div className="ecommerce-check-row"><label className="ecommerce-check"><input type="checkbox" checked={form.track_inventory} onChange={(event) => update("track_inventory", event.target.checked)} /><span>Track inventory</span></label>
          <label className="ecommerce-check"><input type="checkbox" checked={form.allow_backorder} onChange={(event) => update("allow_backorder", event.target.checked)} /><span className="ecommerce-check-copy"><strong>Let customers order when sold out</strong><small>Customers can still place an order when stock reaches zero.</small></span></label></div>
        </div>
      </fieldset>

      <fieldset className="ecommerce-form-section ecommerce-form-section--media">
        <legend>Images and weight</legend>
        <div className="ecommerce-product-images">
          <div className="ecommerce-product-images-header">
            <div><strong>Product gallery</strong><span>The first image will be the main product image.</span></div>
            <span className="ecommerce-product-image-count">{productImages.length} of 4</span>
          </div>
          <div className={`ecommerce-product-image-grid${productImages.length ? " has-images" : ""}`}>
            {productImages.map((imageUrl, index) => (
              <figure key={imageUrl}>
                <img src={resolveMediaUrl(imageUrl)} alt={`Product image ${index + 1}`} />
                <figcaption>{index === 0 ? "Main image" : `Image ${index + 1}`}</figcaption>
                <button type="button" onClick={() => removeProductImage(imageUrl)} aria-label={`Remove product image ${index + 1}`}><X size={15} /></button>
              </figure>
            ))}
            {productImages.length < 4 && (
              <label
                className={`ecommerce-product-image-upload${imageUploadBusy ? " is-busy" : ""}${imageDragActive ? " is-dragging" : ""}`}
                onDragEnter={(event) => { event.preventDefault(); setImageDragActive(true); }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={() => setImageDragActive(false)}
                onDrop={dropProductImages}
              >
                <span className="ecommerce-product-image-upload-icon"><ImagePlus size={23} /></span>
                <strong>{imageUploadBusy ? "Uploading images…" : productImages.length ? "Add another image" : "Add product images"}</strong>
                <span>{imageUploadBusy ? "Please keep this window open." : "Drag and drop, or click to browse"}</span>
                <small>PNG, JPG, or WebP · 25 MB maximum</small>
                <input type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={imageUploadBusy} aria-label="Upload product images" onChange={uploadProductImages} />
              </label>
            )}
          </div>
          {imageUploadError && <div className="ecommerce-error" role="alert">{imageUploadError}</div>}
        </div>
        <div className="ecommerce-field-grid ecommerce-field-grid--two">
          <label>Weight<input type="number" min="0" step="0.001" value={form.weight} onChange={(event) => update("weight", event.target.value)} /></label>
          <label>Unit<select value={form.weight_unit} onChange={(event) => update("weight_unit", event.target.value)} required><option value="" disabled>Choose unit</option><option value="kg">kg</option><option value="g">g</option><option value="lb">lb</option><option value="oz">oz</option></select></label>

        </div>
      </fieldset>


    </>
  );
}

function requiredFieldLabel(field) {
  const explicitLabel = field.getAttribute("aria-label");
  if (explicitLabel) return explicitLabel;
  const label = field.closest("label");
  const directText = Array.from(label?.childNodes || [])
    .find((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
    ?.textContent.trim();
  const labelText = directText || label?.querySelector(":scope > span")?.textContent?.trim() || "this field";
  const languageCard = field.closest(".ecommerce-translation-card")?.querySelector(":scope > strong")?.textContent?.trim();
  return languageCard && labelText === "Name" ? `${languageCard} name` : labelText;
}

function EcommercePageSkeleton() {
  return (
    <div className="ecommerce-page-skeleton" role="status" aria-label="Loading online store catalog">
      <header><div><i /><i /><i /></div><i /></header>
      <section>{Array.from({ length: 3 }, (_, index) => <i key={index} />)}</section>
      <article><header><div><i /><i /></div><i /></header>{Array.from({ length: 5 }, (_, index) => <i key={index} />)}</article>
    </div>
  );
}

export default function EcommercePage({ section = "products", user }) {
  const { i18n } = useTranslation(["dashboard"]);
  const config = SECTION_CONFIG[section] || SECTION_CONFIG.products;
  const Icon = config.icon;
  const language = i18n?.resolvedLanguage?.split("-")[0] || "en";
  const cacheScope = user?.id ? `user-${user.id}` : "authenticated";
  const initialCatalogSnapshot = useMemo(() => readEcommerceCatalogCacheSnapshot(cacheScope), [cacheScope]);
  const [catalog, setCatalog] = useState(() => initialCatalogSnapshot?.catalog || { tags: [], categories: [], products: [] });
  const [status, setStatus] = useState(() => initialCatalogSnapshot ? "ready" : "loading");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(() => blankForm(section));
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = useCallback(({ type = "error", title, message }) => {
    setToast({ id: Date.now(), type, title, message });
  }, []);

  const loadCatalog = useCallback(async () => {
    const cached = readEcommerceCatalogCacheSnapshot(cacheScope);
    if (cached) {
      setCatalog(cached.catalog);
      setStatus("ready");
    } else {
      setStatus("loading");
    }
    try {
      const data = await fetchEcommerceCatalog({ scope: cacheScope, force: Boolean(cached?.isStale) });
      setCatalog({ tags: data?.tags || [], categories: data?.categories || [], products: data?.products || [] });
      setStatus("ready");
    } catch (loadError) {
      if (cached) {
        setStatus("ready");
        return;
      }
      const message = loadError.message || "Could not load the catalog.";
      setStatus("error");
      showToast({ type: "error", title: "Could not load online store", message });
    }
  }, [cacheScope, showToast]);

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
    setFormOpen(true);
  };
  const openEdit = (item) => {
    setEditing(item);
    setForm(itemToForm(section, item));
    setFormOpen(true);
  };
  const closeForm = () => { if (!saving) setFormOpen(false); };

  const submit = async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const invalidField = Array.from(formElement.elements)
      .find((field) => field.willValidate && !field.validity.valid);
    if (invalidField) {
      const fieldLabel = requiredFieldLabel(invalidField);
      const action = invalidField.tagName === "SELECT" ? "Choose" : "Enter";
      showToast({
        type: "error",
        title: "Complete the required fields",
        message: `${action} ${fieldLabel.toLowerCase()} before saving.`,
      });
      invalidField.focus({ preventScroll: true });
      invalidField.scrollIntoView?.({ behavior: "smooth", block: "center" });
      return;
    }

    const wasEditing = Boolean(editing?.id);
    setSaving(true);
    try {
      const result = await saveEcommerceItem(
        section,
        editing?.id,
        payloadFromForm(section, form),
        { scope: cacheScope },
      );
      const savedItem = result?.[config.singular];
      if (savedItem?.id) {
        setCatalog((current) => ({
          ...current,
          [section]: current[section].some((item) => item.id === savedItem.id)
            ? current[section].map((item) => item.id === savedItem.id ? savedItem : item)
            : [savedItem, ...current[section]],
        }));
      }
      setFormOpen(false);
      showToast({
        type: "success",
        title: `${config.singular[0].toUpperCase()}${config.singular.slice(1)} saved`,
        message: wasEditing ? "Your changes were saved successfully." : `The new ${config.singular} was created successfully.`,
      });
    } catch (saveError) {
      const message = saveError.message || `Could not save this ${config.singular}.`;
      showToast({ type: "error", title: `Could not save ${config.singular}`, message });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item) => {
    if (!window.confirm(`Delete ${translatedName(item, language)}?`)) return;
    try {
      await deleteEcommerceItem(section, item.id, { scope: cacheScope });
      setCatalog((current) => ({
        ...current,
        [section]: current[section].filter((candidate) => candidate.id !== item.id),
      }));
      showToast({
        type: "success",
        title: `${config.singular[0].toUpperCase()}${config.singular.slice(1)} deleted`,
        message: `${translatedName(item, language)} was removed.`,
      });
    } catch (deleteError) {
      const message = deleteError.message || `Could not delete this ${config.singular}.`;
      showToast({ type: "error", title: `Could not delete ${config.singular}`, message });
    }
  };
  const activeCount = items.filter((item) => item.status === "active").length;
  const inactiveCount = items.filter((item) => item.status === "inactive").length;

  if (status === "loading") {
    return <section className="ecommerce-page"><EcommercePageSkeleton /></section>;
  }

  return (
    <section className="ecommerce-page" aria-labelledby={`ecommerce-${section}-title`}>
      <header className="ecommerce-page-header app-page-intro">
        <div>
          <h1 id={`ecommerce-${section}-title`}>{config.title}</h1>
          <p>{config.description}</p>
        </div>
        <button type="button" className="ecommerce-primary-button" onClick={openCreate}><Plus size={18} />Add {config.singular}</button>
      </header>

      <div className="ecommerce-summary-grid" aria-label="Catalog overview">
        {[[`Total ${config.title.toLowerCase()}`, items.length, Icon], ["Active", activeCount, CheckCircle2], ["Inactive", inactiveCount, Boxes]].map(([label, value, SummaryIcon]) => (
          <article className="ecommerce-summary-card" key={label}><span className="ecommerce-summary-icon"><SummaryIcon size={20} /></span><div><strong>{value}</strong><span>{label}</span></div></article>
        ))}
      </div>

      <section className="ecommerce-list-card" aria-labelledby={`ecommerce-${section}-list-title`}>
        <header className="ecommerce-list-header">
          <div><h2 id={`ecommerce-${section}-list-title`}>Manage {config.title.toLowerCase()}</h2></div>
          <label className="ecommerce-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${config.title.toLowerCase()}`} /></label>
        </header>

        {filteredItems.length === 0 ? (
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
            <form onSubmit={submit} noValidate>
              <TranslationFields form={form} setForm={setForm} descriptions={section !== "tags"} />
              {section === "tags" && <CommonFields form={form} setForm={setForm} />}
              {section === "categories" && <><CommonFields form={form} setForm={setForm} /><fieldset className="ecommerce-form-section"><legend>Hierarchy</legend><div className="ecommerce-field-grid"><label>Parent category<select value={form.parent_id || ""} onChange={(event) => setForm({ ...form, parent_id: event.target.value })}><option value="">Top level</option>{catalog.categories.filter((category) => category.id !== editing?.id).map((category) => <option key={category.id} value={category.id}>{translatedName(category, language)}</option>)}</select></label><label><span>Display position</span><input type="number" min="0" step="1" inputMode="numeric" value={form.sort_order} required aria-label="Display position" aria-describedby="category-display-position-help" onChange={(event) => setForm({ ...form, sort_order: event.target.value })} /><small id="category-display-position-help" className="ecommerce-field-help">Lower numbers appear first. Use 0 for the first position.</small></label></div></fieldset></>}
              {section === "products" && <><div className="ecommerce-field-grid"><label>Slug<input value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} required /></label></div><ProductFields form={form} setForm={setForm} catalog={catalog} /></>}
              <footer><button type="button" className="ecommerce-secondary-button" onClick={closeForm}>Cancel</button><button type="submit" className="ecommerce-primary-button" disabled={saving}>{saving && <LoaderCircle size={17} className="is-spinning" />}{saving ? "Saving…" : "Save"}</button></footer>
            </form>
          </section>
        </div>
      )}
      <AuthToast
        key={toast?.id}
        type={toast?.type}
        title={toast?.title}
        message={toast?.message}
        dir={language === "ar" ? "rtl" : "ltr"}
        onDismiss={() => setToast(null)}
      />    </section>
  );
}
