const uuid = () => globalThis.crypto.randomUUID();
const validHex = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ""));
const localized = (en = "") => ({ en: String(en).trim() });
const skuCode = (value, suffix) => `${String(value || "product").replace(/[^a-z0-9]+/gi, "-").slice(0, 70)}-${suffix}`;
export const stableOrder = (a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0) || String(a.id).localeCompare(String(b.id));
const semanticLabel = (labels) => labels?.en || labels?.ar || (labels ? labels[Object.keys(labels).sort()[0]] : "");
const stableCode = (prefix, id) => `${prefix}-${id.replace(/-/g, "")}`;

export const hydrateVariantGroups = (product) => {
  const options = [...(product?.options || [])].filter((option) => option.active !== false).sort(stableOrder);
  const variants = [...(product?.variants || [])].filter((variant) => variant.active !== false).sort(stableOrder);
  const colorOption = options.find((option) => String(option.code || "").toLowerCase() === "color")
    || options.find((option) => String(option.name_translations?.en || "").trim().toLowerCase() === "color")
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
    const fallbackName = selected.filter((value) => value.id !== colorValue?.id).map((value) => semanticLabel(value.value_translations) || value.code).join(" / ");
    const groupId = variantValue?.id || variant.id;
    let group = groupById.get(groupId);
    if (!group) {
      group = { id: groupId, code: variantValue?.code, color_hex: variantValue?.color_hex, translations: variantValue?.value_translations, sort_order: variantValue?.sort_order || 0, name: semanticLabel(variantValue?.value_translations) || fallbackName || "", colors: [] };
      groups.push(group);
      groupById.set(groupId, group);
    }
    group.colors.push({
      ...variant,
      valueId: colorValue?.id || variant.id,
      valueCode: colorValue?.code, valueTranslations: colorValue?.value_translations, sort_order: colorValue?.sort_order || 0,
      colorName: semanticLabel(colorValue?.value_translations) || "",
      colorValue: colorValue?.color_hex || "",
      quantity: Number(variant.inventory_quantity || 0),
    });
  }

  return {
    ...(variants.length ? {track_inventory:variants.some(v=>v.track_inventory!==false),low_stock_threshold:Number(variants[0].low_stock_threshold ?? product?.low_stock_threshold ?? 5),allow_backorder:variants.some(v=>Boolean(v.allow_backorder))} : {}),
    inventorySettingsBaseline: variants.length ? {track_inventory:variants.some(v=>v.track_inventory!==false),low_stock_threshold:Number(variants[0].low_stock_threshold ?? product?.low_stock_threshold ?? 5),allow_backorder:variants.some(v=>Boolean(v.allow_backorder))} : null,
    inventoryBaseline: inventoryFingerprint(product?.inventory_quantity, variants),
    nativeVariantInventory: options.length > 0 && !(options.length === 2 && colorOption && variantOption),
    variantOptionId: variantOption?.id || (options.length ? null : uuid()),
    colorOptionId: colorOption?.id || (options.length ? null : uuid()),
    variantOption: variantOption ? { ...variantOption, values: [] } : null,
    colorOption: colorOption ? { ...colorOption, values: [] } : null,
    variantGroups: groups.sort(stableOrder).map((group) => ({ ...group, colors: group.colors.sort((a, b) => stableOrder({ ...a, id: a.valueId }, { ...b, id: b.valueId }) || String(a.id).localeCompare(String(b.id))) })),
    hadVariantInventory: Boolean(options.length || variants.length),
  };
};

