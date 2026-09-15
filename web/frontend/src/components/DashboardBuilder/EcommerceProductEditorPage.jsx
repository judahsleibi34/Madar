import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, ChevronDown, ImagePlus, Plus, Save, Search, Trash2, X } from "lucide-react";
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
const buildCombinations = (options) => {
  if (!options.length || options.some((option) => !activeOptionValues(option).length)) return [];
  return options.reduce(
    (combinations, option) => combinations.flatMap((ids) => activeOptionValues(option).map((value) => [...ids, value.id])),
    [[]],
  );
};

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
  const scope = user?.id ? `user-${user.id}` : "authenticated";
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
  const [selectedCombinations, setSelectedCombinations] = useState(() => new Set());
  const [valueDrafts, setValueDrafts] = useState({});
  const [editingValue, setEditingValue] = useState({});
  const [merchantNotice, setMerchantNotice] = useState("");
  const [selectedVariantIds, setSelectedVariantIds] = useState(() => new Set());
  const persistedVariantIds = useRef(new Set());
  const referencedValueIds = useRef(new Set());

  useEffect(() => {
    if (initialCatalog && !editing) {
      setCatalog(initialCatalog);
      setForm(emptyProduct(initialCatalog.commerce_currency));
      setState({ loading: false, saving: false, error: "" });
      return undefined;
    }
    let cancelled = false;
    fetchEcommerceCatalog({ scope, force: true }).then((result) => {
      if (cancelled) return;
      const product = result.products?.find((item) => item.id === productId);
      if (editing && !product) throw new Error(t("commerce:errors.productNotFound"));
      persistedVariantIds.current = new Set((product?.variants || []).map((variant) => variant.id));
      referencedValueIds.current = new Set((product?.variants || []).flatMap((variant) => variant.option_value_ids || []));
      setCatalog(result);
      setForm(product ? { ...emptyProduct(result.commerce_currency), ...product, attributes: product.attributes || [], options: product.options || [], variants: product.variants || [] } : emptyProduct(result.commerce_currency));
      setState({ loading: false, saving: false, error: "" });
    }).catch((error) => !cancelled && setState({ loading: false, saving: false, error: error.message || t("commerce:errors.loadProduct") }));
    return () => { cancelled = true; };
  }, [editing, initialCatalog, productId, scope, t]);

  const valueById = useMemo(() => new Map(form.options.flatMap((option) => option.values || []).map((value) => [value.id, value])), [form.options]);
  const optionIdByValueId = useMemo(() => new Map(form.options.flatMap((option) => (option.values || []).map((value) => [value.id, option.id]))), [form.options]);
  const variantValuesInOptionOrder = (variant) => form.options.map((option) => variant.option_value_ids.find((id) => optionIdByValueId.get(id) === option.id) || "");
  const possibleCombinations = useMemo(() => buildCombinations(form.options), [form.options]);
  const existingCombinationKeys = useMemo(() => new Set(form.variants.map((variant) => combinationKey(form.options.map((option) => variant.option_value_ids.find((id) => optionIdByValueId.get(id) === option.id) || "")))), [form.options, form.variants, optionIdByValueId]);
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
  const addOption = () => update("options", [...form.options, { id: uuid(), code: "", name_translations: { en: "" }, required: true, sort_order: form.options.length, values: [] }]);
  const changeOption = (id, change) => update("options", form.options.map((item) => item.id === id ? { ...item, ...change } : item));
  const addValue = (option, rawValue) => {
    const label = String(rawValue || "").trim();
    if (!label) return;
    if (activeOptionValues(option).some((value) => String(value.value_translations?.en || "").trim().toLocaleLowerCase() === label.toLocaleLowerCase())) {
      setMerchantNotice(t("admin.duplicateOptionValue", { option: option.name_translations?.en || t("merchant.options") }));
      return;
    }
    const nextValue = { id: uuid(), code: "", value_translations: { en: label }, sort_order: option.values.length, active: true };
    changeOption(option.id, { values: [...option.values, nextValue] });
    setValueDrafts((current) => ({ ...current, [option.id]: "" }));
    setEditingValue((current) => ({ ...current, [option.id]: nextValue.id }));
    setMerchantNotice("");
  };
  const changeValue = (option, valueId, change) => changeOption(option.id, { values: option.values.map((value) => value.id === valueId ? { ...value, ...change } : value) });
  const removeValue = (option, value) => {
    if (referencedValueIds.current.has(value.id) || form.variants.some((variant) => variant.option_value_ids.includes(value.id))) {
      changeValue(option, value.id, { active: false });
      setMerchantNotice(t("admin.referencedValueArchived", { value: localize(value, "value") || value.code }));
      return;
    }
    changeOption(option.id, { values: option.values.filter((entry) => entry.id !== value.id) });
    setMerchantNotice("");
  };
  const removeOption = (option) => {
    const valueIds = new Set((option.values || []).map((value) => value.id));
    if (form.variants.some((variant) => variant.option_value_ids.some((id) => valueIds.has(id)))) {
      setMerchantNotice(t("admin.optionUsedByVariant"));
      return;
    }
    update("options", form.options.filter((entry) => entry.id !== option.id));
    setMerchantNotice("");
  };
  const newVariant = (optionValueIds) => {
    const suffix = optionValueIds.map((id) => code(valueById.get(id)?.value_translations?.en, "value").toUpperCase()).join("-");
    return { id: uuid(), sku: `${form.sku || skuCode(form.translations.en.name, autoSkuSuffix)}-${suffix}`.slice(0, 120), barcode: null, price_override: null, compare_at_price_override: null, track_inventory: true, inventory_quantity: 0, low_stock_threshold: 5, allow_backorder: false, images: [], active: true, option_value_ids: optionValueIds };
  };
  const createSelectedVariants = () => {
    const additions = possibleCombinations.filter((ids) => selectedCombinations.has(combinationKey(ids)) && !existingCombinationKeys.has(combinationKey(ids))).map(newVariant);
    if (!additions.length) return;
    update("variants", [...form.variants, ...additions]);
    setSelectedCombinations(new Set());
    setMerchantNotice(t("admin.variantsCreated", { count: additions.length }));
  };
  const changeVariant = (id, change) => update("variants", form.variants.map((item) => item.id === id ? { ...item, ...change } : item));
  const bulkChangeVariants = (change) => {
    if (!selectedVariantIds.size) return;
    update("variants", form.variants.map((variant) => selectedVariantIds.has(variant.id) ? { ...variant, ...change } : variant));
    setMerchantNotice(t("admin.variantsUpdated", { count: selectedVariantIds.size }));
  };
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
    }
    const variantKeys = form.variants.map((variant) => combinationKey(variant.option_value_ids));
    if (new Set(variantKeys).size !== variantKeys.length) return t("admin.validationDuplicateCombination");
    const skus = form.variants.map((variant) => String(variant.sku || "").trim().toLocaleLowerCase());
    if (skus.some((sku) => !sku)) return t("admin.validationVariantSku");
    if (new Set(skus).size !== skus.length) return t("admin.validationUniqueSku");
    for (const variant of form.variants) {
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
  const move = (items, index, delta) => {
    const target = index + delta;
    if (target < 0 || target >= items.length) return items;
    const reordered = [...items];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    return reordered;
  };
  const uploadMedia = async (files, variantId = null) => {
    const target = variantId || "product";
    const current = variantId ? form.variants.find((item) => item.id === variantId)?.images || [] : form.images || [];
    const selected = Array.from(files || []);
    if (!selected.length) return;
    const showUploadError = (message) => setUploadError({ target, message });
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
    } catch (error) {
      showUploadError(error.message || t("commerce:errors.uploadMedia"));
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
        options: form.options.map((option, index) => ({ ...option, code: code(option.code || option.name_translations.en, `option-${index + 1}`), sort_order: index, name_translations: localized(option.name_translations.en, option.name_translations.ar), values: option.values.map((value, valueIndex) => ({ ...value, code: code(value.code || value.value_translations.en, `value-${valueIndex + 1}`), sort_order: valueIndex, value_translations: localized(value.value_translations.en, value.value_translations.ar) })) })),
        variants: form.variants.map((variant) => ({ ...variant, sku: variant.sku.trim(), barcode: variant.barcode || null, price_override: variant.price_override === "" || variant.price_override == null ? null : Number(variant.price_override), compare_at_price_override: variant.compare_at_price_override === "" || variant.compare_at_price_override == null ? null : Number(variant.compare_at_price_override), inventory_quantity: Number(variant.inventory_quantity || 0), low_stock_threshold: Number(variant.low_stock_threshold || 0), option_value_ids: variant.option_value_ids.filter(Boolean) })),
      };
      const savedProduct = await saveEcommerceItem("products", productId, payload, { scope });
      onSaved?.(savedProduct);
    } catch (error) {
      setState((current) => ({ ...current, saving: false, error: error.message || t("commerce:errors.saveProduct") }));
    }
  };

  if (state.loading) return <section className="ecommerce-product-editor" dir={direction}>
