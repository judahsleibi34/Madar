import { getEcommerceCacheScope } from "./utils/ecommerceAdminCache";
import { ProductEditorSkeleton } from "./CommerceLoadingLayouts";
import { notifyCommerceAction } from "../../utils/commerceActionToast";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ChevronDown, ImagePlus, Pencil, Plus, Save, Search, Trash2, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { DASHBOARD_ROUTES } from "../../config/routes";
import { fetchEcommerceCatalog, saveEcommerceItem, uploadEcommerceProductImage } from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";
import { getResponsiveMediaProps, isVideoMediaUrl, resolveMediaUrl } from "../../utils/media";

const uuid = () => globalThis.crypto?.randomUUID?.() || `00000000-0000-4000-8000-${Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12)}`;
const code = (value, fallback) => String(value || fallback).trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || fallback;
const skuCode = (value, suffix) => {
  const readablePrefix = code(value, "product").toUpperCase().slice(0, 100);
  return `${readablePrefix}-${suffix}`;
};
const localized = (en = "", ar = "") => ({ en: String(en).trim(), ...(String(ar).trim() ? { ar: String(ar).trim() } : {}) });
const emptyProduct = (currency = "USD") => ({
  slug: "", sku: "", barcode: null, category_id: null, tag_ids: [], product_type: "physical", brand: "",
  translations: { en: { name: "", description: "" }, ar: { name: "", description: "" } }, status: "draft",
  price: 0, compare_at_price: null, cost_price: null, currency: currency || "USD", track_inventory: true, inventory_quantity: 0,
  low_stock_threshold: 5, allow_backorder: false, images: [], weight: null, weight_unit: "kg",
  requires_shipping: true, taxable: true, seo_title: "", seo_description: "", attributes: [], options: [], variants: [],
});

const activeOptionValues = (option) => (option.values || []).filter((value) => value.active !== false);
const combinationKey = (ids) => ids.filter(Boolean).join(":");

function Checkbox({ checked, onChange, children, ariaLabel }) {
  return <label className="ecommerce-editor-checkbox">
    <input type="checkbox" checked={checked} onChange={onChange} aria-label={ariaLabel} />
    <span>{children}</span>
  </label>;
}

function SearchableDropdown({ label, items, value, multiple = false, onChange, searchLabel, emptyLabel, noResultsLabel, selectionLabel }) {
  const detailsRef = useRef(null);
  const [query, setQuery] = useState("");
  const selectedIds = multiple ? value : [value];
  const selectedItem = items.find((item) => item.id === value);
  const filteredItems = items.filter((item) => item.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  const summary = multiple
    ? (value.length ? selectionLabel(value.length) : emptyLabel)
    : (selectedItem?.label || emptyLabel);

  useEffect(() => {
    const closeOnOutside = (event) => {
      if (detailsRef.current && !detailsRef.current.contains(event.target)) detailsRef.current.removeAttribute("open");
    };
    document.addEventListener("mousedown", closeOnOutside);
    return () => document.removeEventListener("mousedown", closeOnOutside);
  }, []);

  return <div className="ecommerce-editor-search-select">
    <span className="ecommerce-editor-search-select-label">{label}</span>
    <details ref={detailsRef} onToggle={(event) => { if (!event.currentTarget.open) setQuery(""); }}>
      <summary><span>{summary}</span><ChevronDown size={17} /></summary>
      <div className="ecommerce-editor-search-menu">
        <label className="ecommerce-editor-search-box">
          <Search size={16} />
          <input type="search" aria-label={searchLabel} placeholder={searchLabel} value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <div className="ecommerce-editor-search-options" role="listbox" aria-multiselectable={multiple || undefined}>
          {filteredItems.map((item) => multiple
            ? <label className="ecommerce-editor-search-option" key={item.id}>
                <input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => onChange(selectedIds.includes(item.id) ? value.filter((id) => id !== item.id) : [...value, item.id])} />
                <span>{item.label}</span>
              </label>
            : <button type="button" role="option" aria-selected={value === item.id} className={value === item.id ? "is-selected" : ""} key={item.id} onClick={() => { onChange(item.id); detailsRef.current?.removeAttribute("open"); }}>
                {item.label}
              </button>)}
          {!filteredItems.length && <p className="ecommerce-editor-search-empty">{noResultsLabel}</p>}
        </div>
      </div>
    </details>
  </div>;
}

