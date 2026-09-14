import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, Plus, Save, Trash2, Upload } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { DASHBOARD_ROUTES } from "../../config/routes";
import { fetchEcommerceCatalog, saveEcommerceItem, uploadEcommerceProductImage } from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";
import { commerceInventoryState } from "../../utils/commerceStock";

const uuid = () => globalThis.crypto?.randomUUID?.() || `00000000-0000-4000-8000-${Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12)}`;
const code = (value, fallback) => String(value || fallback).trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || fallback;
const localized = (en = "", ar = "") => ({ en: String(en).trim(), ...(String(ar).trim() ? { ar: String(ar).trim() } : {}) });
const emptyProduct = (currency = "USD") => ({
  slug: "", sku: "", barcode: null, category_id: null, tag_ids: [], product_type: "physical", brand: "",
  translations: { en: { name: "", description: "" }, ar: { name: "", description: "" } }, status: "draft",
  price: 0, compare_at_price: null, cost_price: null, currency, track_inventory: true, inventory_quantity: 0,
  low_stock_threshold: 5, allow_backorder: false, images: [], weight: null, weight_unit: "kg",
  requires_shipping: true, taxable: true, seo_title: "", seo_description: "", attributes: [], options: [], variants: [],
});

export default function EcommerceProductEditorPage({ user }) {
  const { productId } = useParams();
  const { t, locale, direction, localize } = useCommerceI18n();
  const navigate = useNavigate();
  const scope = user?.id ? `user-${user.id}` : "authenticated";
  const [catalog, setCatalog] = useState({ products: [], categories: [], tags: [], commerce_currency: "USD" });
  const [form, setForm] = useState(emptyProduct());
  const [state, setState] = useState({ loading: true, saving: false, error: "" });
  const [uploading, setUploading] = useState("");
  const editing = Boolean(productId);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceCatalog({ scope, force: true }).then((result) => {
      if (cancelled) return;
      const product = result.products?.find((item) => item.id === productId);
      if (editing && !product) throw new Error(t("commerce:errors.productNotFound"));
      setCatalog(result);
      setForm(product ? { ...emptyProduct(result.commerce_currency), ...product, attributes: product.attributes || [], options: product.options || [], variants: product.variants || [] } : emptyProduct(result.commerce_currency));
      setState({ loading: false, saving: false, error: "" });
    }).catch((error) => !cancelled && setState({ loading: false, saving: false, error: error.message || t("commerce:errors.loadProduct") }));
    return () => { cancelled = true; };
  }, [editing, productId, scope, t]);

  const valueById = useMemo(() => new Map(form.options.flatMap((option) => option.values || []).map((value) => [value.id, value])), [form.options]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const updateTranslation = (locale, field, value) => setForm((current) => ({ ...current, translations: { ...current.translations, [locale]: { ...current.translations[locale], [field]: value } } }));
  const addAttribute = () => update("attributes", [...form.attributes, { id: uuid(), name_translations: { en: "" }, value_translations: { en: "" }, sort_order: form.attributes.length }]);
  const changeAttribute = (id, field, value) => update("attributes", form.attributes.map((item) => item.id === id ? { ...item, [field]: value } : item));
  const addOption = () => update("options", [...form.options, { id: uuid(), code: `option-${form.options.length + 1}`, name_translations: { en: "" }, required: true, sort_order: form.options.length, values: [] }]);
  const changeOption = (id, change) => update("options", form.options.map((item) => item.id === id ? { ...item, ...change } : item));
  const addValue = (option) => changeOption(option.id, { values: [...option.values, { id: uuid(), code: `value-${option.values.length + 1}`, value_translations: { en: "" }, sort_order: option.values.length, active: true }] });
  const changeValue = (option, valueId, change) => changeOption(option.id, { values: option.values.map((value) => value.id === valueId ? { ...value, ...change } : value) });
  const addVariant = () => update("variants", [...form.variants, { id: uuid(), sku: "", barcode: null, price_override: null, compare_at_price_override: null, track_inventory: true, inventory_quantity: 0, low_stock_threshold: 5, allow_backorder: false, images: [], active: true, option_value_ids: form.options.map(() => "") }]);
  const changeVariant = (id, change) => update("variants", form.variants.map((item) => item.id === id ? { ...item, ...change } : item));
  const move = (items, index, delta) => {
    const target = index + delta;
    if (target < 0 || target >= items.length) return items;
    const reordered = [...items];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    return reordered;
  };
  const uploadImages = async (files, variantId = null) => {
    const current = variantId ? form.variants.find((item) => item.id === variantId)?.images || [] : form.images || [];
    const selected = Array.from(files || []);
    if (!selected.length) return;
    if (selected.length > 4 - current.length) return setState((value) => ({ ...value, error: t("commerce:errors.variantImageLimit") }));
    if (selected.some((file) => !["image/png", "image/jpeg", "image/webp"].includes(file.type))) return setState((value) => ({ ...value, error: t("commerce:errors.invalidImageType") }));
    setUploading(variantId || "product");
    setState((value) => ({ ...value, error: "" }));
    try {
      const urls = [];
      for (const file of selected) urls.push(await uploadEcommerceProductImage(file));
      if (variantId) changeVariant(variantId, { images: [...current, ...urls].slice(0, 4) });
      else update("images", [...current, ...urls].slice(0, 4));
    } catch (error) {
      setState((value) => ({ ...value, error: error.message || t("commerce:errors.uploadImage") }));
    } finally {
      setUploading("");
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setState((current) => ({ ...current, saving: true, error: "" }));
    try {
      const payload = {
        ...form,
        slug: code(form.slug || form.translations.en.name, "product"),
        sku: form.sku.trim() || null,
        barcode: form.barcode || null,
        price: Number(form.price || 0), compare_at_price: form.compare_at_price === "" || form.compare_at_price == null ? null : Number(form.compare_at_price),
        inventory_quantity: Number(form.inventory_quantity || 0), low_stock_threshold: Number(form.low_stock_threshold || 0), currency: catalog.commerce_currency,
        attributes: form.attributes.map((item, index) => ({ ...item, sort_order: index, name_translations: localized(item.name_translations.en, item.name_translations.ar), value_translations: localized(item.value_translations.en, item.value_translations.ar) })),
        options: form.options.map((option, index) => ({ ...option, code: code(option.code || option.name_translations.en, `option-${index + 1}`), sort_order: index, name_translations: localized(option.name_translations.en, option.name_translations.ar), values: option.values.map((value, valueIndex) => ({ ...value, code: code(value.code || value.value_translations.en, `value-${valueIndex + 1}`), sort_order: valueIndex, value_translations: localized(value.value_translations.en, value.value_translations.ar) })) })),
        variants: form.variants.map((variant) => ({ ...variant, sku: variant.sku.trim(), barcode: variant.barcode || null, price_override: variant.price_override === "" || variant.price_override == null ? null : Number(variant.price_override), compare_at_price_override: variant.compare_at_price_override === "" || variant.compare_at_price_override == null ? null : Number(variant.compare_at_price_override), inventory_quantity: Number(variant.inventory_quantity || 0), low_stock_threshold: Number(variant.low_stock_threshold || 0), option_value_ids: variant.option_value_ids.filter(Boolean) })),
      };
      await saveEcommerceItem("products", productId, payload, { scope });
      navigate(DASHBOARD_ROUTES.ecommerceProducts);
    } catch (error) {
      setState((current) => ({ ...current, saving: false, error: error.message || t("commerce:errors.saveProduct") }));
    }
  };

  if (state.loading) return <section className="ecommerce-product-editor" dir={direction}>
<p>{t("merchant.loadingProduct")}</p>
</section>;
  return (
    <form className="ecommerce-product-editor" onSubmit={submit} dir={direction} lang={locale}>
      <header>
<div>
<Link to={DASHBOARD_ROUTES.ecommerceProducts}>
<ArrowLeft size={16} />{t("common.products")}</Link>
<h1>{editing ? t("merchant.editProduct") : t("merchant.newProduct")}</h1>
</div>
<button className="ecommerce-primary-button" disabled={state.saving}>
<Save size={17} />{state.saving ? t("merchant.saving") : t("merchant.saveProduct")}</button>
</header>
      {state.error && <p className="ecommerce-editor-error" role="alert">{state.error}</p>}
      <section>
<h2>{t("merchant.basic")}</h2>
<div className="ecommerce-editor-grid">
<label>{t("merchant.nameEnglish")}<input required maxLength={200} dir="ltr" value={form.translations.en.name} onChange={(e) => updateTranslation("en", "name", e.target.value)} />
</label>
<label>{t("merchant.nameArabic")}<input maxLength={200} dir="rtl" value={form.translations.ar?.name || ""} onChange={(e) => updateTranslation("ar", "name", e.target.value)} />
</label>
<label>{t("merchant.slug")}<input dir="ltr" value={form.slug} onChange={(e) => update("slug", e.target.value)} />
</label>
<label>{t("merchant.productSku")}<input dir="ltr" value={form.sku || ""} onChange={(e) => update("sku", e.target.value)} />
</label>
<label>{t("merchant.brand")}<input value={form.brand} onChange={(e) => update("brand", e.target.value)} />
</label>
<label>{t("common.status")}<select value={form.status} onChange={(e) => update("status", e.target.value)}>
<option value="draft">{t("common.draft")}</option>
<option value="active">{t("common.active")}</option>
<option value="inactive">{t("common.inactive")}</option>
<option value="archived">{t("common.archived")}</option>
</select>
</label>
<label className="is-wide">{t("merchant.descriptionEnglish")}<textarea rows={4} dir="ltr" value={form.translations.en.description} onChange={(e) => updateTranslation("en", "description", e.target.value)} />
</label>
<label className="is-wide">{t("merchant.descriptionArabic")}<textarea rows={4} dir="rtl" value={form.translations.ar?.description || ""} onChange={(e) => updateTranslation("ar", "description", e.target.value)} />
</label>
</div>
</section>
      <section>
<h2>{t("merchant.pricing")}</h2>
<div className="ecommerce-editor-grid">
<label>{t("merchant.basePrice")}<input type="number" min="0" step="0.01" required value={form.price} onChange={(e) => update("price", e.target.value)} />
</label>
<label>{t("merchant.comparePrice")}<input type="number" min="0" step="0.01" value={form.compare_at_price ?? ""} onChange={(e) => update("compare_at_price", e.target.value)} />
</label>
<label>{t("merchant.storeCurrency")}<input readOnly dir="ltr" value={catalog.commerce_currency || form.currency} />
</label>
</div>
</section>
      <section>
<h2>{t("merchant.organizationMedia")}</h2>
<div className="ecommerce-editor-grid">
<label>{t("merchant.category")}<select value={form.category_id || ""} onChange={(e) => update("category_id", e.target.value || null)}>
<option value="">{t("merchant.noCategory")}</option>{catalog.categories.map((item) => <option value={item.id} key={item.id}>{localize(item.translations) || item.name || item.slug}</option>)}</select>
</label>
<fieldset className="is-wide">
<legend>{t("common.tags")}</legend>
<div className="ecommerce-editor-checks">{catalog.tags.map((item) => <label key={item.id}>
<input type="checkbox" checked={form.tag_ids.includes(item.id)} onChange={() => update("tag_ids", form.tag_ids.includes(item.id) ? form.tag_ids.filter((id) => id !== item.id) : [...form.tag_ids, item.id])} />{localize(item.translations) || item.name || item.slug}</label>)}</div>
</fieldset>
</div>
<div className="ecommerce-editor-images">{form.images.map((url, index) => <div key={url}>
<img src={url} alt={t("admin.productImage", { count: index + 1 })} />
<button type="button" aria-label={`Remove product image ${index + 1}`} onClick={() => update("images", form.images.filter((item) => item !== url))}>
<Trash2 size={15} />
</button>
</div>)}</div>
<label className="ecommerce-editor-upload">
<Upload size={16} />{uploading === "product" ? t("merchant.uploading") : t("merchant.addImages")}<input type="file" aria-label={t("merchant.addImages")} accept="image/png,image/jpeg,image/webp" multiple disabled={Boolean(uploading) || form.images.length >= 4} onChange={(event) => { void uploadImages(event.target.files); event.target.value = ""; }} />
</label>
</section>
      <section>
<h2>{t("merchant.attributes")}</h2>
<p>{t("admin.attributesHelp")}</p>{form.attributes.map((item) => <div className="ecommerce-editor-row" key={item.id}>
<input aria-label={t("admin.attributeNameEnglish")} placeholder={t("merchant.nameEnglish")} dir="ltr" value={item.name_translations.en || ""} onChange={(e) => changeAttribute(item.id, "name_translations", { ...item.name_translations, en: e.target.value })} />
<input aria-label={t("admin.attributeValueEnglish")} placeholder={t("merchant.valueEnglish")} dir="ltr" value={item.value_translations.en || ""} onChange={(e) => changeAttribute(item.id, "value_translations", { ...item.value_translations, en: e.target.value })} />
<input aria-label={t("admin.attributeNameArabic")} placeholder={t("merchant.nameArabic")} dir="rtl" value={item.name_translations.ar || ""} onChange={(e) => changeAttribute(item.id, "name_translations", { ...item.name_translations, ar: e.target.value })} />
<input aria-label={t("admin.attributeValueArabic")} placeholder={t("merchant.valueArabic")} dir="rtl" value={item.value_translations.ar || ""} onChange={(e) => changeAttribute(item.id, "value_translations", { ...item.value_translations, ar: e.target.value })} />
<button type="button" onClick={() => update("attributes", form.attributes.filter((entry) => entry.id !== item.id))}>
<Trash2 size={16} />
</button>
</div>)}<button type="button" onClick={addAttribute}>
<Plus size={16} />{t("merchant.addAttribute")}</button>
</section>
      <section>
<h2>{t("merchant.options")}</h2>
<p>{t("admin.optionsHelp")}</p>{form.options.map((option) => <article className="ecommerce-editor-option" key={option.id}>
<div className="ecommerce-editor-row">
<input required placeholder={t("merchant.optionNameEnglish")} dir="ltr" value={option.name_translations.en || ""} onChange={(e) => changeOption(option.id, { name_translations: { ...option.name_translations, en: e.target.value } })} />
<input placeholder={t("merchant.optionNameArabic")} dir="rtl" value={option.name_translations.ar || ""} onChange={(e) => changeOption(option.id, { name_translations: { ...option.name_translations, ar: e.target.value } })} />
<label>
<input type="checkbox" checked={option.required} onChange={(e) => changeOption(option.id, { required: e.target.checked })} />{t("merchant.required")}</label>
<button type="button" onClick={() => update("options", form.options.filter((entry) => entry.id !== option.id))}>
<Trash2 size={16} />
</button>
</div>{option.values.map((value) => <div className="ecommerce-editor-row is-value" key={value.id}>
<input required placeholder={t("merchant.valueEnglish")} dir="ltr" value={value.value_translations.en || ""} onChange={(e) => changeValue(option, value.id, { value_translations: { ...value.value_translations, en: e.target.value } })} />
<input placeholder={t("merchant.valueArabic")} dir="rtl" value={value.value_translations.ar || ""} onChange={(e) => changeValue(option, value.id, { value_translations: { ...value.value_translations, ar: e.target.value } })} />
<button type="button" onClick={() => changeOption(option.id, { values: option.values.filter((entry) => entry.id !== value.id) })}>
<Trash2 size={16} />
</button>
</div>)}<button type="button" onClick={() => addValue(option)}>
<Plus size={16} />{t("merchant.addValue")}</button>
</article>)}<button type="button" disabled={form.options.length >= 5} onClick={addOption}>
<Plus size={16} />{t("merchant.addOption")}</button>
</section>
      {(form.attributes.length > 1 || form.options.some((option) => option.values.length > 1) || form.options.length > 1) && <section>
<h2>{t("merchant.displayOrder")}</h2>
<p>{t("admin.displayOrderDescription")}</p>{form.attributes.map((item, index) => <div className="ecommerce-editor-order" key={item.id}>
<span>{t("merchant.attributes")}: {localize(item, "name") || index + 1}</span>
<button type="button" aria-label={t("admin.moveAttributeUp")} disabled={!index} onClick={() => update("attributes", move(form.attributes, index, -1))}>
<ArrowUp size={15} />
</button>
<button type="button" aria-label={t("admin.moveAttributeDown")} disabled={index === form.attributes.length - 1} onClick={() => update("attributes", move(form.attributes, index, 1))}>
<ArrowDown size={15} />
</button>
</div>)}{form.options.map((option, index) => <div key={option.id}>
<div className="ecommerce-editor-order">
<span>{t("merchant.options")}: {localize(option, "name") || index + 1}</span>
<button type="button" aria-label={t("admin.moveOptionUp")} disabled={!index} onClick={() => update("options", move(form.options, index, -1))}>
<ArrowUp size={15} />
</button>
<button type="button" aria-label={t("admin.moveOptionDown")} disabled={index === form.options.length - 1} onClick={() => update("options", move(form.options, index, 1))}>
<ArrowDown size={15} />
</button>
</div>{option.values.map((value, valueIndex) => <div className="ecommerce-editor-order is-value" key={value.id}>
<span>{t("admin.value")}: {localize(value, "value") || valueIndex + 1}</span>
<button type="button" aria-label={t("admin.moveValueUp")} disabled={!valueIndex} onClick={() => changeOption(option.id, { values: move(option.values, valueIndex, -1) })}>
<ArrowUp size={15} />
</button>
<button type="button" aria-label={t("admin.moveValueDown")} disabled={valueIndex === option.values.length - 1} onClick={() => changeOption(option.id, { values: move(option.values, valueIndex, 1) })}>
<ArrowDown size={15} />
</button>
</div>)}</div>)}</section>}
      <section>
<h2>{t("merchant.variants")}</h2>
<p>{t("admin.variantsHelp")}</p>{form.variants.map((variant) => <article className="ecommerce-editor-variant" key={variant.id}>
<div className="ecommerce-editor-grid">{form.options.map((option, optionIndex) => <label key={option.id}>{localize(option, "name") || `${t("merchant.options")} ${optionIndex + 1}`}<select required={option.required} value={variant.option_value_ids[optionIndex] || ""} onChange={(e) => { const ids = [...variant.option_value_ids]; ids[optionIndex] = e.target.value; changeVariant(variant.id, { option_value_ids: ids }); }}>
<option value="">{t("admin.chooseValue")}</option>{option.values.map((value) => <option value={value.id} key={value.id}>{localize(value, "value") || value.code}</option>)}</select>
</label>)}<label>{t("merchant.variantSku")}<input dir="ltr" required value={variant.sku} onChange={(e) => changeVariant(variant.id, { sku: e.target.value })} />
</label>
<label>{t("common.barcode")}<input dir="ltr" value={variant.barcode || ""} onChange={(e) => changeVariant(variant.id, { barcode: e.target.value })} />
</label>
<label>{t("merchant.priceOverride")}<input type="number" min="0" step="0.01" placeholder={t("merchant.inheritBase")} value={variant.price_override ?? ""} onChange={(e) => changeVariant(variant.id, { price_override: e.target.value })} />
</label>
<label>{t("merchant.inventory")}<input type="number" min="0" value={variant.inventory_quantity} onChange={(e) => changeVariant(variant.id, { inventory_quantity: e.target.value })} />
</label>
<label>
<input type="checkbox" checked={variant.allow_backorder} onChange={(e) => changeVariant(variant.id, { allow_backorder: e.target.checked })} />{t("merchant.allowBackorder")}</label>
<label>
<input type="checkbox" checked={variant.active} onChange={(e) => changeVariant(variant.id, { active: e.target.checked })} />{t("common.active")}</label>
</div>
<p>{variant.option_value_ids.filter(Boolean).map((id) => localize(valueById.get(id), "value")).filter(Boolean).join(" / ") || t("admin.incompleteCombination")}</p>
<button type="button" onClick={() => update("variants", form.variants.filter((entry) => entry.id !== variant.id))}>
<Trash2 size={16} />{t("merchant.removeVariant")}</button>
</article>)}<button type="button" disabled={!form.options.length} onClick={addVariant}>
<Plus size={16} />{t("merchant.addVariant")}</button>
</section>
      {form.variants.length > 0 && <section>
<h2>{t("merchant.variantMedia")}</h2>
<p>{t("admin.variantMediaHelp")}</p>{form.variants.map((variant, variantIndex) => <article className="ecommerce-editor-variant-media" key={variant.id}>
<strong><bdi>{variant.sku || `${t("merchant.variants")} ${variantIndex + 1}`}</bdi></strong>
<div className="ecommerce-editor-images">{variant.images.map((url, index) => <div key={url}>
<img src={url} alt={t("admin.variantImage", { variant: variantIndex + 1, image: index + 1 })} />
<button type="button" aria-label={`Remove image from variant ${variantIndex + 1}`} onClick={() => changeVariant(variant.id, { images: variant.images.filter((item) => item !== url) })}>
<Trash2 size={15} />
</button>
</div>)}</div>
<label className="ecommerce-editor-upload">
<Upload size={16} />{uploading === variant.id ? t("merchant.uploading") : t("merchant.addImages")}<input type="file" aria-label={t("merchant.addImages")} accept="image/png,image/jpeg,image/webp" multiple disabled={Boolean(uploading) || variant.images.length >= 4} onChange={(event) => { void uploadImages(event.target.files, variant.id); event.target.value = ""; }} />
</label>
</article>)}</section>}
      {form.variants.length > 0 && <section>
<h2>{t("merchant.variantDetails")}</h2>{form.variants.map((variant, index) => <article className="ecommerce-editor-variant-media" key={variant.id}>
<strong><bdi>{variant.sku || `${t("merchant.variants")} ${index + 1}`}</bdi></strong>
<div className="ecommerce-editor-grid">
<label>{t("merchant.compareOverride")}<input type="number" min="0" step="0.01" placeholder={t("merchant.inheritBase")} value={variant.compare_at_price_override ?? ""} onChange={(e) => changeVariant(variant.id, { compare_at_price_override: e.target.value })} />
</label>
<label>{t("merchant.lowThreshold")}<input type="number" min="0" value={variant.low_stock_threshold} onChange={(e) => changeVariant(variant.id, { low_stock_threshold: e.target.value })} />
</label>
<label>
<input type="checkbox" checked={variant.track_inventory} onChange={(e) => changeVariant(variant.id, { track_inventory: e.target.checked })} />{t("merchant.trackInventory")}</label>
</div>
</article>)}</section>}
      <section>
<h2>{t("merchant.inventory")}</h2>{form.options.length ? <p>{t("merchant.variantInventoryHelp")}</p> : <div className="ecommerce-editor-grid">
<label>{t("merchant.currentStock")}<input type="number" min="0" value={form.inventory_quantity} onChange={(e) => update("inventory_quantity", e.target.value)} />
</label>
<label>{t("merchant.lowThreshold")}<input type="number" min="0" value={form.low_stock_threshold} onChange={(e) => update("low_stock_threshold", e.target.value)} />
</label>
<label>
<input type="checkbox" checked={form.allow_backorder} onChange={(e) => update("allow_backorder", e.target.checked)} />{t("merchant.allowBackorder")}</label>
</div>}</section>
      {form.variants.length > 0 && <section className="ecommerce-editor-stock">
<h2>{t("merchant.inventory")}</h2>{form.variants.map((variant, index) => { const stock = commerceInventoryState(variant); return <p key={variant.id}>
<bdi>{variant.sku || `${t("merchant.variants")} ${index + 1}`}</bdi>
<span className={`ecommerce-stock-chip is-${stock}`}>{t(`stock.${stock}`)}</span>
</p>; })}</section>}
      <footer>
<Link to={DASHBOARD_ROUTES.ecommerceProducts}>{t("common.cancel")}</Link>
<button className="ecommerce-primary-button" disabled={state.saving}>
<Save size={17} />{t("merchant.saveProduct")}</button>
</footer>
    </form>
  );
}
