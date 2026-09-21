import { getEcommerceCacheScope } from "./utils/ecommerceAdminCache";
import { ProductEditorSkeleton } from "./CommerceLoadingLayouts";
import { notifyCommerceAction } from "../../utils/commerceActionToast";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ChevronDown, ImagePlus, Plus, Save, Search, Trash2, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { DASHBOARD_ROUTES } from "../../config/routes";
import { fetchEcommerceCatalog, saveEcommerceItem, saveEcommerceProductVariants, uploadEcommerceProductImage } from "../../services/ecommerceApi";
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
  variantOptionId: uuid(), colorOptionId: uuid(), variantGroups: [], hadVariantInventory: false,
});

const validHex = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ""));
const emptyVariantColor = () => ({
  id: uuid(), valueId: uuid(), colorName: "", colorValue: "", quantity: 0,
  sku: "", barcode: null, price_override: null, compare_at_price_override: null,
  track_inventory: true, low_stock_threshold: 5, allow_backorder: false, images: [], active: true,
});
const emptyVariantGroup = () => ({ id: uuid(), name: "", colors: [emptyVariantColor()] });
const variantInventoryIsFilled = (groups) => {
  if (!groups.length) return false;
  for (const group of groups) {
    if (!String(group.name || "").trim() || !group.colors.length) return false;
    for (const color of group.colors) {
      if (!String(color.colorName || "").trim() || !String(color.colorValue || "").trim()) return false;
    }
  }
  return true;
};