function ProductMediaUploader({ items, busy, disabled, progress, error, dragging, onDragging, onFiles, onRemove, t, label }) {
  const dropFiles = (event) => {
    event.preventDefault();
    onDragging(false);
    if (disabled) return;
    onFiles(event.dataTransfer.files);
  };

  return <div className="ecommerce-product-images ecommerce-editor-media-uploader">
    <div className="ecommerce-product-images-header">
      <div><strong>{label}</strong><span>{t("admin.galleryHelp")}</span></div>
      <span className="ecommerce-product-image-count">{t("admin.mediaCount", { count: items.length })}</span>
    </div>
    <div className={`ecommerce-product-image-grid${items.length ? " has-images" : ""}`}>
      {items.map((mediaUrl, index) => <figure key={mediaUrl}>
        {isVideoMediaUrl(mediaUrl)
          ? <video src={resolveMediaUrl(mediaUrl)} muted playsInline preload="metadata" aria-label={t("admin.productMedia", { count: index + 1 })} />
          : <img {...getResponsiveMediaProps(mediaUrl, { widths: [768, 1024, 1440], fallbackWidth: 1024, sizes: "320px" })} alt={t("admin.productMedia", { count: index + 1 })} loading="lazy" decoding="async" />}
        <figcaption>{index === 0 ? t("admin.mainMedia") : t("admin.media", { count: index + 1 })}</figcaption>
        <button type="button" onClick={() => onRemove(mediaUrl)} aria-label={t("admin.removeMedia", { count: index + 1 })}><X size={15} /></button>
      </figure>)}
      {items.length < 10 && <label
        className={`ecommerce-product-image-upload${busy ? " is-busy" : ""}${dragging ? " is-dragging" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); onDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) onDragging(false); }}
        onDrop={dropFiles}
      >
        <span className="ecommerce-product-image-upload-icon"><ImagePlus size={23} /></span>
        <strong>{busy ? t("admin.uploadProgress", progress) : items.length ? t("admin.addAnotherMedia") : t("merchant.addMedia")}</strong>
        <span>{busy ? t("admin.keepOpen") : t("admin.dragBrowse")}</span>
        <small>{t("admin.mediaRequirements")}</small>
        <input type="file" accept="image/png,image/jpeg,image/webp,video/mp4,video/webm" multiple disabled={disabled} aria-label={t("admin.uploadProductMedia")} onChange={(event) => { onFiles(event.target.files); event.target.value = ""; }} />
      </label>}
    </div>
    {error && <p className="ecommerce-editor-media-error" role="alert">{error}</p>}
  </div>;
}

export function EcommerceProductEditor({ user, productId, embedded = false, initialCatalog, onClose, onSaved }) {
  const { t, locale, direction, localize } = useCommerceI18n();
  const scope = getEcommerceCacheScope(user);
  const [catalog, setCatalog] = useState(() => initialCatalog || { products: [], categories: [], tags: [], commerce_currency: "USD" });
  const [form, setForm] = useState(() => emptyProduct(initialCatalog?.commerce_currency));
  const [state, setState] = useState({ loading: !initialCatalog, saving: false, error: "" });
  const [uploading, setUploading] = useState("");
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 });
  const [uploadError, setUploadError] = useState({ target: "", message: "" });
  const [dragTarget, setDragTarget] = useState("");
  const editing = Boolean(productId);
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(editing);
  const [skuManuallyEdited, setSkuManuallyEdited] = useState(editing);
  const [autoSkuSuffix] = useState(() => uuid().replace(/-/g, "").slice(0, 8).toUpperCase());
  const [editingValue, setEditingValue] = useState({});
  const [merchantNotice, setMerchantNotice] = useState("");
  const showMerchantNotice = (message) => {
    setMerchantNotice(message);
    notifyCommerceAction({ type: "error", title: t("admin.completeRequired"), message });
  };
  const persistedVariantIds = useRef(new Set());
  const referencedValueIds = useRef(new Set());
  const [expandedOptions, setExpandedOptions] = useState({});
  const toggleOptionExpand = (optionId) => setExpandedOptions((current) => ({ ...current, [optionId]: !current[optionId] }));
  const [inlineValueForm, setInlineValueForm] = useState(null); // { optionId, mode: "text"|"color" }
  const openInlineValueForm = (optionId, mode) => {
    setInlineValueForm({ optionId, mode });
    setInlineTextDraft("");
    setInlineTextDraftAr("");
    setInlineColorDraft("");
    setInlineColorDraftAr("");
    setInlineColorHex("#808080");
  };
  const closeInlineValueForm = () => setInlineValueForm(null);
  const [inlineTextDraft, setInlineTextDraft] = useState("");
  const [inlineTextDraftAr, setInlineTextDraftAr] = useState("");
  const [inlineColorDraft, setInlineColorDraft] = useState("");
  const [inlineColorDraftAr, setInlineColorDraftAr] = useState("");
  const [inlineColorHex, setInlineColorHex] = useState("#808080");
  const submitInlineTextValue = (optionId) => {
    const en = inlineTextDraft.trim();
    if (!en) return;
    const option = form.options.find((o) => o.id === optionId);
    if (!option) return;
    const exists = activeOptionValues(option).some((v) => String(v.value_translations?.en || "").trim().toLocaleLowerCase() === en.toLocaleLowerCase());
    if (exists) { showMerchantNotice(t("admin.duplicateOptionValue", { option: option.name_translations.en })); return; }
    const nv = { id: uuid(), code: "", value_translations: localized(en, inlineTextDraftAr), color_hex: null, sort_order: option.values.length, active: true };
    changeOption(optionId, (current) => ({ values: [...current.values, { ...nv, sort_order: current.values.length }] }));
    setInlineTextDraft(""); setInlineTextDraftAr(""); setMerchantNotice("");
  };
  const submitInlineColorValue = (optionId) => {
    const en = inlineColorDraft.trim();
    if (!en) return;
    const option = form.options.find((o) => o.id === optionId);
    if (!option) return;
    const exists = activeOptionValues(option).some((v) => String(v.value_translations?.en || "").trim().toLocaleLowerCase() === en.toLocaleLowerCase());
    if (exists) { showMerchantNotice(t("admin.duplicateOptionValue", { option: option.name_translations.en })); return; }
    let hex = inlineColorHex.trim();
    if (!hex.startsWith("#") && hex.length > 0) hex = `#${hex}`;
    if (!/^#[0-9a-fA-F]{6}$/.test(hex)) hex = "#808080";
    const nv = { id: uuid(), code: "", value_translations: localized(en, inlineColorDraftAr), color_hex: hex.toUpperCase(), sort_order: option.values.length, active: true };
    changeOption(optionId, (current) => ({ values: [...current.values, { ...nv, sort_order: current.values.length }] }));
    setInlineColorDraft(""); setInlineColorDraftAr(""); setInlineColorHex("#808080"); setMerchantNotice("");
  };

  useEffect(() => {
    let cancelled = false;
    if (initialCatalog && !editing) {
      Promise.resolve().then(() => {
        if (cancelled) return;
        setCatalog(initialCatalog);
        setForm(emptyProduct(initialCatalog.commerce_currency));
        setState({ loading: false, saving: false, error: "" });
      });
      return () => { cancelled = true; };
    }
    fetchEcommerceCatalog({ scope, force: true }).then((result) => {
      if (cancelled) return;
      const product = result.products?.find((item) => item.id === productId);
      if (editing && !product) throw new Error(t("commerce:errors.productNotFound"));
      persistedVariantIds.current = new Set((product?.variants || []).map((variant) => variant.id));
      referencedValueIds.current = new Set((product?.variants || []).flatMap((variant) => variant.option_value_ids || []));
      setCatalog(result);
      setForm(product ? { ...emptyProduct(result.commerce_currency), ...product, attributes: product.attributes || [], options: (product.options || []).map((option) => ({ ...option, required: true, display_type: option.display_type || "text", values: (option.values || []).map((value) => ({ ...value, color_hex: value.color_hex || null })) })), variants: product.variants || [] } : emptyProduct(result.commerce_currency));
      setState({ loading: false, saving: false, error: "" });
    }).catch(() => {
      if (cancelled) return;
      setState({ loading: false, saving: false, error: t("commerce:errors.loadProduct") });
      notifyCommerceAction({ type: "error", title: t("commerce:errors.loadProduct"), message: t("admin.tryAgain") });
    });
    return () => { cancelled = true; };
  }, [editing, initialCatalog, productId, scope, t]);

  const valueById = useMemo(() => new Map(form.options.flatMap((option) => option.values || []).map((value) => [value.id, value])), [form.options]);
  const optionIdByValueId = useMemo(() => new Map(form.options.flatMap((option) => (option.values || []).map((value) => [value.id, option.id]))), [form.options]);

  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const updateTranslation = (locale, field, value) => setForm((current) => ({ ...current, translations: { ...current.translations, [locale]: { ...current.translations[locale], [field]: value } } }));
  const updateEnglishName = (value) => setForm((current) => ({
    ...current,
    ...(!slugManuallyEdited ? { slug: code(value, "") } : {}),
    ...(!skuManuallyEdited ? { sku: value.trim() ? skuCode(value, autoSkuSuffix) : "" } : {}),
    translations: {
      ...current.translations,
      en: { ...current.translations.en, name: value },
    },
  }));
  const addAttribute = () => update("attributes", [...form.attributes, { id: uuid(), name_translations: { en: "" }, value_translations: { en: "" }, sort_order: form.attributes.length }]);
  const changeAttribute = (id, field, value) => update("attributes", form.attributes.map((item) => item.id === id ? { ...item, [field]: value } : item));
  const addOption = () => update("options", [...form.options, { id: uuid(), code: "", name_translations: { en: "" }, required: true, display_type: "text", sort_order: form.options.length, values: [] }]);
  const changeOption = (id, change) => setForm((current) => ({ ...current, options: current.options.map((item) => item.id === id ? { ...item, ...(typeof change === "function" ? change(item) : change) } : item) }));

  const changeValue = (option, valueId, change) => changeOption(option.id, (current) => ({ values: current.values.map((value) => value.id === valueId ? { ...value, ...change } : value) }));
  const removeValue = (option, value) => {
    if (referencedValueIds.current.has(value.id) || form.variants.some((variant) => variant.option_value_ids.includes(value.id))) {
      changeValue(option, value.id, { active: false });
      showMerchantNotice(t("admin.referencedValueArchived", { value: localize(value, "value") || value.code }));
      return;
    }
    changeOption(option.id, { values: option.values.filter((entry) => entry.id !== value.id) });
    setMerchantNotice("");
  };
  const removeOption = (option) => {
    const valueIds = new Set((option.values || []).map((value) => value.id));
    if (form.variants.some((variant) => variant.option_value_ids.some((id) => valueIds.has(id)))) {
      showMerchantNotice(t("admin.optionUsedByVariant"));
      return;
    }
    update("options", form.options.filter((entry) => entry.id !== option.id));
    setMerchantNotice("");
  };
  const changeVariant = (id, change) => update("variants", form.variants.map((item) => item.id === id ? { ...item, ...change } : item));
  const resolveOrCreateValue = (option, label) => {
    const normalized = String(label || "").trim().toLocaleLowerCase();
    if (!normalized) return null;
    const existingActive = activeOptionValues(option).find(
      (value) => String(value.value_translations?.en || "").trim().toLocaleLowerCase() === normalized,
    );
    if (existingActive) return existingActive.id;
    const archived = (option.values || []).find(
      (value) => value.active === false && String(value.value_translations?.en || "").trim().toLocaleLowerCase() === normalized,
    );
    if (archived) { changeValue(option, archived.id, { active: true }); return archived.id; }
    const newValue = { id: uuid(), code: "", value_translations: { en: String(label).trim() }, normalized_value: normalized, color_hex: option.display_type === "color" ? "#808080" : null, sort_order: option.values.length, active: true };
    changeOption(option.id, (current) => ({ values: [...current.values, { ...newValue, sort_order: current.values.length }] }));
    return newValue.id;
  };
  const updateVariantOption = (variantId, optionId, newValueId) => {
    setForm((current) => ({
      ...current,
      variants: current.variants.map((variant) => {
        if (variant.id !== variantId) return variant;
        const filteredIds = variant.option_value_ids.filter((id) => optionIdByValueId.get(id) !== optionId);
        return { ...variant, option_value_ids: newValueId ? [...filteredIds, newValueId] : filteredIds };
      }),
    }));
  };
  const addVariantRow = () => {
    const rowSuffix = uuid().replace(/-/g, "").slice(0, 6).toUpperCase();
    update("variants", [...form.variants, {
      id: uuid(), sku: `${form.sku || skuCode(form.translations.en.name, autoSkuSuffix)}-${rowSuffix}`.slice(0, 120),
      barcode: null, price_override: null, compare_at_price_override: null,
      track_inventory: true, inventory_quantity: 0, low_stock_threshold: 5, allow_backorder: false,
      images: [], active: true, option_value_ids: [],
    }]);
  };
  const removeVariantRow = (variantId) => {
    if (persistedVariantIds.current.has(variantId)) {
      changeVariant(variantId, { active: false });
    } else {
      update("variants", form.variants.filter((v) => v.id !== variantId));
    }
  };
  const getSelectedValueForOption = (variant, optionId) => variant.option_value_ids.find((id) => optionIdByValueId.get(id) === optionId) || "";
  const validateMerchantForm = () => {
    if (!String(form.translations.en.name || "").trim()) return t("admin.validationProductName");
    const optionNames = form.options.map((option) => String(option.name_translations?.en || "").trim().toLocaleLowerCase());
    if (optionNames.some((name) => !name)) return t("admin.validationOptionName");
    if (new Set(optionNames).size !== optionNames.length) return t("admin.validationDuplicateOption");
    for (const option of form.options) {
      const values = option.values || [];
      if (!values.length) return t("admin.addAtLeastOneValue", { option: option.name_translations.en });
      const labels = values.map((value) => String(value.value_translations?.en || "").trim().toLocaleLowerCase());
      if (labels.some((label) => !label)) return t("admin.validationValueName", { option: option.name_translations.en });
      if (new Set(labels).size !== labels.length) return t("admin.duplicateOptionValue", { option: option.name_translations.en });
      if (option.display_type === "color" && values.some((value) => value.active !== false && !/^#[0-9a-f]{6}$/i.test(value.color_hex || ""))) return t("admin.validationColorSwatch", { option: option.name_translations.en });
    }
    const activeVariants = form.variants.filter((v) => v.active !== false);
    const variantKeys = activeVariants.map((variant) => combinationKey([...variant.option_value_ids].sort()));
    if (new Set(variantKeys).size !== variantKeys.length) return t("admin.validationDuplicateCombination");
    const skus = activeVariants.map((variant) => String(variant.sku || "").trim().toLocaleLowerCase());
    if (skus.some((sku) => !sku)) return t("admin.validationVariantSku");
    if (new Set(skus).size !== skus.length) return t("admin.validationUniqueSku");
    if (form.status === "active" && form.options.length && !activeVariants.some((variant) => variant.active)) return t("admin.validationSellableVariant");
    for (const variant of activeVariants) {
      const selected = new Set(variant.option_value_ids);
      if (variant.active && form.options.some((option) => option.required && !(option.values || []).some((value) => selected.has(value.id)))) {
        return t("admin.validationRequiredOptions");
      }
    }
    return "";
  };
  const appendMedia = (url, variantId = null) => setForm((current) => variantId ? {
    ...current,
    variants: current.variants.map((variant) => variant.id === variantId
      ? { ...variant, images: [...(variant.images || []), url].slice(0, 10) }
      : variant),
  } : { ...current, images: [...(current.images || []), url].slice(0, 10) });
  const uploadMedia = async (files, variantId = null) => {
    const target = variantId || "product";
    const current = variantId ? form.variants.find((item) => item.id === variantId)?.images || [] : form.images || [];
    const selected = Array.from(files || []);
    if (!selected.length) return;
    const showUploadError = (message) => {
      setUploadError({ target, message });
      notifyCommerceAction({ type: "error", title: t("commerce:errors.uploadMedia"), message });
    };
    if (selected.length > 10 - current.length) return showUploadError(t("commerce:errors.mediaLimit"));
    if (selected.some((file) => !["image/png", "image/jpeg", "image/webp", "video/mp4", "video/webm"].includes(file.type))) return showUploadError(t("commerce:errors.invalidMediaType"));
    if (selected.some((file) => file.size > (file.type.startsWith("video/") ? 250 : 25) * 1024 * 1024)) return showUploadError(t("commerce:errors.mediaFileTooLarge"));
    setUploading(target);
    setUploadProgress({ current: 1, total: selected.length });
    setUploadError({ target: "", message: "" });
    setState((value) => ({ ...value, error: "" }));
    try {
      for (const [index, file] of selected.entries()) {
        setUploadProgress({ current: index + 1, total: selected.length });
        const url = await uploadEcommerceProductImage(file);
        if (!url) throw new Error(t("commerce:errors.uploadMedia"));
        appendMedia(url, variantId);
      }
      notifyCommerceAction({ type: "success", title: t("feedback.mediaUploaded"), message: t("feedback.mediaUploadedBody") });
    } catch {
      showUploadError(t("commerce:errors.uploadMedia"));
    } finally {
      setUploading("");
      setUploadProgress({ current: 0, total: 0 });
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    const validationError = validateMerchantForm();
    if (validationError) {
      setState((current) => ({ ...current, saving: false, error: validationError }));
      notifyCommerceAction({ type: "error", title: t("admin.completeRequired"), message: validationError });
      return;
    }
    setState((current) => ({ ...current, saving: true, error: "" }));
    try {
      const payload = {
        ...form,
        slug: code(form.slug || form.translations.en.name, "product"),
        sku: String(form.sku || "").trim() || null,
        barcode: form.barcode || null,
        price: Number(form.price || 0), compare_at_price: form.compare_at_price === "" || form.compare_at_price == null ? null : Number(form.compare_at_price),
        inventory_quantity: Number(form.inventory_quantity || 0), low_stock_threshold: Number(form.low_stock_threshold || 0), currency: catalog.commerce_currency,
        attributes: form.attributes.map((item, index) => ({ ...item, sort_order: index, name_translations: localized(item.name_translations.en, item.name_translations.ar), value_translations: localized(item.value_translations.en, item.value_translations.ar) })),
        options: form.options.map((option, index) => ({ ...option, display_type: option.display_type || "text", code: code(option.code || option.name_translations.en, `option-${index + 1}`), sort_order: index, name_translations: localized(option.name_translations.en, option.name_translations.ar), values: option.values.map((value, valueIndex) => ({ ...value, color_hex: option.display_type === "color" ? value.color_hex : null, code: code(value.code || value.value_translations.en, `value-${valueIndex + 1}`), sort_order: valueIndex, value_translations: localized(value.value_translations.en, value.value_translations.ar) })) })),
        variants: form.variants.map((variant) => ({ ...variant, sku: variant.sku.trim(), barcode: variant.barcode || null, price_override: variant.price_override === "" || variant.price_override == null ? null : Number(variant.price_override), compare_at_price_override: variant.compare_at_price_override === "" || variant.compare_at_price_override == null ? null : Number(variant.compare_at_price_override), inventory_quantity: Number(variant.inventory_quantity || 0), low_stock_threshold: Number(variant.low_stock_threshold || 0), option_value_ids: variant.option_value_ids.filter(Boolean) })),
      };
      const savedProduct = await saveEcommerceItem("products", productId, payload, { scope });
      notifyCommerceAction({ type: "success", title: t("admin.savedTitle", { item: t("admin.productSingular") }), message: t("admin.changesSaved") });
      onSaved?.(savedProduct);
    } catch {
      setState((current) => ({ ...current, saving: false, error: t("commerce:errors.saveProduct") }));
      notifyCommerceAction({ type: "error", title: t("commerce:errors.saveProduct"), message: t("admin.tryAgain") });
    } finally {
      setState((current) => ({ ...current, saving: false }));
    }
  };

  if (state.loading) return <ProductEditorSkeleton label={t("merchant.loadingProduct")} direction={direction} lang={locale} />;
  return (
    <form className="ecommerce-product-editor" onSubmit={submit} dir={direction} lang={locale} noValidate>
      <header>
<div>
{!embedded && <Link to={DASHBOARD_ROUTES.ecommerceProducts}>
<ArrowLeft size={16} />{t("common.products")}</Link>}
<h1>{editing ? t("merchant.editProduct") : t("merchant.newProduct")}</h1>
</div>
</header>
      {state.error && <p className="ecommerce-editor-error" role="alert">{state.error}</p>}
      <section>
<h2>{t("merchant.basic")}</h2>
<fieldset className="ecommerce-editor-translations" aria-label={t("admin.translations")}>
<div className="ecommerce-editor-translation-grid">
<div className="ecommerce-editor-language-card">
<strong>{t("admin.english")}</strong>
<label>{t("admin.name")}<input aria-label={t("merchant.nameEnglish")} required maxLength={200} dir="ltr" value={form.translations.en.name} onChange={(e) => updateEnglishName(e.target.value)} />
</label>
<label>{t("admin.description")}<textarea aria-label={t("merchant.descriptionEnglish")} rows={4} dir="ltr" value={form.translations.en.description} onChange={(e) => updateTranslation("en", "description", e.target.value)} />
</label>
</div>
<div className="ecommerce-editor-language-card">
<strong>{t("admin.arabic")}</strong>
<label>{t("admin.name")}<input aria-label={t("merchant.nameArabic")} maxLength={200} dir="rtl" value={form.translations.ar?.name || ""} onChange={(e) => updateTranslation("ar", "name", e.target.value)} />
</label>
<label>{t("admin.description")}<textarea aria-label={t("merchant.descriptionArabic")} rows={4} dir="rtl" value={form.translations.ar?.description || ""} onChange={(e) => updateTranslation("ar", "description", e.target.value)} />
</label>
</div>
</div>
</fieldset>
<div className="ecommerce-editor-grid ecommerce-editor-basic-meta">
<label>{t("merchant.slug")}<input dir="ltr" value={form.slug} onChange={(e) => { setSlugManuallyEdited(true); update("slug", e.target.value); }} />
</label>
<label>{t("merchant.productSku")}<input dir="ltr" disabled={Boolean(form.options.length)} value={form.sku || ""} onChange={(e) => { setSkuManuallyEdited(true); update("sku", e.target.value); }} />
{form.options.length > 0 && <small className="ecommerce-editor-field-help">{t("admin.skuMovedToVariants")}</small>}
</label>
<label>{t("merchant.brand")}<input value={form.brand} onChange={(e) => update("brand", e.target.value)} />
<small className="ecommerce-editor-field-help">{t("merchant.brandHelp")}</small>
</label>
<label>{t("common.status")}<select value={form.status} onChange={(e) => update("status", e.target.value)}>
<option value="draft">{t("common.draft")}</option>
<option value="active">{t("common.active")}</option>
<option value="inactive">{t("common.inactive")}</option>
<option value="archived">{t("common.archived")}</option>
</select>
</label>
</div>
</section>
      <section>
<h2>{t("merchant.pricing")}</h2>
<div className="ecommerce-editor-grid">
<label>{t("merchant.basePrice")}<input type="number" min="0" step="0.01" required value={form.price} onChange={(e) => update("price", e.target.value)} />
</label>
<label><span className="ecommerce-editor-field-label">{t("merchant.comparePrice")} <span className="ecommerce-editor-field-optional">{t("admin.optional")}</span></span><input type="number" min="0.01" step="0.01" value={form.compare_at_price ?? ""} onChange={(e) => update("compare_at_price", e.target.value)} />
</label>
<label>{t("merchant.storeCurrency")}<input readOnly dir="ltr" value={catalog.commerce_currency || form.currency} />
</label>
</div>
</section>
<section>
<h2>{t("merchant.organizationMedia")}</h2>
<div className="ecommerce-editor-organization-grid">
<SearchableDropdown
  label={t("merchant.category")}
  items={[{ id: "", label: t("merchant.noCategory") }, ...catalog.categories.map((item) => ({ id: item.id, label: localize(item.translations) || item.name || item.slug }))]}
  value={form.category_id || ""}
  onChange={(value) => update("category_id", value || null)}
  searchLabel={t("merchant.searchCategories")}
  emptyLabel={t("merchant.noCategory")}
  noResultsLabel={t("merchant.noSearchResults")}
  selectionLabel={() => ""}
/>
<SearchableDropdown
  label={t("common.tags")}
  items={catalog.tags.map((item) => ({ id: item.id, label: localize(item.translations) || item.name || item.slug }))}
  value={form.tag_ids}
  multiple
  onChange={(value) => update("tag_ids", value)}
  searchLabel={t("merchant.searchTags")}
  emptyLabel={t("merchant.noTags")}
  noResultsLabel={t("merchant.noSearchResults")}
  selectionLabel={(count) => t("merchant.tagsSelected", { count })}
/>
</div>
<ProductMediaUploader
  items={form.images}
  busy={uploading === "product"}
  disabled={Boolean(uploading)}
  progress={uploadProgress}
  error={uploadError.target === "product" ? uploadError.message : ""}
  dragging={dragTarget === "product"}
  onDragging={(active) => setDragTarget(active ? "product" : "")}
  onFiles={(files) => { void uploadMedia(files); }}
  onRemove={(url) => update("images", form.images.filter((item) => item !== url))}
  t={t}
  label={t("admin.productGallery")}
/>
</section>
      <section className="ecommerce-editor-specifications">
<h2>{t("merchant.attributes")}</h2>
<p>{t("admin.attributesHelp")}</p>
{form.attributes.length > 0 && <div className="ecommerce-editor-spec-list">
{form.attributes.map((item, index) => <article className="ecommerce-editor-spec-card" key={item.id}>
<header className="ecommerce-editor-spec-card-header">
<div className="ecommerce-editor-spec-title"><span>{index + 1}</span><strong>{t("admin.specification")}</strong></div>
<div className="ecommerce-editor-row-actions">
<button className="ecommerce-editor-delete-icon" type="button" aria-label={t("admin.removeSpecification")} onClick={() => update("attributes", form.attributes.filter((entry) => entry.id !== item.id))}><Trash2 size={16} /></button>
</div>
</header>
<div className="ecommerce-editor-spec-fields">
<div className="ecommerce-editor-spec-field">
<strong>{t("admin.specification")}</strong>
<p>{t("admin.specificationNameHelp")}</p>
<label><span>{t("admin.english")}</span><input aria-label={t("admin.attributeNameEnglish")} placeholder={t("admin.specificationNameExampleEnglish")} dir="ltr" value={item.name_translations.en || ""} onChange={(e) => changeAttribute(item.id, "name_translations", { ...item.name_translations, en: e.target.value })} /></label>
<label><span>{t("admin.arabic")}</span><input aria-label={t("admin.attributeNameArabic")} placeholder={t("admin.specificationNameExampleArabic")} dir="rtl" value={item.name_translations.ar || ""} onChange={(e) => changeAttribute(item.id, "name_translations", { ...item.name_translations, ar: e.target.value })} /></label>
</div>
<div className="ecommerce-editor-spec-field">
<strong>{t("admin.specificationValue")}</strong>
<p>{t("admin.specificationValueHelp")}</p>
<label><span>{t("admin.english")}</span><input aria-label={t("admin.attributeValueEnglish")} placeholder={t("admin.specificationValueExampleEnglish")} dir="ltr" value={item.value_translations.en || ""} onChange={(e) => changeAttribute(item.id, "value_translations", { ...item.value_translations, en: e.target.value })} /></label>
<label><span>{t("admin.arabic")}</span><input aria-label={t("admin.attributeValueArabic")} placeholder={t("admin.specificationValueExampleArabic")} dir="rtl" value={item.value_translations.ar || ""} onChange={(e) => changeAttribute(item.id, "value_translations", { ...item.value_translations, ar: e.target.value })} /></label>
</div>
</div>
</article>)}
</div>}
<button className="ecommerce-primary-button" type="button" disabled={form.attributes.length >= 50} onClick={addAttribute}><Plus size={16} />{t("merchant.addAttribute")}</button>
</section>
      <section className="ecommerce-editor-options-variants">
        <h2>{t("merchant.variantAttributes")}</h2>
        <p>{t("admin.variantAttributesHelp")}</p>
        {merchantNotice && <p className="ecommerce-editor-notice" role="status">{merchantNotice}</p>}
        {!form.options.length ? (
          <button className="ecommerce-primary-button" type="button" onClick={addOption}>
            <Plus size={16} />{t("merchant.addVariantAttribute")}
          </button>
        ) : (
          <>
            <div className="ecommerce-editor-option-list">
              {form.options.map((option, optionIndex) => {
                const activeValues = activeOptionValues(option);
                const isExpanded = Boolean(expandedOptions[option.id]);
                const isColorType = option.display_type === "color";
                const isNamed = Boolean(option.name_translations?.en?.trim());
                const inlineForm = inlineValueForm?.optionId === option.id ? inlineValueForm : null;
                const editingValId = editingValue[option.id];

                return (
                  <article className="ecommerce-editor-option-card is-compact" key={option.id}>
                    <div className="ecommerce-editor-attribute-row">
                      <div className="ecommerce-editor-attribute-info">
                        <span className="ecommerce-editor-attribute-idx">{optionIndex + 1}</span>
                        <input
                          required
                          aria-label={t("admin.englishName")}
                          placeholder={t("admin.optionNameExampleEnglish")}
                          dir="ltr"
                          className="ecommerce-editor-option-name-input"
                          value={option.name_translations.en || ""}
                          onChange={(e) => changeOption(option.id, { name_translations: { ...option.name_translations, en: e.target.value } })}
                        />
                        <select
                          aria-label={t("admin.presentationType")}
                          className="ecommerce-editor-type-select"
                          value={option.display_type || "text"}
                          onChange={(e) => changeOption(option.id, {
                            display_type: e.target.value,
                            values: option.values.map((value) => ({
                              ...value,
                              color_hex: e.target.value === "color" ? value.color_hex || "#808080" : null,
                            })),
                          })}
                        >
                          <option value="text">{t("admin.textType")}</option>
                          <option value="color">{t("admin.colorType")}</option>
                        </select>
                        <span className="ecommerce-editor-value-count">
                          {activeValues.length} {activeValues.length === 1 ? "value" : "values"}
                        </span>
                        {!isNamed && (
                          <span className="ecommerce-editor-unnamed-warning">
                            {t("admin.nameAttributeNotice") || "Name this attribute before using it in variants."}
                          </span>
                        )}
                      </div>

                      <div className="ecommerce-editor-row-actions">
                        {isNamed && (
                          <button
                            className="ecommerce-editor-add-inline-btn"
                            type="button"
                            onClick={() => openInlineValueForm(option.id, isColorType ? "color" : "text")}
                          >
                            <Plus size={14} />
                            {isColorType ? (t("merchant.addColor") || "Add color") : (t("merchant.addValue") || "Add value")}
                          </button>
                        )}
                        <button
                          className={`ecommerce-editor-toggle-btn${isExpanded ? " is-expanded" : ""}`}
                          type="button"
                          aria-label={isExpanded ? t("admin.hideValues") : t("admin.manageValues")}
                          onClick={() => toggleOptionExpand(option.id)}
                        >
                          <ChevronDown size={15} className={`ecommerce-editor-chevron${isExpanded ? " is-rotated" : ""}`} />
                          <span>{isExpanded ? (t("admin.hideValues") || "Hide values") : (t("admin.manageValues") || "Manage values")}</span>
                        </button>
                        <button
                          className="ecommerce-editor-delete-icon"
                          type="button"
                          aria-label={t("admin.removeOption") || "Delete"}
                          title={t("common.delete") || "Delete"}
                          onClick={() => removeOption(option)}
                        >
                          <Trash2 size={16} />
                          <span>{t("common.delete") || "Delete"}</span>
                        </button>
                      </div>
                    </div>

                    {inlineForm && (
                      <div className="ecommerce-editor-inline-value-form">
                        {inlineForm.mode === "text" ? (
                          <>
                            <label>
                              <span>{t("admin.valueName") || "Value"}</span>
                              <input
                                dir="ltr"
                                autoFocus
                                aria-label={t("admin.valueName") || "Value"}
                                placeholder={t("admin.optionValueExample") || "42"}
                                value={inlineTextDraft}
                                onChange={(e) => setInlineTextDraft(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") { e.preventDefault(); submitInlineTextValue(option.id); }
                                  if (e.key === "Escape") closeInlineValueForm();
                                }}
                              />
                            </label>
                            <label>
                              <span>{t("admin.arabicValue") || "Arabic"}</span>
                              <input
                                dir="rtl"
                                aria-label={t("admin.arabicValue") || "Arabic"}
                                placeholder={t("admin.optionNameExampleArabic") || "٤٢"}
                                value={inlineTextDraftAr}
                                onChange={(e) => setInlineTextDraftAr(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") { e.preventDefault(); submitInlineTextValue(option.id); }
                                }}
                              />
                            </label>
                            <div className="ecommerce-editor-inline-value-actions">
                              <button
                                className="ecommerce-primary-button"
                                type="button"
                                disabled={!inlineTextDraft.trim()}
                                onClick={() => submitInlineTextValue(option.id)}
                              >
                                <Plus size={14} />{t("merchant.addValue") || "Add value"}
                              </button>
                              <button className="ecommerce-secondary-button" type="button" onClick={closeInlineValueForm}>
                                {t("common.cancel") || "Cancel"}
                              </button>
                            </div>
                          </>
                        ) : (
                          <>
                            <label>
                              <span>{t("admin.colorName") || "Color name"}</span>
                              <input
                                dir="ltr"
                                autoFocus
                                aria-label={t("admin.valueName") || "Value"}
                                placeholder="Red"
                                value={inlineColorDraft}
                                onChange={(e) => setInlineColorDraft(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") { e.preventDefault(); submitInlineColorValue(option.id); }
                                  if (e.key === "Escape") closeInlineValueForm();
                                }}
                              />
                            </label>
                            <label>
                              <span>{t("admin.arabicName") || "Arabic name"}</span>
                              <input
                                dir="rtl"
                                aria-label={t("admin.arabicValue") || "Arabic"}
                                placeholder="أحمر"
                                value={inlineColorDraftAr}
                                onChange={(e) => setInlineColorDraftAr(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") { e.preventDefault(); submitInlineColorValue(option.id); }
                                }}
                              />
                            </label>
                            <label className="ecommerce-editor-color-field">
                              <span>{t("admin.colorSwatch") || "Color swatch"}</span>
                              <span className="ecommerce-editor-color-pick-row">
                                <input
                                  aria-label={t("admin.colorSwatch") || "Color swatch"}
                                  type="color"
                                  value={/^#[0-9a-fA-F]{6}$/.test(inlineColorHex) ? inlineColorHex : "#808080"}
                                  onInput={(e) => setInlineColorHex(e.currentTarget.value.toUpperCase())}
                                  onChange={(e) => setInlineColorHex(e.target.value.toUpperCase())}
                                />
                                <input
                                  dir="ltr"
                                  className="ecommerce-editor-hex-input"
                                  aria-label="Hex"
                                  placeholder="#FF0000"
                                  value={inlineColorHex}
                                  onChange={(e) => {
                                    let v = e.target.value.toUpperCase();
                                    if (!v.startsWith("#") && v.length > 0) v = `#${v}`;
                                    setInlineColorHex(v);
                                  }}
                                />
                              </span>
                            </label>
                            <div className="ecommerce-editor-inline-value-actions">
                              <button
                                className="ecommerce-primary-button"
                                type="button"
                                disabled={!inlineColorDraft.trim()}
                                onClick={() => submitInlineColorValue(option.id)}
                              >
                                <Plus size={14} />{t("merchant.addColor") || "Add color"}
                              </button>
                              <button className="ecommerce-secondary-button" type="button" onClick={closeInlineValueForm}>
                                {t("common.cancel") || "Cancel"}
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    )}

                    {isExpanded && (
                      <div className="ecommerce-editor-managed-values">
                        {!activeValues.length ? (
                          <p className="ecommerce-editor-empty-values-hint">
                            {t("admin.addAtLeastOneValue", { option: option.name_translations.en }) || "No values yet."}
                          </p>
                        ) : (
                          <div className="ecommerce-editor-values-table">
                            {activeValues.map((value) => {
                              const isValEditing = editingValId === value.id;
                              const labelText = localize(value, "value") || value.code;
                              return (
                                <div className={`ecommerce-editor-value-entry${isValEditing ? " is-editing" : ""}`} key={value.id}>
                                  <div className="ecommerce-editor-value-entry-row">
                                    {isColorType && (
                                      <i
                                        className="ecommerce-color-swatch"
                                        style={{ backgroundColor: value.color_hex || "#808080" }}
                                        aria-hidden="true"
                                      />
                                    )}
                                    <button
                                      type="button"
                                      className="ecommerce-editor-value-name-btn"
                                      onClick={() => setEditingValue((cur) => ({ ...cur, [option.id]: isValEditing ? null : value.id }))}
                                    >
                                      <bdi>{labelText}</bdi>
                                    </button>
                                    {isColorType && (
                                      <code className="ecommerce-editor-color-value-hex">
                                        {(value.color_hex || "#808080").toUpperCase()}
                                      </code>
                                    )}
                                    <div className="ecommerce-editor-value-entry-actions">
                                      <button
                                        type="button"
                                        className="ecommerce-editor-val-action-btn"
                                        aria-label={t("admin.editOptionValue") || "Edit value"}
                                        onClick={() => setEditingValue((cur) => ({ ...cur, [option.id]: isValEditing ? null : value.id }))}
                                      >
                                        <Pencil size={13} />
                                        <span>{t("admin.edit") || "Edit"}</span>
                                      </button>
                                      <button
                                        type="button"
                                        className="ecommerce-editor-val-action-btn is-danger"
                                        aria-label={t("admin.removeOptionValue", { value: labelText })}
                                        onClick={() => removeValue(option, value)}
                                      >
                                        <Trash2 size={13} />
                                        <span>{t("admin.remove") || "Remove"}</span>
                                      </button>
                                    </div>
                                  </div>

                                  {isValEditing && (
                                    <div className="ecommerce-editor-value-edit-panel">
                                      <label>
                                        <span>{t("admin.englishValue") || "English"}</span>
                                        <input
                                          dir="ltr"
                                          value={value.value_translations?.en || ""}
                                          onChange={(e) => changeValue(option, value.id, {
                                            value_translations: { ...value.value_translations, en: e.target.value },
                                          })}
                                        />
                                      </label>
                                      <label>
                                        <span>{t("admin.arabicValue") || "Arabic"}</span>
                                        <input
                                          dir="rtl"
                                          value={value.value_translations?.ar || ""}
                                          onChange={(e) => changeValue(option, value.id, {
                                            value_translations: { ...value.value_translations, ar: e.target.value },
                                          })}
                                        />
                                      </label>
                                      {isColorType && (
                                        <label className="ecommerce-editor-color-field">
                                          <span>{t("admin.colorSwatch") || "Color swatch"}</span>
                                          <span className="ecommerce-editor-color-pick-row">
                                            <input
                                              aria-label={t("admin.colorSwatch") || "Color swatch"}
                                              type="color"
                                              value={/^#[0-9a-fA-F]{6}$/.test(value.color_hex || "") ? value.color_hex : "#808080"}
                                              onInput={(e) => changeValue(option, value.id, { color_hex: e.currentTarget.value.toUpperCase() })}
                                              onChange={(e) => changeValue(option, value.id, { color_hex: e.target.value.toUpperCase() })}
                                            />
                                            <input
                                              dir="ltr"
                                              className="ecommerce-editor-hex-input"
                                              aria-label="Hex"
                                              placeholder="#FF0000"
                                              value={value.color_hex || "#808080"}
                                              onChange={(e) => {
                                                let v = e.target.value.toUpperCase();
                                                if (!v.startsWith("#") && v.length > 0) v = `#${v}`;
                                                changeValue(option, value.id, { color_hex: v });
                                              }}
                                            />
                                          </span>
                                        </label>
                                      )}
                                      <button
                                        type="button"
                                        className="ecommerce-secondary-button ecommerce-editor-val-close-btn"
                                        aria-label={t("admin.closeValueEditor") || "Close"}
                                        onClick={() => setEditingValue((cur) => ({ ...cur, [option.id]: null }))}
                                      >
                                        {t("admin.close") || "Close"}
                                      </button>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
            <button className="ecommerce-primary-button" type="button" disabled={form.options.length >= 5} onClick={addOption}>
              <Plus size={16} />{t("merchant.addVariantAttribute")}
            </button>
          </>
        )}
      </section>

      {form.options.length > 0 && (
        <section className="ecommerce-variant-matrix">
          <header className="ecommerce-variant-matrix-header">
            <div>
              <h3>{t("merchant.variantsInventory")}</h3>
            </div>
            <div className="ecommerce-variant-matrix-header-actions">
              <button className="ecommerce-primary-button" type="button" onClick={addVariantRow}>
                <Plus size={16} />{t("merchant.addVariant")}
              </button>
            </div>
          </header>

          {form.variants.filter((v) => v.active !== false).length === 0 && (
            <p className="ecommerce-editor-inline-help">{t("admin.addVariantHelp")}</p>
          )}

          <div style={{ display: "none" }}>
            {form.options.filter((option) => Boolean(option.name_translations?.en?.trim())).map((option) => (
              <datalist key={option.id} id={`option-values-${option.id}`}>
                {activeOptionValues(option).map((value) => (
                  <option key={value.id} value={localize(value, "value") || value.code} />
                ))}
              </datalist>
            ))}
          </div>

          {form.variants.filter((v) => v.active !== false).length > 0 && (() => {
            const namedOptions = form.options.filter((option) => Boolean(option.name_translations?.en?.trim()));
            const gridCols = `${namedOptions.map(() => "minmax(130px, 1fr)").join(" ")} 85px minmax(140px, 1.4fr) 115px 85px 75px`;

            return (
              <div className="ecommerce-variant-matrix-table-wrap">
                <div className="ecommerce-variant-matrix-table">
                  <div className="ecommerce-variant-matrix-head" aria-hidden="true" style={{ gridTemplateColumns: gridCols }}>
                    {namedOptions.map((option) => (
                      <span key={option.id}>{option.name_translations.en}</span>
                    ))}
                    <span>{t("admin.quantity")}</span>
                    <span>{t("common.sku")}</span>
                    <span>{t("common.price")}</span>
                    <span>{t("admin.available")}</span>
                    <span>{t("admin.actions")}</span>
                  </div>

                  <div className="ecommerce-variant-matrix-group">
                    {form.variants.filter((variant) => variant.active !== false).map((variant) => {
                      const variantLabel = variant.option_value_ids.map((id) => localize(valueById.get(id), "value") || valueById.get(id)?.code).join(" / ");
                      return (
                        <div className="ecommerce-variant-matrix-row is-available" style={{ gridTemplateColumns: gridCols }} key={variant.id}>
                          {namedOptions.map((option) => {
                            const selectedId = getSelectedValueForOption(variant, option.id);
                            const selectedValue = selectedId ? valueById.get(selectedId) : null;
                            const isColorOpt = option.display_type === "color";

                            return (
                              <div className="ecommerce-variant-attr-cell" key={option.id}>
                                {isColorOpt && (
                                  <i
                                    className={`ecommerce-color-swatch${selectedValue?.color_hex ? "" : " ecommerce-color-swatch--empty"}`}
                                    style={{ backgroundColor: selectedValue?.color_hex || "transparent" }}
                                    aria-hidden="true"
                                  />
                                )}
                                <input
                                  list={`option-values-${option.id}`}
                                  dir="ltr"
                                  placeholder={option.name_translations.en || "..."}
                                  value={selectedId ? (localize(selectedValue, "value") || selectedValue?.code || "") : ""}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    if (!val.trim()) {
                                      updateVariantOption(variant.id, option.id, "");
                                      return;
                                    }
                                    const valueId = resolveOrCreateValue(option, val);
                                    if (valueId) updateVariantOption(variant.id, option.id, valueId);
                                  }}
                                />
                              </div>
                            );
                          })}

                          <label className="ecommerce-variant-qty-cell">
                            <input
                              aria-label={t("admin.variantQuantityLabel", { variant: variantLabel })}
                              type="number"
                              min="0"
                              value={variant.inventory_quantity ?? ""}
                              onChange={(e) => changeVariant(variant.id, { inventory_quantity: e.target.value })}
                            />
                          </label>

                          <label className="ecommerce-variant-sku-cell">
                            <input
                              aria-label={t("admin.variantSkuLabel", { variant: variantLabel })}
                              dir="ltr"
                              value={variant.sku || ""}
                              onChange={(e) => changeVariant(variant.id, { sku: e.target.value })}
                            />
                          </label>

                          <label className="ecommerce-variant-price-cell">
                            <input
                              className="ecommerce-variant-price-input"
                              aria-label={t("admin.variantPriceLabel", { variant: variantLabel })}
                              type="number"
                              min="0"
                              step="0.01"
                              placeholder={form.price}
                              value={variant.price_override ?? ""}
                              onChange={(e) => changeVariant(variant.id, { price_override: e.target.value })}
                            />
                            <span className="ecommerce-variant-currency">{catalog.commerce_currency}</span>
                          </label>

                          <div className="ecommerce-variant-avail-cell">
                            <label className="ecommerce-editor-switch" title={t("admin.available") || "Available"}>
                              <input
                                type="checkbox"
                                aria-label={t("admin.variantAvailabilityLabel", { variant: variantLabel }) || "Available"}
                                checked={variant.active !== false}
                                onChange={(e) => changeVariant(variant.id, { active: e.target.checked })}
                              />
                              <span className="ecommerce-editor-switch-slider" />
                            </label>
                          </div>

                          <div className="ecommerce-variant-row-actions">
                            <button
                              className="ecommerce-variant-delete-action"
                              type="button"
                              aria-label={t("admin.removeVariantLabel", { variant: variantLabel }) || "Delete"}
                              title={t("common.delete") || "Delete"}
                              onClick={() => removeVariantRow(variant.id)}
                            >
                              <Trash2 size={16} />
                              <span className="ecommerce-variant-delete-text">{t("common.delete") || "Delete"}</span>
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })()}
        </section>
      )}
      {!form.options.length && <section className="ecommerce-editor-inventory">
<h2>{t("merchant.inventory")}</h2><div className="ecommerce-editor-grid ecommerce-editor-inventory-fields">
<label>{t("merchant.currentStock")}<input type="number" min="0" value={form.inventory_quantity} onChange={(e) => update("inventory_quantity", e.target.value)} />
</label>
<label>{t("merchant.lowThreshold")}<input type="number" min="0" value={form.low_stock_threshold} onChange={(e) => update("low_stock_threshold", e.target.value)} />
</label>
</div>
<div className="ecommerce-editor-inventory-checks">
<Checkbox checked={form.track_inventory} onChange={(e) => update("track_inventory", e.target.checked)}>{t("merchant.trackInventory")}</Checkbox>
<Checkbox checked={form.allow_backorder} onChange={(e) => update("allow_backorder", e.target.checked)}>{t("merchant.allowBackorder")}</Checkbox>
</div></section>}
      <footer>
{embedded ? <button type="button" className="ecommerce-secondary-button" onClick={onClose}>{t("common.cancel")}</button> : <Link to={DASHBOARD_ROUTES.ecommerceProducts}>{t("common.cancel")}</Link>}
<button className="ecommerce-primary-button" disabled={state.saving}>
<Save size={17} />{t("merchant.saveProduct")}</button>
</footer>
    </form>
  );
}

export default function EcommerceProductEditorPage({ user }) {
  const { productId } = useParams();
  const navigate = useNavigate();
  const closeEditor = () => navigate(DASHBOARD_ROUTES.ecommerceProducts);
  return <EcommerceProductEditor user={user} productId={productId} onClose={closeEditor} onSaved={closeEditor} />;
}