const buildInventory = (form, autoSkuSuffix) => {
    // Preserve imported/custom option topologies rather than flattening dimensions.
    if (form.nativeVariantInventory) return {
      options: (form.options || []).filter((option) => option.active !== false).sort(stableOrder).map((option) => ({ ...option, values: option.values.filter((value) => value.active !== false).sort(stableOrder) })),
      variants: (form.variants || []).filter((variant) => variant.active !== false).sort(stableOrder),
      expected_catalog_version: form.catalog_version || null,
    };
    if (!form.variantGroups.length) return { options: [], variants: [], expected_catalog_version: form.catalog_version || null };
    const colorValues = [];
    const colorValueByName = new Map();
    const persistedColorByName = new Map();
    const persistedColorFieldsByName = new Map();
    for (const color of form.variantGroups.flatMap(group => group.colors)) {
      if (!color.valueCode) continue;
      const key=color.colorName.trim().toLowerCase();
      const previous=persistedColorByName.get(key);
      if (previous && previous !== color.valueId) {
        const error=new Error("Duplicate color value");error.code="OPTION_VALUE_CONFLICT";throw error;
      }
      persistedColorByName.set(key,color.valueId);persistedColorFieldsByName.set(key,color);
    }
    for (const group of form.variantGroups) {
      for (const color of group.colors) {
        const key = color.colorName.trim().toLowerCase();
        if (color.valueCode) {
          const previous = persistedColorByName.get(key);
          if (previous && previous !== color.valueId) {
            const error = new Error("Duplicate color value");
            error.code = "OPTION_VALUE_CONFLICT";
            throw error;
          }
          persistedColorByName.set(key, color.valueId);
        }
        if (!colorValueByName.has(key)) {
          const canonical=persistedColorFieldsByName.get(key) || color;
          const value = {
            id: canonical.valueId,
            code: canonical.valueCode || stableCode("color", canonical.valueId),
            value_translations: { ...canonical.valueTranslations, ...localized(color.colorName) },
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
        ...form.variantOption,
        id: form.variantOptionId,
        code: form.variantOption?.code || "size",
        name_translations: form.variantOption?.name_translations || { en: "Size", ar: "المقاس" },
        required: form.variantOption?.required ?? true,
        display_type: form.variantOption?.display_type || "text",
        sort_order: form.variantOption?.sort_order ?? 0,
        values: form.variantGroups.map((group, index) => ({
          id: group.id,
          code: group.code || stableCode("value", group.id),
          value_translations: { ...group.translations, ...localized(group.name) },
          color_hex: form.variantOption?.display_type === "color" ? group.color_hex : null,
          sort_order: index,
          active: true,
        })),
      },
      {
        ...form.colorOption,
        id: form.colorOptionId,
        code: form.colorOption?.code || "color",
        name_translations: form.colorOption?.name_translations || { en: "Color" },
        required: form.colorOption?.required ?? true,
        display_type: "color",
        sort_order: form.colorOption?.sort_order ?? 1,
        values: colorValues,
      },
    ];
    const variants = form.variantGroups.flatMap((group) => group.colors.map((color) => {
      const selectedColor = colorValueByName.get(color.colorName.trim().toLowerCase());
      const generatedSku = `${String(form.sku || skuCode(form.translations.en.name, autoSkuSuffix)).slice(0, 87)}-${color.id.replace(/-/g, "").toUpperCase()}`;
      return {
        id: color.id,
        sku: String(color.sku || generatedSku).trim().slice(0, 120),
        barcode: color.barcode || null,
        price_override: color.price_override === "" || color.price_override == null ? null : Number(color.price_override),
        compare_at_price_override: color.compare_at_price_override === "" || color.compare_at_price_override == null ? null : Number(color.compare_at_price_override),
        track_inventory: color.track_inventory ?? true,
        inventory_quantity: Number(color.quantity),
        low_stock_threshold: Number(color.low_stock_threshold || 0),
        allow_backorder: Boolean(color.allow_backorder),
        images: color.images || [],
        active: true,
        option_value_ids: [group.id, selectedColor.id],
      };
    }));
    return { options, variants, expected_catalog_version: form.catalog_version || null };
  };


export const combinedSizeNames = (name) => {
 const text=String(name || "").trim();
 if (/^\d+(?:\s*-\s*\d+)+$/.test(text)) return [...new Set(text.split(/\s*-\s*/))];
 if (/[/,+&]|\s+(?:or|او)\s+/i.test(text)) return [...new Set(text.split(/\s*(?:[/,+&]|\s+(?:or|او)\s+)\s*/i).filter(Boolean))];
 return [];
};

const derivedId = async (seed) => {
  const digest = new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(`madar-size-split-v1:${seed}`)));
  digest[6] = (digest[6] & 15) | 128; digest[8] = (digest[8] & 63) | 128;
  const hex = [...digest.slice(0, 16)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};

// Explicit conversion conserves each source variant's total stock. Hydration
// never migrates data. Canonical DB remapping also handles unseen archived rows.
export const splitLegacySizeGroup = async (form, groupId) => {
  const source = form.variantGroups.find((g) => g.id === groupId);
  const names = combinedSizeNames(source?.name);
  if (names.length < 2) return form.variantGroups;
  const option = (form.options || []).find((o) => o.id === form.variantOptionId);
  const groups = await Promise.all(names.map(async (name, index) => {
    const present = form.variantGroups.find((g) => g.name.trim().toLowerCase() === name);
    // An already visible size requires an explicit merchant merge, not guessing stock.
    if (present) throw new Error("LEGACY_SIZE_MERGE_REQUIRED");
    const oldValue = (option?.values || []).find((v) => String(v.value_translations?.en || "").trim() === name);
    const id = oldValue?.id || await derivedId(`${source.id}:value:${name}`);
    const colors = await Promise.all(source.colors.map(async (color) => {
      const oldVariant = (form.variants || []).find((v) => v.option_value_ids?.includes(id) && v.option_value_ids?.includes(color.valueId));
      return { ...color, ...(oldVariant || {}), id: oldVariant?.id || await derivedId(`${color.id}:variant:${name}`),
        sku: oldVariant?.sku || "", quantity: Math.floor(Number(color.quantity) / names.length) + (index < Number(color.quantity) % names.length ? 1 : 0) };
    }));
    return { id, code: oldValue?.code, color_hex: oldValue?.color_hex || source.color_hex, translations: oldValue?.value_translations, name, colors };
  }));
  return form.variantGroups.flatMap((g) => g.id === groupId ? groups : [g]);
};

export const catalogSaveErrorMessage = (error, t) => {
  const codes = ["PRODUCT_SKU_CONFLICT", "PRODUCT_SLUG_CONFLICT", "VARIANT_SKU_CONFLICT", "CATALOG_SKU_CONFLICT", "OPTION_CODE_CONFLICT", "OPTION_NAME_CONFLICT", "OPTION_VALUE_CODE_CONFLICT", "OPTION_VALUE_CONFLICT", "VARIANT_COMBINATION_CONFLICT", "CATALOG_CHANGED_CONFLICT", "CATALOG_UNIQUE_CONFLICT"];
  const code = codes.includes(error?.code) ? error.code : error?.status === 409 ? "CATALOG_UNIQUE_CONFLICT" : null;
  const message = code ? t(`commerce:errors.${code}`) : t("commerce:errors.saveProduct");
  return error?.context?.reference_id ? `${message} ${t("commerce:errors.reference", { id: error.context.reference_id })}` : message;
};


export const editVariantColor = (groups, groupId, colorId, change) => {
  const source = groups.find((g) => g.id === groupId)?.colors.find((c) => c.id === colorId);
  const shared = Object.fromEntries(Object.entries(change).filter(([key]) => ["colorName", "colorValue"].includes(key)));
  return groups.map((group) => ({ ...group, colors: group.colors.map((color) =>
    color.id === colorId ? { ...color, ...change } : source?.valueId && color.valueId === source.valueId ? { ...color, ...shared } : color) }));
};

export const splitLegacyOptionValue = async (form, optionId, valueId) => {
  const option = form.options.find((item) => item.id === optionId);
  const source = option?.values.find((value) => value.id === valueId);
  const names = combinedSizeNames(source?.value_translations?.en);
  const affected = form.variants.filter((variant) => variant.active !== false && variant.option_value_ids.includes(valueId));
  if (names.length < 2 || !affected.length) return { options: form.options, variants: form.variants };
  const values = await Promise.all(names.map(async (name, index) => {
    const previous = option.values.find((value) => value.value_translations?.en?.trim() === name);
    const id = previous?.id || await derivedId(`${valueId}:value:${name}`);
    return { ...previous, id, code: previous?.code || stableCode("value", id), value_translations: { ...previous?.value_translations, en: name },
      color_hex: option.display_type === "color" ? previous?.color_hex || source.color_hex : null, sort_order: index, active: true };
  }));
  const variants = new Map(form.variants.map((variant) => [variant.id, variant]));
  for (const variant of affected) {
    variants.set(variant.id, { ...variant, active: false });
    for (const [index, value] of values.entries()) {
      const selected = variant.option_value_ids.map((id) => id === valueId ? value.id : id).sort();
      const previous = form.variants.find((item) => [...item.option_value_ids].sort().join(",") === selected.join(","));
      if (previous?.active !== false && previous) throw new Error("LEGACY_SIZE_MERGE_REQUIRED");
      const id = previous?.id || await derivedId(`${variant.id}:variant:${value.value_translations.en}`);
      variants.set(id, { ...variant, id, sku: previous?.sku || `${String(form.sku || "PRODUCT").slice(0, 87)}-${id.replace(/-/g, "").toUpperCase()}`,
        option_value_ids: selected, active: true, inventory_quantity: Math.floor(variant.inventory_quantity / values.length) + (index < variant.inventory_quantity % values.length ? 1 : 0) });
    }
  }
  const replacements = new Map(values.map((value) => [value.id, value]));
  const oldValues = option.values.map((value) => value.id === valueId ? { ...value, active: false } : replacements.get(value.id) || value);
  const oldIds = new Set(oldValues.map((value) => value.id));
  return { options: form.options.map((item) => item.id === optionId ? { ...item, values: [...oldValues, ...values.filter((value) => !oldIds.has(value.id))] } : item), variants: [...variants.values()] };
};

const inventoryFingerprint = (quantity, variants) => JSON.stringify({
 quantity:Number(quantity || 0), variants:variants.map(v=>[v.id,Number(v.inventory_quantity ?? v.quantity ?? 0)]).sort((a,b)=>String(a[0]).localeCompare(String(b[0])))
});
export const buildVariantInventoryPayload = (form, suffix) => {
 const inventory=buildInventory(form,suffix);
 inventory.variants=inventory.variants.map(variant=>{
   const result={...variant};
   for(const key of ["track_inventory","low_stock_threshold","allow_backorder"]){
     if(!form.inventorySettingsBaseline || form[key]!==form.inventorySettingsBaseline[key]) {
       if(form[key]!==undefined) result[key]=key==="low_stock_threshold" ? Number(form[key]) : Boolean(form[key]);
     }
   }
   return result;
 });
 return {...inventory, expected_catalog_version:form.catalog_version || null,
 expected_inventory_version:form.inventory_version || null,
 preserve_inventory:Boolean(form.inventoryBaseline && form.inventoryBaseline===inventoryFingerprint(form.inventory_quantity, inventory.variants))};
};