<p>{t("merchant.loadingProduct")}</p>
</section>;
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
{form.attributes.length > 0 && <div className="ecommerce-editor-spec-table">
<div className="ecommerce-editor-spec-head"><span>{t("admin.specification")}</span><span>{t("admin.specificationValue")}</span><span aria-hidden="true" /></div>
{form.attributes.map((item, index) => <div className="ecommerce-editor-spec-row" key={item.id}>
<div>
<input aria-label={t("admin.attributeNameEnglish")} placeholder={t("admin.englishName")} dir="ltr" value={item.name_translations.en || ""} onChange={(e) => changeAttribute(item.id, "name_translations", { ...item.name_translations, en: e.target.value })} />
<input aria-label={t("admin.attributeNameArabic")} placeholder={t("admin.arabicName")} dir="rtl" value={item.name_translations.ar || ""} onChange={(e) => changeAttribute(item.id, "name_translations", { ...item.name_translations, ar: e.target.value })} />
</div>
<div>
<input aria-label={t("admin.attributeValueEnglish")} placeholder={t("admin.englishValue")} dir="ltr" value={item.value_translations.en || ""} onChange={(e) => changeAttribute(item.id, "value_translations", { ...item.value_translations, en: e.target.value })} />
<input aria-label={t("admin.attributeValueArabic")} placeholder={t("admin.arabicValue")} dir="rtl" value={item.value_translations.ar || ""} onChange={(e) => changeAttribute(item.id, "value_translations", { ...item.value_translations, ar: e.target.value })} />
</div>
<div className="ecommerce-editor-row-actions">
<button type="button" aria-label={t("admin.moveAttributeUp")} disabled={!index} onClick={() => update("attributes", move(form.attributes, index, -1))}><ArrowUp size={15} /></button>
<button type="button" aria-label={t("admin.moveAttributeDown")} disabled={index === form.attributes.length - 1} onClick={() => update("attributes", move(form.attributes, index, 1))}><ArrowDown size={15} /></button>
<button type="button" aria-label={t("admin.removeSpecification")} onClick={() => update("attributes", form.attributes.filter((entry) => entry.id !== item.id))}><Trash2 size={16} /></button>
</div>
</div>)}
</div>}
<button type="button" disabled={form.attributes.length >= 50} onClick={addAttribute}><Plus size={16} />{t("merchant.addAttribute")}</button>
</section>
      <section className="ecommerce-editor-options-variants">
