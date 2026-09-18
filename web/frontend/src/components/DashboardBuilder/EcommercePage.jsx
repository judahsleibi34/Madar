import { getEcommerceCacheScope } from "./utils/ecommerceAdminCache";
import { CatalogSkeleton } from "./CommerceLoadingLayouts";
import { notifyCommerceAction } from "../../utils/commerceActionToast";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  Boxes,
  CheckCircle2,
  Clock3,
  FolderTree,
  ImagePlus,
  LoaderCircle,
  Package,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  Tag,
  Trash2,
  X,
} from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import { EcommerceProductEditor } from "./EcommerceProductEditorPage";

import {
  deleteEcommerceItem,
  fetchEcommerceCatalog,
  saveEcommerceItem,
  uploadEcommerceProductImage,
} from "../../services/ecommerceApi";
import { resolveMediaUrl } from "../../utils/media";
import { formatCommerceMoney, useCommerceI18n } from "../../utils/commerceI18n";
import { commerceProductStock } from "../../utils/commerceStock";
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

const SUMMARY_VISIBILITY_STORAGE_KEY = "madar-ecommerce-summary-cards-v1";

function readHiddenSummaryCards(storageKey) {
  try {
    const value = JSON.parse(window.localStorage.getItem(storageKey) || "[]");
    return Array.isArray(value) ? value.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

const blankTranslations = () => ({
  en: { name: "", description: "" },
  ar: { name: "", description: "" },
});

function ecommerceSlug(value = "") {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

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
    slug: ecommerceSlug(form.slug || form.translations.en.name) || null,
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

function AutoGrowingTextarea({ value, onChange, ...props }) {
  const textareaRef = useRef(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const minimumHeight = 48;
    const maximumHeight = 144;
    textarea.style.height = "auto";
    const contentHeight = Math.max(textarea.scrollHeight, minimumHeight);
    textarea.style.height = `${Math.min(contentHeight, maximumHeight)}px`;
    textarea.style.overflowY = contentHeight > maximumHeight ? "auto" : "hidden";
  }, [value]);

  return <textarea ref={textareaRef} value={value} onChange={onChange} {...props} />;
}

function TranslationFields({ form, setForm, descriptions = false, autoGenerateSlug = false, t }) {
  const update = (locale, field, value) => {
    setForm((current) => ({
      ...current,
      ...(autoGenerateSlug && locale === "en" && field === "name" ? { slug: ecommerceSlug(value) } : {}),
      translations: {
        ...current.translations,
        [locale]: { ...current.translations[locale], [field]: value },
      },
    }));
  };

  return (
    <fieldset className="ecommerce-form-section" aria-label={t("commerce:admin.translations")}>
      <div className="ecommerce-translation-grid">
        {[
          ["en", t("commerce:admin.english"), "ltr"],
          ["ar", t("commerce:admin.arabic"), "rtl"],
        ].map(([locale, label, direction]) => (
          <div className="ecommerce-translation-card" key={locale} dir={direction}>
            <strong>{label}</strong>
            <label>
              {t("commerce:admin.name")}
              <input
                value={form.translations[locale].name}
                onChange={(event) => update(locale, "name", event.target.value)}
                maxLength={200}
                required={locale === "en"}
              />
            </label>
            {descriptions && (
              <label>
                {t("commerce:admin.description")}
                <AutoGrowingTextarea
                  value={form.translations[locale].description}
                  onChange={(event) => update(locale, "description", event.target.value)}
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

function CommonFields({ form, setForm, onSlugChange, t }) {
  return (
    <div className="ecommerce-field-grid">
      <label>
        {t("commerce:merchant.slug")}
        <input value={form.slug} onChange={(event) => { onSlugChange?.(); setForm((current) => ({ ...current, slug: event.target.value })); }} required />
      </label>
      <label>
        {t("commerce:common.status")}
        <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })} required><option value="" disabled>{t("commerce:admin.chooseStatus")}</option>
          <option value="draft">{t("commerce:common.draft")}</option>
          <option value="active">{t("commerce:common.active")}</option><option value="inactive">{t("commerce:common.inactive")}</option>
          <option value="archived">{t("commerce:common.archived")}</option>
        </select>
      </label>
    </div>
  );
}

function ProductFields({ form, setForm, catalog, t, language }) {
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
      setImageUploadError(t("commerce:errors.imageLimit", { count: 4 - productImages.length }));
      notifyCommerceAction({ type: "error", title: t("commerce:errors.uploadImage"), message: t("commerce:errors.imageLimit", { count: 4 - productImages.length }) });
      return;
    }
    if (files.some((file) => !["image/png", "image/jpeg", "image/webp"].includes(file.type))) {
      setImageUploadError(t("commerce:errors.invalidImageType"));
      notifyCommerceAction({ type: "error", title: t("commerce:errors.uploadImage"), message: t("commerce:errors.invalidImageType") });
      return;
    }
    setImageUploadBusy(true);
    try {
      for (const file of files) {
        const imageUrl = await uploadEcommerceProductImage(file);
        if (!imageUrl) throw new Error(t("commerce:errors.unusableImage"));
        setForm((current) => ({
          ...current,
          images: [...(Array.isArray(current.images) ? current.images : []), imageUrl].slice(0, 4),
        }));
      }
      notifyCommerceAction({ type: "success", title: t("commerce:feedback.mediaUploaded"), message: t("commerce:feedback.mediaUploadedBody") });
    } catch {
      setImageUploadError(t("commerce:errors.uploadImage"));
      notifyCommerceAction({ type: "error", title: t("commerce:errors.uploadImage"), message: t("commerce:admin.tryAgain") });
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
        <legend>{t("commerce:admin.identityOrganization")}</legend>
        <div className="ecommerce-field-grid ecommerce-field-grid--three">
          <label>
            <span className="ecommerce-field-label">{t("commerce:common.sku")} <span className="ecommerce-field-optional">{t("commerce:admin.automatic")}</span></span>
            <input aria-label="SKU" aria-describedby="product-sku-help" value={form.sku} onChange={(event) => update("sku", event.target.value)} />
            <small id="product-sku-help" className="ecommerce-field-help">{t("commerce:admin.skuHelp")}</small>
          </label>
          <label>
            <span className="ecommerce-field-label">{t("commerce:common.barcode")} <span className="ecommerce-field-optional">{t("commerce:admin.optional")}</span></span>
            <input aria-label="Barcode" aria-describedby="product-barcode-help" value={form.barcode} onChange={(event) => update("barcode", event.target.value)} />
            <small id="product-barcode-help" className="ecommerce-field-help">{t("commerce:admin.barcodeHelp")}</small>
          </label>
          <label>{t("commerce:merchant.brand")}<input value={form.brand} onChange={(event) => update("brand", event.target.value)} /></label>
          <label>{t("commerce:admin.productType")}<select value={form.product_type} onChange={(event) => update("product_type", event.target.value)} required><option value="" disabled>{t("commerce:admin.chooseProductType")}</option><option value="physical">{t("commerce:admin.physical")}</option><option value="digital">{t("commerce:admin.digital")}</option><option value="service">{t("commerce:admin.service")}</option></select></label>
          <label>{t("commerce:merchant.category")}<select value={form.category_id} onChange={(event) => update("category_id", event.target.value)}><option value="">{t("commerce:admin.uncategorized")}</option>{catalog.categories.map((category) => <option key={category.id} value={category.id}>{translatedName(category, language)}</option>)}</select></label>
          <label>{t("commerce:common.status")}<select value={form.status} onChange={(event) => update("status", event.target.value)} required><option value="" disabled>{t("commerce:admin.chooseStatus")}</option><option value="draft">{t("commerce:common.draft")}</option><option value="active">{t("commerce:common.active")}</option><option value="inactive">{t("commerce:common.inactive")}</option><option value="archived">{t("commerce:common.archived")}</option></select></label>
        </div>
        {catalog.tags.length > 0 && (
          <div className="ecommerce-tag-picker">
            <span>{t("commerce:common.tags")}</span>
            <div>{catalog.tags.map((tag) => <label key={tag.id}><input type="checkbox" checked={selectedTagIds.includes(tag.id)} onChange={() => toggleTag(tag.id)} />{translatedName(tag, language)}</label>)}</div>
          </div>
        )}
      </fieldset>

      <fieldset className="ecommerce-form-section">
        <legend>{t("commerce:merchant.pricing")}</legend>
        <div className="ecommerce-field-grid ecommerce-field-grid--three">
          <label>{t("commerce:admin.regularPrice")}<input type="number" min="0" step="0.01" value={form.price} onChange={(event) => update("price", event.target.value)} required /></label>
          <label><span className="ecommerce-field-label">{t("commerce:admin.discountedPrice")} <span className="ecommerce-field-optional">{t("commerce:admin.optional")}</span></span><input type="number" min="0" max={form.price || undefined} step="0.01" value={form.discount_price} onChange={(event) => update("discount_price", event.target.value)} /><small className="ecommerce-field-help">{t("commerce:admin.discountHelp")}</small></label>
          <label>{t("commerce:common.currency")}<select value={form.currency} onChange={(event) => update("currency", event.target.value)} required><option value="" disabled>{t("commerce:admin.chooseCurrency")}</option><option value="ILS">{t("commerce:admin.ils")}</option><option value="USD">{t("commerce:admin.usd")}</option><option value="JOD">{t("commerce:admin.jod")}</option><option value="EUR">{t("commerce:admin.eur")}</option></select></label>
        </div>
      </fieldset>

      <fieldset className="ecommerce-form-section">
        <legend>{t("commerce:merchant.inventory")}</legend>
        <div className="ecommerce-field-grid ecommerce-field-grid--three">
          <label>{t("commerce:merchant.currentStock")}<input type="number" min="0" value={form.inventory_quantity} required onChange={(event) => update("inventory_quantity", event.target.value)} /><small className="ecommerce-field-help">{t("commerce:admin.stockHelp")}</small></label>
          <label>{t("commerce:merchant.lowThreshold")}<input type="number" min="0" value={form.low_stock_threshold} required onChange={(event) => update("low_stock_threshold", event.target.value)} /><small className="ecommerce-field-help">{t("commerce:admin.thresholdHelp")}</small></label>
          <div className="ecommerce-check-row"><label className="ecommerce-check"><input type="checkbox" checked={form.track_inventory} onChange={(event) => update("track_inventory", event.target.checked)} /><span>{t("commerce:merchant.trackInventory")}</span></label>
          <label className="ecommerce-check"><input type="checkbox" checked={form.allow_backorder} onChange={(event) => update("allow_backorder", event.target.checked)} /><span className="ecommerce-check-copy"><strong>{t("commerce:merchant.allowBackorder")}</strong><small>{t("commerce:admin.backorderHelp")}</small></span></label></div>
        </div>
      </fieldset>

      <fieldset className="ecommerce-form-section ecommerce-form-section--media">
        <legend>{t("commerce:admin.imagesWeight")}</legend>
        <div className="ecommerce-product-images">
          <div className="ecommerce-product-images-header">
            <div><strong>{t("commerce:admin.productGallery")}</strong><span>{t("commerce:admin.galleryHelp")}</span></div>
            <span className="ecommerce-product-image-count">{t("commerce:admin.imageCount", { count: productImages.length })}</span>
          </div>
          <div className={`ecommerce-product-image-grid${productImages.length ? " has-images" : ""}`}>
            {productImages.map((imageUrl, index) => (
              <figure key={imageUrl}>
                <img src={resolveMediaUrl(imageUrl)} alt={t("commerce:admin.productImage", { count: index + 1 })} />
                <figcaption>{index === 0 ? t("commerce:admin.mainImage") : t("commerce:admin.image", { count: index + 1 })}</figcaption>
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
                <strong>{imageUploadBusy ? t("commerce:merchant.uploading") : productImages.length ? t("commerce:admin.addAnotherImage") : t("commerce:merchant.addImages")}</strong>
                <span>{imageUploadBusy ? t("commerce:admin.keepOpen") : t("commerce:admin.dragBrowse")}</span>
                <small>{t("commerce:admin.imageRequirements")}</small>
                <input type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={imageUploadBusy} aria-label="Upload product images" onChange={uploadProductImages} />
              </label>
            )}
          </div>
          {imageUploadError && <div className="ecommerce-error" role="alert">{imageUploadError}</div>}
        </div>
        <div className="ecommerce-field-grid ecommerce-field-grid--two">
          <label>{t("commerce:admin.weight")}<input type="number" min="0" step="0.001" value={form.weight} onChange={(event) => update("weight", event.target.value)} /></label>
          <label>{t("commerce:admin.unit")}<select value={form.weight_unit} onChange={(event) => update("weight_unit", event.target.value)} required><option value="" disabled>{t("commerce:admin.chooseUnit")}</option><option value="kg">kg</option><option value="g">g</option><option value="lb">lb</option><option value="oz">oz</option></select></label>

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

export default function EcommercePage({ section = "products", user }) {
  const { t, locale: language, direction } = useCommerceI18n();
  const config = SECTION_CONFIG[section] || SECTION_CONFIG.products;
  const Icon = config.icon;
  const cacheScope = getEcommerceCacheScope(user);
  const summaryStorageKey = `${SUMMARY_VISIBILITY_STORAGE_KEY}:${cacheScope}:${section}`;
  const summaryCustomizerRef = useRef(null);
  const catalogRequestVersion = useRef(0);
  const [summaryCustomizerOpen, setSummaryCustomizerOpen] = useState(false);
  const [hiddenSummaryCardIds, setHiddenSummaryCardIds] = useState(() => readHiddenSummaryCards(summaryStorageKey));
  const initialCatalogSnapshot = useMemo(() => readEcommerceCatalogCacheSnapshot(cacheScope), [cacheScope]);
  const [catalog, setCatalog] = useState(() => initialCatalogSnapshot?.catalog || { tags: [], categories: [], products: [], stock_summary: { low_stock: 0, out_of_stock: 0 } });
  const [status, setStatus] = useState(() => initialCatalogSnapshot ? "ready" : "loading");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null);
  const [stockFilter, setStockFilter] = useState("all");
  const [form, setForm] = useState(() => blankForm(section));
  const [formOpen, setFormOpen] = useState(false);
  const [productEditorOpen, setProductEditorOpen] = useState(false);
  const [productEditorId, setProductEditorId] = useState(null);
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    try {
      window.localStorage.setItem(summaryStorageKey, JSON.stringify(hiddenSummaryCardIds));
    } catch {
      // Keep the current selection for this session if storage is unavailable.
    }
  }, [hiddenSummaryCardIds, summaryStorageKey]);

  useEffect(() => {
    if (!summaryCustomizerOpen) return undefined;
    const closeOnOutsidePress = (event) => {
      if (!summaryCustomizerRef.current?.contains(event.target)) setSummaryCustomizerOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setSummaryCustomizerOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePress);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePress);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [summaryCustomizerOpen]);

  useEffect(() => {
    if (!productEditorOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setProductEditorOpen(false);
    };
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [productEditorOpen]);

  const showToast = useCallback(({ type = "error", title, message }) => {
    setToast({ id: Date.now(), type, title, message });
  }, []);

  const loadCatalog = useCallback(async () => {
    const version = ++catalogRequestVersion.current;
    const cached = readEcommerceCatalogCacheSnapshot(cacheScope);
    if (cached) {
      setCatalog(cached.catalog);
      setStatus("ready");
    } else {
      setStatus("loading");
    }
    try {
      const data = await fetchEcommerceCatalog({ scope: cacheScope, force: Boolean(cached?.isStale) });
      if (version !== catalogRequestVersion.current) return;
      setCatalog({ tags: data?.tags || [], categories: data?.categories || [], products: data?.products || [], stock_summary: data?.stock_summary || { low_stock: 0, out_of_stock: 0 }, commerce_currency: data?.commerce_currency || null });
      setStatus("ready");
    } catch {
      if (version !== catalogRequestVersion.current) return;
      if (cached) {
        setStatus("ready");
        showToast({ type: "error", title: t("commerce:admin.loadCommerce"), message: t("commerce:feedback.cachedCatalog") });
        return;
      }
      const message = t("commerce:admin.loadCatalog");
      setStatus("error");
      showToast({ type: "error", title: t("commerce:admin.loadCommerce"), message });
    }
  }, [cacheScope, showToast, t]);

  useEffect(() => {
    const timer = window.setTimeout(loadCatalog, 0);
    return () => { window.clearTimeout(timer); catalogRequestVersion.current += 1; };
  }, [loadCatalog]);

  const items = useMemo(() => catalog[section] || [], [catalog, section]);
  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      const matchesSearch = !needle || [translatedName(item, language), item.slug, item.sku, item.brand].filter(Boolean).some((value) => String(value).toLowerCase().includes(needle));
      const matchesStock = section !== "products" || stockFilter === "all" || (stockFilter === "low_stock" ? item.has_low_stock : item.has_out_of_stock);
      return matchesSearch && matchesStock;
    });
  }, [items, language, query, section, stockFilter]);

  const openCreate = () => {
    setEditing(null);
    setForm(blankForm(section));
    setSlugManuallyEdited(false);
    setFormOpen(true);
  };
  const openEdit = (item) => {
    setEditing(item);
    setForm(itemToForm(section, item));
    setSlugManuallyEdited(true);
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
      const action = invalidField.tagName === "SELECT" ? t("commerce:admin.choose") : t("commerce:admin.enter");
      showToast({
        type: "error",
        title: t("commerce:admin.completeRequired"),
        message: t("commerce:admin.requiredBeforeSave", { action, field: fieldLabel.toLocaleLowerCase(language) }),
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
        title: t("commerce:admin.savedTitle", { item: t(`commerce:admin.${sectionKey}Singular`) }),
        message: wasEditing ? t("commerce:admin.changesSaved") : t("commerce:admin.createdSuccessfully", { item: t(`commerce:admin.${sectionKey}Singular`).toLocaleLowerCase(language) }),
      });
    } catch {
      const message = t("commerce:admin.saveFailed", { item: t(`commerce:admin.${sectionKey}Singular`).toLocaleLowerCase(language) });
      showToast({ type: "error", title: t("commerce:admin.saveFailedTitle", { item: t(`commerce:admin.${sectionKey}Singular`).toLocaleLowerCase(language) }), message });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item) => {
    if (!window.confirm(t("commerce:admin.deleteConfirm", { name: translatedName(item, language) }))) return;
    try {
      await deleteEcommerceItem(section, item.id, { scope: cacheScope });
      setCatalog((current) => ({
        ...current,
        [section]: current[section].filter((candidate) => candidate.id !== item.id),
      }));
      showToast({
        type: "success",
        title: t("commerce:admin.deletedTitle", { item: t(`commerce:admin.${sectionKey}Singular`) }),
        message: t("commerce:admin.deletedBody", { name: translatedName(item, language) }),
      });
    } catch {
      const message = t("commerce:admin.deleteFailed", { item: t(`commerce:admin.${sectionKey}Singular`).toLocaleLowerCase(language) });
      showToast({ type: "error", title: t("commerce:admin.deleteFailedTitle", { item: t(`commerce:admin.${sectionKey}Singular`).toLocaleLowerCase(language) }), message });
    }
  };
  const activeCount = items.filter((item) => item.status === "active").length;
  const inactiveCount = items.filter((item) => item.status === "inactive").length;
  const draftCount = items.filter((item) => item.status === "draft").length;
  const archivedCount = items.filter((item) => item.status === "archived").length;
  const stockSummary = catalog.stock_summary || {};
  const lowStockCount = Number(stockSummary.low_stock ?? items.reduce((count, item) => count + Number(item.low_stock_count || 0), 0));
  const outOfStockCount = Number(stockSummary.out_of_stock ?? items.reduce((count, item) => count + Number(item.out_of_stock_count || 0), 0));
  const sectionKey = section === "categories" ? "categories" : section === "tags" ? "tags" : "products";
  const summaryCards = [
    { id: "total", label: t(`dashboard:ecommercePages.${sectionKey}.totalLabel`), value: items.length, icon: Icon },
    { id: "draft", label: t("commerce:common.draft"), value: draftCount, icon: Clock3 },
    { id: "active", label: t("commerce:common.active"), value: activeCount, icon: CheckCircle2 },
    { id: "inactive", label: t("commerce:common.inactive"), value: inactiveCount, icon: Boxes },
    { id: "archived", label: t("commerce:common.archived"), value: archivedCount, icon: Archive },
    ...(section === "products" ? [
      { id: "low-stock", label: t("commerce:merchant.lowStock"), value: lowStockCount, icon: Package },
      { id: "out-of-stock", label: t("commerce:merchant.outOfStock"), value: outOfStockCount, icon: Boxes },
    ] : []),
  ];
  const visibleSummaryCards = summaryCards.filter((card) => !hiddenSummaryCardIds.includes(card.id));
  const toggleSummaryCard = (cardId) => {
    setHiddenSummaryCardIds((current) => (
      current.includes(cardId) ? current.filter((id) => id !== cardId) : [...current, cardId]
    ));
  };

  if (status === "loading") {
    return <section className="ecommerce-page"><CatalogSkeleton label={t("commerce:admin.loadingCatalog")} section={section} summaryCount={visibleSummaryCards.length} /></section>;
  }

  return (
    <section className="ecommerce-page" aria-labelledby={`ecommerce-${section}-title`} dir={direction} lang={language}>
      <header className="ecommerce-page-header app-page-intro">
        <div>
          <h1 id={`ecommerce-${section}-title`}>{t(`dashboard:ecommercePages.${sectionKey}.title`)}</h1>
          <p>{t(`dashboard:ecommercePages.${sectionKey}.description`)}</p>
        </div>
      </header>

      <div className="ecommerce-summary-toolbar">
        <div className="ecommerce-summary-customizer" ref={summaryCustomizerRef}>
          <button type="button" className="ecommerce-summary-customizer-toggle" aria-expanded={summaryCustomizerOpen} aria-controls="ecommerce-summary-card-checklist" onClick={() => setSummaryCustomizerOpen((current) => !current)}>
            <SlidersHorizontal size={18} aria-hidden="true" />
            <span>{t(`commerce:admin.customize${sectionKey[0].toUpperCase() + sectionKey.slice(1)}Cards`)}</span>
          </button>
          {summaryCustomizerOpen && (
            <div className="ecommerce-summary-customizer-menu" id="ecommerce-summary-card-checklist">
              <header><div><strong>{t(`commerce:admin.${sectionKey}Cards`)}</strong><span>{t("commerce:admin.chooseCards", { defaultValue: "Choose what you want to see" })}</span></div><button type="button" className="ecommerce-summary-customizer-reset" onClick={() => setHiddenSummaryCardIds([])} disabled={!hiddenSummaryCardIds.length}>{t("commerce:admin.showAll", { defaultValue: "Show all" })}</button></header>
              <div className="ecommerce-summary-customizer-list">
                {summaryCards.map((card) => <label key={card.id}><input type="checkbox" checked={!hiddenSummaryCardIds.includes(card.id)} onChange={() => toggleSummaryCard(card.id)} /><span>{card.label}</span></label>)}
              </div>
            </div>
          )}
        </div>
        {section !== "products" && <button type="button" className="ecommerce-primary-button" onClick={openCreate}><Plus size={18} />{t("commerce:admin.add", { item: t(`commerce:admin.${sectionKey}Singular`) })}</button>}
        {section === "products" && <button type="button" className="ecommerce-primary-button" onClick={() => { setProductEditorId(null); setProductEditorOpen(true); }}><Plus size={18} />{t("commerce:admin.add", { item: t("commerce:admin.productsSingular") })}</button>}
      </div>

      <div className="ecommerce-summary-grid" aria-label={t("dashboard:ecommercePages.overview")}>
        {visibleSummaryCards.map(({ id, label, value, icon: SummaryIcon }) => (
          <article className="ecommerce-summary-card" key={id}><span className="ecommerce-summary-icon"><SummaryIcon size={20} /></span><div><span>{label}</span><strong>{value}</strong></div></article>
        ))}
        {!visibleSummaryCards.length && <p className="ecommerce-summary-empty">{t("commerce:admin.noCardsSelected", { defaultValue: "No cards selected. Use Customize cards to add them." })}</p>}
      </div>

      <section className="ecommerce-list-card" aria-labelledby={`ecommerce-${section}-list-title`}>
        <header className="ecommerce-list-header">
          <div className="ecommerce-list-heading">
            <h2 id={`ecommerce-${section}-list-title`}>{t("commerce:admin.manage", { items: t(`dashboard:ecommercePages.${sectionKey}.title`) })}</h2>
            {section === "products" && <div className="ecommerce-stock-filter-panel">
              <span className="ecommerce-stock-filter-label"><SlidersHorizontal size={15} aria-hidden="true" />{t("commerce:admin.stockFilter")}</span>
              <div className="ecommerce-stock-filters" role="group" aria-label={t("commerce:admin.stockFilter")}>
                {["all", "low_stock", "out_of_stock"].map((value) => <button type="button" key={value} className={stockFilter === value ? "is-active" : ""} aria-pressed={stockFilter === value} onClick={() => setStockFilter(value)}>
                  {value === "all" ? t("commerce:merchant.allStock") : value === "low_stock" ? t("commerce:merchant.lowStock") : t("commerce:merchant.outOfStock")}
                </button>)}
              </div>
            </div>}
          </div>
          <div className="ecommerce-list-controls">
            <label className="ecommerce-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("commerce:admin.search", { items: t(`dashboard:ecommercePages.${sectionKey}.title`) })} /></label>
          </div>
        </header>

        {filteredItems.length === 0 ? (
          <div className="ecommerce-empty-state"><span><Icon size={27} /></span><h3>{query || stockFilter !== "all" ? t("commerce:admin.noMatching") : t(`dashboard:ecommercePages.${sectionKey}.emptyTitle`)}</h3><p>{query || stockFilter !== "all" ? t("commerce:admin.tryDifferent") : t(`dashboard:ecommercePages.${sectionKey}.emptyDescription`)}</p></div>
        ) : (
          <div className="ecommerce-record-list">
            {filteredItems.map((item) => {
              const parent = section === "categories" ? catalog.categories.find((candidate) => candidate.id === item.parent_id) : null;
              const category = section === "products" ? catalog.categories.find((candidate) => candidate.id === item.category_id) : null;
              return (
                <article className="ecommerce-record" key={item.id}>
                  <span className="ecommerce-record-icon"><Icon size={18} /></span>
                  <div className="ecommerce-record-main"><strong>{translatedName(item, language)}</strong><span>{section === "products" ? <><bdi>{item.sku}</bdi> · <bdi>{formatCommerceMoney(item.price, item.currency, language)}</bdi></> : item.slug}</span>{section === "products" && <span className={`ecommerce-stock-indicator is-${commerceProductStock(item).state}`}>{t(`commerce:stock.${commerceProductStock(item).state}`)}{item.options?.length ? ` · ${t("commerce:admin.variantStockCounts", { low: item.low_stock_count || 0, out: item.out_of_stock_count || 0 })}` : ""}</span>}</div>
                  <div className="ecommerce-record-meta">{parent ? t("commerce:admin.under", { name: translatedName(parent, language) }) : category ? translatedName(category, language) : section === "categories" ? t("commerce:admin.topLevel") : ""}</div>
                  <span className={`ecommerce-status is-${item.status}`}>{t(`commerce:status.${item.status}`, { defaultValue: item.status })}</span>
                  <div className="ecommerce-record-actions">{section === "products" ? <button type="button" onClick={() => { setProductEditorId(item.id); setProductEditorOpen(true); }} aria-label={t("commerce:admin.openEditor", { name: translatedName(item, language) })}><Pencil size={16} /></button> : <button type="button" onClick={() => openEdit(item)} aria-label={t("commerce:admin.quickEdit", { name: translatedName(item, language) })}><Pencil size={16} /></button>}<button type="button" onClick={() => remove(item)} aria-label={t("commerce:admin.delete", { name: translatedName(item, language) })}><Trash2 size={16} /></button></div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {formOpen && (
        <div className="ecommerce-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeForm(); }}>
          <section className="ecommerce-modal" role="dialog" aria-modal="true" aria-labelledby="ecommerce-form-title">
            <header><div><span>{editing ? t("commerce:admin.edit") : t("commerce:admin.create")}</span><h2 id="ecommerce-form-title">{editing ? t("commerce:admin.editItem", { item: t(`commerce:admin.${sectionKey}Singular`) }) : t("commerce:admin.newItem", { item: t(`commerce:admin.${sectionKey}Singular`) })}</h2></div><button type="button" onClick={closeForm} aria-label={t("commerce:admin.close")}><X size={20} /></button></header>
            <form onSubmit={submit} noValidate>
              <TranslationFields form={form} setForm={setForm} descriptions={section !== "tags"} autoGenerateSlug={!editing && !slugManuallyEdited} t={t} />
              {section === "tags" && <CommonFields form={form} setForm={setForm} onSlugChange={() => setSlugManuallyEdited(true)} t={t} />}
              {section === "categories" && <><CommonFields form={form} setForm={setForm} onSlugChange={() => setSlugManuallyEdited(true)} t={t} /><fieldset className="ecommerce-form-section ecommerce-hierarchy-section" aria-label={t("commerce:admin.hierarchy")}><small id="category-display-position-help" className="ecommerce-field-help">{t("commerce:admin.displayOrderHelp")}</small><div className="ecommerce-field-grid"><label>{t("commerce:admin.parentCategory")}<select value={form.parent_id || ""} onChange={(event) => setForm({ ...form, parent_id: event.target.value })}><option value="">{t("commerce:admin.topLevel")}</option>{catalog.categories.filter((category) => category.id !== editing?.id).map((category) => <option key={category.id} value={category.id}>{translatedName(category, language)}</option>)}</select></label><label><span>{t("commerce:admin.displayPosition")}</span><input type="number" min="0" step="1" inputMode="numeric" value={form.sort_order} required aria-label={t("commerce:admin.displayPosition")} aria-describedby="category-display-position-help" onChange={(event) => setForm({ ...form, sort_order: event.target.value })} /></label></div></fieldset></>}
              {section === "products" && <><div className="ecommerce-field-grid"><label>{t("commerce:merchant.slug")}<input value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} required /></label></div><ProductFields form={form} setForm={setForm} catalog={catalog} t={t} language={language} /></>}
              <footer><button type="button" className="ecommerce-secondary-button" onClick={closeForm}>{t("commerce:common.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={saving}>{saving && <LoaderCircle size={17} className="is-spinning" />}{saving ? t("commerce:merchant.saving") : t("commerce:common.save")}</button></footer>
            </form>
          </section>
        </div>
      )}
      {productEditorOpen && (
        <div className="ecommerce-product-editor-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setProductEditorOpen(false); }}>
          <section className="ecommerce-product-editor-modal" role="dialog" aria-modal="true" aria-label={t(productEditorId ? "commerce:merchant.editProduct" : "commerce:merchant.newProduct")}>
            <button type="button" className="ecommerce-product-editor-modal-close" onClick={() => setProductEditorOpen(false)} aria-label={t("commerce:admin.close")}><X size={20} /></button>
            <EcommerceProductEditor
              user={user}
              productId={productEditorId}
              embedded
              initialCatalog={catalog}
              onClose={() => setProductEditorOpen(false)}
              onSaved={() => {
                setProductEditorOpen(false);
                void loadCatalog();
              }}
            />
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