const hydrateVariantGroups = (product) => {
  const options = product?.options || [];
  const variants = (product?.variants || []).filter((variant) => variant.active !== false);
  const colorOption = options.find((option) => String(option.code || "").toLocaleLowerCase() === "color")
    || options.find((option) => String(option.name_translations?.en || "").trim().toLocaleLowerCase() === "color")
    || options.find((option) => option.display_type === "color")
    || options.find((option) => (option.values || []).some((value) => validHex(value.color_hex)));
  const variantOption = options.find((option) => option.id !== colorOption?.id);
  const valueById = new Map(options.flatMap((option) => (option.values || []).map((value) => [value.id, value])));
  const groups = [];
  const groupById = new Map();

  for (const variant of variants) {
    const selected = (variant.option_value_ids || []).map((id) => valueById.get(id)).filter(Boolean);
    const variantValue = selected.find((value) => (variantOption?.values || []).some((candidate) => candidate.id === value.id));
    const colorValue = selected.find((value) => (colorOption?.values || []).some((candidate) => candidate.id === value.id));
    const fallbackName = selected.filter((value) => value.id !== colorValue?.id).map((value) => value.value_translations?.en || value.code).join(" / ");
    const groupId = variantValue?.id || variant.id;
    let group = groupById.get(groupId);
    if (!group) {
      group = { id: groupId, name: variantValue?.value_translations?.en || fallbackName || "", colors: [] };
      groups.push(group);
      groupById.set(groupId, group);
    }
    group.colors.push({
      ...variant,
      valueId: colorValue?.id || uuid(),
      colorName: colorValue?.value_translations?.en || "",
      colorValue: colorValue?.color_hex || "",
      quantity: Number(variant.inventory_quantity || 0),
    });
  }

  return {
    variantOptionId: variantOption?.id || uuid(),
    colorOptionId: colorOption?.id || uuid(),
    variantGroups: groups,
    hadVariantInventory: Boolean(options.length || variants.length),
  };
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
  const [expandedVariants, setExpandedVariants] = useState({});

  useEffect(() => {
    let cancelled = false;
    if (initialCatalog && !editing) {
      return () => { cancelled = true; };
    }
    fetchEcommerceCatalog({ scope, force: true }).then((result) => {
      if (cancelled) return;
      const product = result.products?.find((item) => item.id === productId);
      if (editing && !product) throw new Error(t("commerce:errors.productNotFound"));
      setCatalog(result);
      setForm(product ? {
        ...emptyProduct(result.commerce_currency),
        ...product,
        attributes: product.attributes || [],
        ...hydrateVariantGroups(product),
      } : emptyProduct(result.commerce_currency));
      setState({ loading: false, saving: false, error: "" });
    }).catch(() => {
      if (cancelled) return;
      setState({ loading: false, saving: false, error: t("commerce:errors.loadProduct") });
      notifyCommerceAction({ type: "error", title: t("commerce:errors.loadProduct"), message: t("admin.tryAgain") });
    });
    return () => { cancelled = true; };
  }, [editing, initialCatalog, productId, scope, t]);

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
  const addVariantGroup = () => {
    const group = emptyVariantGroup();
    setForm((current) => ({ ...current, variantGroups: [...current.variantGroups, group] }));
    setExpandedVariants((current) => ({ ...current, [group.id]: true }));
  };
  const changeVariantGroup = (groupId, change) => setForm((current) => ({
    ...current,
    variantGroups: current.variantGroups.map((group) => group.id === groupId ? { ...group, ...change } : group),
  }));
  const removeVariantGroup = (groupId) => setForm((current) => ({
    ...current,
    variantGroups: current.variantGroups.filter((group) => group.id !== groupId),
  }));
  const addVariantColor = (groupId) => setForm((current) => ({
    ...current,
    variantGroups: current.variantGroups.map((group) => group.id === groupId
      ? { ...group, colors: [...group.colors, emptyVariantColor()] }
      : group),
  }));
  const changeVariantColor = (groupId, colorId, change) => setForm((current) => ({
    ...current,
    variantGroups: current.variantGroups.map((group) => group.id === groupId
      ? { ...group, colors: group.colors.map((color) => color.id === colorId ? { ...color, ...change } : color) }
      : group),
  }));
  const removeVariantColor = (groupId, colorId) => setForm((current) => ({
    ...current,
    variantGroups: current.variantGroups.map((group) => group.id === groupId && group.colors.length > 1
      ? { ...group, colors: group.colors.filter((color) => color.id !== colorId) }
      : group),
  }));
  const validateVariantInventory = () => {
    if (form.status === "active" && form.hadVariantInventory && !form.variantGroups.length) return t("admin.validationSellableVariant");
    const names = form.variantGroups.map((group) => group.name.trim().toLocaleLowerCase());
    if (names.some((name) => !name)) return t("admin.validationVariantName");
    if (new Set(names).size !== names.length) return t("admin.validationDuplicateVariantName");
    const globalColors = new Map();
    for (const group of form.variantGroups) {
      if (!group.colors.length) return t("admin.validationVariantColor");
      const colorNames = group.colors.map((color) => color.colorName.trim().toLocaleLowerCase());
      if (colorNames.some((name) => !name)) return t("admin.validationColorName");
      if (new Set(colorNames).size !== colorNames.length) return t("admin.validationDuplicateColor");
      for (const color of group.colors) {
        if (!validHex(color.colorValue)) return t("admin.validationColorValue");
        const quantity = Number(color.quantity);
        if (!Number.isInteger(quantity) || quantity < 0) return t("admin.validationColorQuantity");
        const key = color.colorName.trim().toLocaleLowerCase();
        const previousHex = globalColors.get(key);
        if (previousHex && previousHex !== color.colorValue.toUpperCase()) return t("admin.validationColorConsistency");
        globalColors.set(key, color.colorValue.toUpperCase());
      }
    }
    return "";
  };
  const validateMerchantForm = () => {
    if (!String(form.translations.en.name || "").trim()) return t("admin.validationProductName");
    return validateVariantInventory();
  };
  const appendMedia = (url) => setForm((current) => ({ ...current, images: [...(current.images || []), url].slice(0, 10) }));
  const uploadMedia = async (files) => {
    const target = "product";
    const current = form.images || [];
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
        appendMedia(url);
      }
      notifyCommerceAction({ type: "success", title: t("feedback.mediaUploaded"), message: t("feedback.mediaUploadedBody") });
    } catch {
      showUploadError(t("commerce:errors.uploadMedia"));
    } finally {
      setUploading("");
      setUploadProgress({ current: 0, total: 0 });
    }
  };

  const buildVariantInventoryPayload = () => {
    if (!form.variantGroups.length) return { options: [], variants: [] };
    const colorValues = [];
    const colorValueByName = new Map();
    for (const group of form.variantGroups) {
      for (const color of group.colors) {
        const key = color.colorName.trim().toLocaleLowerCase();
        if (!colorValueByName.has(key)) {
          const value = {
            id: color.valueId,
            code: code(`color-${colorValues.length + 1}-${color.colorName}`, `color-${colorValues.length + 1}`),
            value_translations: localized(color.colorName),
            color_hex: color.colorValue.toUpperCase(),
            sort_order: colorValues.length,
            active: true,
          };
          colorValues.push(value);
          colorValueByName.set(key, value);
        }
      }
    }
    const options = [
      {
        id: form.variantOptionId,
        code: "variant",
        name_translations: { en: "Variant" },
        required: true,
        display_type: "text",
        sort_order: 0,
        values: form.variantGroups.map((group, index) => ({
          id: group.id,
          code: code(`variant-${index + 1}-${group.name}`, `variant-${index + 1}`),
          value_translations: localized(group.name),
          color_hex: null,
          sort_order: index,
          active: true,
        })),
      },
      {
        id: form.colorOptionId,
        code: "color",
        name_translations: { en: "Color" },
        required: true,
        display_type: "color",
        sort_order: 1,
        values: colorValues,
      },
    ];
    const variants = form.variantGroups.flatMap((group, groupIndex) => group.colors.map((color, colorIndex) => {
      const selectedColor = colorValueByName.get(color.colorName.trim().toLocaleLowerCase());
      const generatedSku = `${form.sku || skuCode(form.translations.en.name, autoSkuSuffix)}-${groupIndex + 1}-${colorIndex + 1}-${color.id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
      return {
        id: color.id,
        sku: String(color.sku || generatedSku).trim().slice(0, 120),
        barcode: color.barcode || null,
        price_override: color.price_override === "" || color.price_override == null ? null : Number(color.price_override),
        compare_at_price_override: color.compare_at_price_override === "" || color.compare_at_price_override == null ? null : Number(color.compare_at_price_override),
        track_inventory: true,
        inventory_quantity: Number(color.quantity),
        low_stock_threshold: Number(color.low_stock_threshold || 0),
        allow_backorder: Boolean(color.allow_backorder),
        images: color.images || [],
        active: true,
        option_value_ids: [group.id, selectedColor.id],
      };
    }));
    return { options, variants };
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
      const inventory = buildVariantInventoryPayload();
      const productForm = { ...form };
      delete productForm.variantGroups;
      delete productForm.variantOptionId;
      delete productForm.colorOptionId;
      delete productForm.hadVariantInventory;
      delete productForm.options;
      delete productForm.variants;
      const payload = {
        ...productForm,
        slug: code(form.slug || form.translations.en.name, "product"),
        sku: String(form.sku || "").trim() || null,
        barcode: form.barcode || null,
        price: Number(form.price || 0), compare_at_price: form.compare_at_price === "" || form.compare_at_price == null ? null : Number(form.compare_at_price),
        inventory_quantity: Number(form.inventory_quantity || 0), low_stock_threshold: Number(form.low_stock_threshold || 0), currency: catalog.commerce_currency,
        attributes: form.attributes.map((item, index) => ({ ...item, sort_order: index, name_translations: localized(item.name_translations.en, item.name_translations.ar), value_translations: localized(item.value_translations.en, item.value_translations.ar) })),
        options: inventory.options,
        variants: inventory.variants,
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

  const saveVariants = async () => {
    if (!productId) return;
    const validationError = validateVariantInventory();
    if (validationError) {
      setState((current) => ({ ...current, saving: false, error: validationError }));
      notifyCommerceAction({ type: "error", title: t("admin.completeRequired"), message: validationError });
      return;
    }
    setState((current) => ({ ...current, saving: true, error: "" }));
    try {
      const inventory = buildVariantInventoryPayload();
      await saveEcommerceProductVariants(productId, inventory, { scope });
      notifyCommerceAction({ type: "success", title: t("admin.savedTitle", { item: t("merchant.variants") }), message: t("admin.changesSaved") });
    } catch {
      setState((current) => ({ ...current, error: t("commerce:errors.saveProduct") }));
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
<label>{t("merchant.productSku")}<input dir="ltr" disabled={Boolean(form.variantGroups.length)} value={form.sku || ""} onChange={(e) => { setSkuManuallyEdited(true); update("sku", e.target.value); }} />
{form.variantGroups.length > 0 && <small className="ecommerce-editor-field-help">{t("admin.skuMovedToVariants")}</small>}
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
      <section className="ecommerce-variant-inventory-editor">
        <header className="ecommerce-variant-editor-header">
          <div><h2>{t("merchant.variantsInventory")}</h2><p>{t("admin.variantCardsHelp")}</p></div>
        </header>
        <div className="ecommerce-variant-card-list">
          {form.variantGroups.map((group, groupIndex) => {
            const expanded = expandedVariants[group.id] !== false;
            const total = group.colors.reduce((sum, color) => sum + (Number.isInteger(Number(color.quantity)) && Number(color.quantity) >= 0 ? Number(color.quantity) : 0), 0);
            const label = group.name.trim() || t("admin.untitledVariant", { count: groupIndex + 1 });
            return <article className="ecommerce-variant-card" key={group.id}>
              <header className="ecommerce-variant-card-header">
                <button type="button" className="ecommerce-variant-card-toggle" aria-expanded={expanded} aria-controls={`variant-card-${group.id}`} onClick={() => setExpandedVariants((current) => ({ ...current, [group.id]: !expanded }))}>
                  <ChevronDown className={expanded ? "is-expanded" : ""} size={18} /><strong>{label}</strong><span>{t("admin.units", { count: total })}</span>
                </button>
                <button type="button" className="ecommerce-variant-card-delete" aria-label={t("admin.removeVariantLabel", { variant: label })} onClick={() => removeVariantGroup(group.id)}><Trash2 size={16} /></button>
              </header>
              {expanded && <div className="ecommerce-variant-card-body" id={`variant-card-${group.id}`}>
                <label className="ecommerce-variant-name-field"><span>{t("admin.variantName")}</span><input required name={`variant-name-${group.id}`} autoComplete="off" maxLength={200} value={group.name} placeholder={t("admin.variantNamePlaceholder")} onChange={(event) => changeVariantGroup(group.id, { name: event.target.value })} /></label>
                <div className="ecommerce-variant-colors-title"><strong>{t("admin.colors")}</strong></div>
                <div className="ecommerce-variant-color-head" aria-hidden="true"><span>{t("admin.colorName")}</span><span>{t("admin.colorValue")}</span><span>{t("admin.quantity")}</span><span /></div>
                <div className="ecommerce-variant-color-list">
                  {group.colors.map((color) => <div className="ecommerce-variant-color-row" key={color.id}>
                    <label><span>{t("admin.colorName")}</span><input required name={`color-name-${color.id}`} autoComplete="off" maxLength={200} value={color.colorName} placeholder={t("admin.colorNamePlaceholder")} onChange={(event) => changeVariantColor(group.id, color.id, { colorName: event.target.value })} /></label>
                    <label>
                      <span>{t("admin.colorValue")}</span>
                      <span className="ecommerce-variant-color-control">
                        <i className={`ecommerce-color-swatch${validHex(color.colorValue) ? "" : " ecommerce-color-swatch--empty"}`} style={{ backgroundColor: validHex(color.colorValue) ? color.colorValue : "transparent" }} aria-hidden="true" />
                        <input className="ecommerce-variant-native-color" type="color" value={validHex(color.colorValue) ? color.colorValue : "#000000"} aria-label={t("admin.colorPickerFor", { color: color.colorName || t("admin.unnamedColor") })} onInput={(event) => changeVariantColor(group.id, color.id, { colorValue: event.currentTarget.value.toUpperCase() })} onChange={(event) => changeVariantColor(group.id, color.id, { colorValue: event.target.value.toUpperCase() })} />
                        <input className="ecommerce-variant-hex-input" name={`color-hex-${color.id}`} autoComplete="off" spellCheck="false" dir="ltr" maxLength={7} placeholder="#111111" aria-label={t("admin.hexFor", { color: color.colorName || t("admin.unnamedColor") })} value={color.colorValue} onChange={(event) => {
                          const raw = event.target.value.trim().toUpperCase();
                          changeVariantColor(group.id, color.id, { colorValue: raw && !raw.startsWith("#") ? `#${raw}` : raw });
                        }} />
                      </span>
                    </label>
                    <label><span>{t("admin.quantity")}</span><input type="number" inputMode="numeric" min="0" step="1" aria-label={t("admin.colorQuantityFor", { color: color.colorName || t("admin.unnamedColor"), variant: label })} value={color.quantity} onChange={(event) => {
                      const raw = event.target.value;
                      const quantity = raw === "" ? "" : Math.max(0, Math.trunc(Number(raw) || 0));
                      changeVariantColor(group.id, color.id, { quantity });
                    }} /></label>
                    <button type="button" className="ecommerce-variant-color-delete" disabled={group.colors.length === 1} title={group.colors.length === 1 ? t("admin.keepOneColor") : t("admin.removeColor")} aria-label={t("admin.removeColor")} onClick={() => removeVariantColor(group.id, color.id)}><Trash2 size={16} /></button>
                  </div>)}
                </div>
                <footer className="ecommerce-variant-card-footer">
                  <button type="button" className="ecommerce-variant-add-color" onClick={() => addVariantColor(group.id)}><Plus size={16} />{t("merchant.addColor")}</button>
                  <strong>{t("admin.variantTotal", { count: total })}</strong>
                </footer>
              </div>}
            </article>;
          })}
        </div>
        <div className="ecommerce-variant-editor-actions">
          <button type="button" className="ecommerce-add-variant-button" onClick={addVariantGroup}><Plus size={16} />{t("merchant.addVariant")}</button>
          {productId && variantInventoryIsFilled(form.variantGroups) && <button type="button" className="ecommerce-save-variants-button" disabled={state.saving} onClick={saveVariants}><Save size={16} />{state.saving ? t("merchant.saving") : t("merchant.saveVariants")}</button>}
        </div>
      </section>
      {!form.variantGroups.length && !form.hadVariantInventory && <section className="ecommerce-editor-inventory">
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