<h2>{t("merchant.optionsVariants")}</h2>
<p>{t("admin.optionsVariantsHelp")}</p>
{merchantNotice && <p className="ecommerce-editor-notice" role="status">{merchantNotice}</p>}
{!form.options.length ? <div className="ecommerce-editor-empty-state">
<strong>{t("admin.noOptionsTitle")}</strong>
<p>{t("admin.noOptionsHelp")}</p>
<button type="button" onClick={addOption}><Plus size={16} />{t("merchant.addOptions")}</button>
</div> : <>
<div className="ecommerce-editor-option-list">
{form.options.map((option, optionIndex) => {
  const activeValues = activeOptionValues(option);
  const selectedValue = option.values.find((value) => value.id === editingValue[option.id] && value.active !== false);
  return <article className="ecommerce-editor-option-card" key={option.id}>
    <header>
      <strong>{option.name_translations.en || t("admin.untitledOption", { count: optionIndex + 1 })}</strong>
      <div className="ecommerce-editor-row-actions">
        <button type="button" aria-label={t("admin.moveOptionUp")} disabled={!optionIndex} onClick={() => update("options", move(form.options, optionIndex, -1))}><ArrowUp size={15} /></button>
        <button type="button" aria-label={t("admin.moveOptionDown")} disabled={optionIndex === form.options.length - 1} onClick={() => update("options", move(form.options, optionIndex, 1))}><ArrowDown size={15} /></button>
        <button type="button" aria-label={t("admin.removeOption")} onClick={() => removeOption(option)}><Trash2 size={16} /></button>
      </div>
    </header>
    <div className="ecommerce-editor-option-names">
      <label>{t("admin.englishName")}<input required dir="ltr" value={option.name_translations.en || ""} onChange={(e) => changeOption(option.id, { name_translations: { ...option.name_translations, en: e.target.value } })} /></label>
      <label>{t("admin.arabicName")}<input dir="rtl" value={option.name_translations.ar || ""} onChange={(e) => changeOption(option.id, { name_translations: { ...option.name_translations, ar: e.target.value } })} /></label>
    </div>
    <Checkbox checked={option.required} onChange={(e) => changeOption(option.id, { required: e.target.checked })} ariaLabel={t("admin.requiredOptionLabel", { option: option.name_translations.en || optionIndex + 1 })}>{t("admin.customerMustChoose")}</Checkbox>
    <span className="ecommerce-editor-values-label">{t("admin.values")}</span>
    <div className="ecommerce-editor-value-chips">
      {activeValues.map((value) => <span className={editingValue[option.id] === value.id ? "is-editing" : ""} key={value.id}>
        <button type="button" onClick={() => setEditingValue((current) => ({ ...current, [option.id]: value.id }))}><bdi>{localize(value, "value") || value.code}</bdi></button>
        <button type="button" aria-label={t("admin.removeOptionValue", { value: localize(value, "value") || value.code })} onClick={() => removeValue(option, value)}><X size={14} /></button>
      </span>)}
      {!activeValues.length && <small>{t("admin.addAtLeastOneValue", { option: option.name_translations.en || t("merchant.options") })}</small>}
    </div>
    <div className="ecommerce-editor-add-value">
      <input aria-label={t("admin.newValueForOption", { option: option.name_translations.en || optionIndex + 1 })} dir="ltr" placeholder={t("admin.valueEntryPlaceholder")} value={valueDrafts[option.id] || ""} onChange={(event) => setValueDrafts((current) => ({ ...current, [option.id]: event.target.value }))} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addValue(option, event.currentTarget.value); } }} />
      <button type="button" disabled={activeValues.length >= 50 || !(valueDrafts[option.id] || "").trim()} onClick={() => addValue(option, valueDrafts[option.id])}><Plus size={16} />{t("merchant.addValue")}</button>
    </div>
    {selectedValue && <div className="ecommerce-editor-value-edit">
      <div>
        <label>{t("admin.englishValue")}<input dir="ltr" value={selectedValue.value_translations.en || ""} onChange={(e) => changeValue(option, selectedValue.id, { value_translations: { ...selectedValue.value_translations, en: e.target.value } })} /></label>
        <label>{t("admin.arabicValue")}<input dir="rtl" value={selectedValue.value_translations.ar || ""} onChange={(e) => changeValue(option, selectedValue.id, { value_translations: { ...selectedValue.value_translations, ar: e.target.value } })} /></label>
      </div>
      <div className="ecommerce-editor-row-actions">
        {(() => { const valueIndex = option.values.findIndex((value) => value.id === selectedValue.id); return <>
          <button type="button" aria-label={t("admin.moveValueUp")} disabled={!valueIndex} onClick={() => changeOption(option.id, { values: move(option.values, valueIndex, -1) })}><ArrowUp size={15} /></button>
          <button type="button" aria-label={t("admin.moveValueDown")} disabled={valueIndex === option.values.length - 1} onClick={() => changeOption(option.id, { values: move(option.values, valueIndex, 1) })}><ArrowDown size={15} /></button>
        </>; })()}
      </div>
    </div>}
  </article>;
})}
</div>
<button type="button" disabled={form.options.length >= 5} onClick={addOption}><Plus size={16} />{t("merchant.addAnotherOption")}</button>
<div className="ecommerce-editor-combination-builder">
<header><div><h3>{t("admin.chooseSellableCombinations")}</h3><p>{t("admin.combinationPreviewHelp")}</p></div><strong>{t("admin.possibleCombinations", { count: possibleCombinations.length })}</strong></header>
{possibleCombinations.length ? <>
<div className="ecommerce-editor-combination-actions">
<button type="button" onClick={() => setSelectedCombinations(new Set(possibleCombinations.filter((ids) => !existingCombinationKeys.has(combinationKey(ids))).map(combinationKey)))}>{t("admin.selectAllAvailable")}</button>
<button type="button" onClick={() => setSelectedCombinations(new Set())}>{t("admin.clearSelection")}</button>
</div>
<div className="ecommerce-editor-combination-grid">
{possibleCombinations.map((ids) => {
  const key = combinationKey(ids);
  const exists = existingCombinationKeys.has(key);
  const label = ids.map((id) => localize(valueById.get(id), "value") || valueById.get(id)?.code).join(" / ");
  return <Checkbox key={key} checked={exists || selectedCombinations.has(key)} ariaLabel={label} onChange={() => {
    if (exists) return;
    setSelectedCombinations((current) => { const next = new Set(current); next.has(key) ? next.delete(key) : next.add(key); return next; });
  }}><bdi>{label}</bdi>{exists && <small>{t("admin.alreadyCreated")}</small>}</Checkbox>;
})}
</div>
<button className="ecommerce-primary-button" type="button" disabled={!selectedCombinations.size} onClick={createSelectedVariants}><Plus size={16} />{t("admin.createSelectedVariants", { count: selectedCombinations.size })}</button>
</> : <p className="ecommerce-editor-inline-help">{t("admin.completeOptionValues")}</p>}
</div>
{form.variants.length > 0 && <div className="ecommerce-editor-variant-manager">
<header><div><h3>{t("admin.manageVariants")}</h3><p>{t("admin.variantManagementHelp")}</p></div><span>{t("admin.variantCount", { count: form.variants.length })}</span></header>
<div className="ecommerce-editor-bulk-actions">
<span>{t("admin.selectedVariants", { count: selectedVariantIds.size })}</span>
<button type="button" disabled={!selectedVariantIds.size} onClick={() => bulkChangeVariants({ active: true })}>{t("admin.activate")}</button>
<button type="button" disabled={!selectedVariantIds.size} onClick={() => bulkChangeVariants({ active: false })}>{t("admin.deactivate")}</button>
<button type="button" disabled={!selectedVariantIds.size} onClick={() => bulkChangeVariants({ price_override: null })}>{t("admin.inheritBasePrice")}</button>
<button type="button" disabled={!selectedVariantIds.size} onClick={() => bulkChangeVariants({ allow_backorder: true })}>{t("admin.enableBackorders")}</button>
<button type="button" disabled={!selectedVariantIds.size} onClick={() => bulkChangeVariants({ allow_backorder: false })}>{t("admin.disableBackorders")}</button>
</div>
<div className="ecommerce-editor-variant-table-wrap"><table className="ecommerce-editor-variant-table">
<thead><tr><th><input type="checkbox" aria-label={t("admin.selectAllVariants")} checked={form.variants.length > 0 && selectedVariantIds.size === form.variants.length} onChange={(event) => setSelectedVariantIds(event.target.checked ? new Set(form.variants.map((variant) => variant.id)) : new Set())} /></th><th>{t("admin.variant")}</th><th>{t("common.sku")}</th><th>{t("common.price")}</th><th>{t("merchant.inventory")}</th><th>{t("common.status")}</th><th>{t("admin.actions")}</th></tr></thead>
<tbody>{form.variants.map((variant, variantIndex) => {
  const orderedValueIds = variantValuesInOptionOrder(variant);
  const variantLabel = orderedValueIds.map((id) => localize(valueById.get(id), "value") || valueById.get(id)?.code).filter(Boolean).join(" / ") || t("admin.incompleteCombination");
  return <tr key={variant.id}>
    <td><input type="checkbox" aria-label={t("admin.selectVariant", { variant: variantLabel })} checked={selectedVariantIds.has(variant.id)} onChange={() => setSelectedVariantIds((current) => { const next = new Set(current); next.has(variant.id) ? next.delete(variant.id) : next.add(variant.id); return next; })} /></td>
    <td data-label={t("admin.variant")}><strong><bdi>{variantLabel}</bdi></strong></td>
    <td data-label={t("common.sku")}><bdi>{variant.sku}</bdi></td>
    <td data-label={t("common.price")}><bdi>{variant.price_override === "" || variant.price_override == null ? t("admin.inheritPrice", { price: form.price, currency: catalog.commerce_currency }) : `${variant.price_override} ${catalog.commerce_currency}`}</bdi></td>
    <td data-label={t("merchant.inventory")}><bdi>{variant.track_inventory ? variant.inventory_quantity : t("stock.untracked")}</bdi></td>
    <td data-label={t("common.status")}><span className={variant.active ? "ecommerce-variant-status is-active" : "ecommerce-variant-status"}>{variant.active ? t("common.active") : t("common.inactive")}</span></td>
    <td><details className="ecommerce-editor-variant-details"><summary>{t("admin.editDetails")}</summary><div className="ecommerce-editor-variant-panel">
      <header className="ecommerce-editor-variant-panel-header"><h4><bdi>{variantLabel}</bdi></h4><button type="button" aria-label={t("admin.closeVariantDetails")} onClick={(event) => event.currentTarget.closest("details")?.removeAttribute("open")}><X size={17} /></button></header>
      <div className="ecommerce-editor-grid">
        {form.options.map((option, optionIndex) => <label key={option.id}>{localize(option, "name") || t("admin.untitledOption", { count: optionIndex + 1 })}<select required={option.required} value={orderedValueIds[optionIndex]} onChange={(e) => { const ids = variant.option_value_ids.filter((id) => optionIdByValueId.get(id) !== option.id); if (e.target.value) ids.push(e.target.value); changeVariant(variant.id, { option_value_ids: ids }); }}><option value="">{t("admin.chooseValue")}</option>{option.values.map((value) => <option value={value.id} key={value.id}>{localize(value, "value") || value.code}{value.active === false ? ` — ${t("common.archived")}` : ""}</option>)}</select></label>)}
        <label>{t("merchant.variantSku")}<input dir="ltr" required value={variant.sku} onChange={(e) => changeVariant(variant.id, { sku: e.target.value })} /></label>
        <label>{t("common.barcode")}<input dir="ltr" value={variant.barcode || ""} onChange={(e) => changeVariant(variant.id, { barcode: e.target.value })} /></label>
        <label>{t("merchant.priceOverride")}<input type="number" min="0" step="0.01" placeholder={t("merchant.inheritBase")} value={variant.price_override ?? ""} onChange={(e) => changeVariant(variant.id, { price_override: e.target.value })} /></label>
        <label>{t("merchant.compareOverride")}<input type="number" min="0" step="0.01" placeholder={t("merchant.inheritBase")} value={variant.compare_at_price_override ?? ""} onChange={(e) => changeVariant(variant.id, { compare_at_price_override: e.target.value })} /></label>
        <label>{t("merchant.inventory")}<input type="number" min="0" value={variant.inventory_quantity} onChange={(e) => changeVariant(variant.id, { inventory_quantity: e.target.value })} /></label>
        <label>{t("merchant.lowThreshold")}<input type="number" min="0" value={variant.low_stock_threshold} onChange={(e) => changeVariant(variant.id, { low_stock_threshold: e.target.value })} /></label>
      </div>
      <div className="ecommerce-editor-checks">
        <Checkbox checked={variant.track_inventory} onChange={(e) => changeVariant(variant.id, { track_inventory: e.target.checked })}>{t("merchant.trackInventory")}</Checkbox>
        <Checkbox checked={variant.allow_backorder} onChange={(e) => changeVariant(variant.id, { allow_backorder: e.target.checked })}>{t("merchant.allowBackorder")}</Checkbox>
        <Checkbox checked={variant.active} onChange={(e) => changeVariant(variant.id, { active: e.target.checked })}>{t("common.active")}</Checkbox>
      </div>
      <ProductMediaUploader items={variant.images || []} busy={uploading === variant.id} disabled={Boolean(uploading)} progress={uploadProgress} error={uploadError.target === variant.id ? uploadError.message : ""} dragging={dragTarget === variant.id} onDragging={(active) => setDragTarget(active ? variant.id : "")} onFiles={(files) => { void uploadMedia(files, variant.id); }} onRemove={(url) => changeVariant(variant.id, { images: (variant.images || []).filter((item) => item !== url) })} t={t} label={t("admin.variantMediaLabel", { count: variantIndex + 1 })} />
      {!persistedVariantIds.current.has(variant.id) && <button type="button" className="ecommerce-editor-remove-unsaved" onClick={() => update("variants", form.variants.filter((entry) => entry.id !== variant.id))}><Trash2 size={16} />{t("admin.removeUnsavedVariant")}</button>}
    </div></details></td>
  </tr>;
})}</tbody></table></div>
</div>}
</>}
</section>
      <section>
<h2>{t("merchant.inventory")}</h2>{form.options.length ? <p>{t("merchant.variantInventoryHelp")}</p> : <div className="ecommerce-editor-grid">
<label>{t("merchant.currentStock")}<input type="number" min="0" value={form.inventory_quantity} onChange={(e) => update("inventory_quantity", e.target.value)} />
</label>
<label>{t("merchant.lowThreshold")}<input type="number" min="0" value={form.low_stock_threshold} onChange={(e) => update("low_stock_threshold", e.target.value)} />
</label>
<label>
<input type="checkbox" checked={form.allow_backorder} onChange={(e) => update("allow_backorder", e.target.checked)} />{t("merchant.allowBackorder")}</label>
<Checkbox checked={form.track_inventory} onChange={(e) => update("track_inventory", e.target.checked)}>{t("merchant.trackInventory")}</Checkbox>
</div>}</section>
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
