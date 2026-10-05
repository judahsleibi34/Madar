import { describe, it, expect, vi } from "vitest";
import { webcrypto } from "node:crypto";
import { hydrateVariantGroups, buildVariantInventoryPayload, splitLegacySizeGroup, catalogSaveErrorMessage, editVariantColor, splitLegacyOptionValue } from "./productVariantIdentity";
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,"0")}`;
const product=()=>({sku:"BASE",options:[
{id:id(1),code:"size",name_translations:{en:"Size",ar:"المقاس"},display_type:"text",sort_order:0,values:[
{id:id(3),code:"variant-1-36",value_translations:{en:"36",ar:"٣٦"},sort_order:1},
{id:id(4),code:"variant-2-37",value_translations:{en:"37"},sort_order:0}]},
{id:id(2),code:"color",name_translations:{en:"Color"},display_type:"color",sort_order:1,values:[
{id:id(5),code:"color-2-red",value_translations:{en:"Red"},color_hex:"#ff0000",sort_order:1},
{id:id(6),code:"color-1-blue",value_translations:{en:"Blue"},color_hex:"#0000ff",sort_order:0}]}],variants:[
{id:id(7),sku:"S36R",inventory_quantity:11,track_inventory:false,option_value_ids:[id(3),id(5)],active:true},
{id:id(8),sku:"S37R",inventory_quantity:5,option_value_ids:[id(4),id(5)],active:true},
{id:id(9),sku:"S36B",inventory_quantity:8,option_value_ids:[id(3),id(6)],active:true}]});
const formFor=p=>({...p,...hydrateVariantGroups(p)});
const identities=p=>({options:p.options.map(o=>[o.id,o.code,o.values.map(v=>[v.id,v.code]).sort()]).sort(),variants:p.variants.map(v=>[v.id,v.sku,v.option_value_ids]).sort()});
describe("persistent identities",()=>{
 it("normal edits preserve UUIDs, codes, translations and tracking",()=>{
  const p=product(), form=formFor(p);form.variantGroups[0].colors[0].quantity=42;
  const saved=buildVariantInventoryPayload(form,"FIXED");
  expect(saved.options[0].code).toBe("size");expect(saved.options[0].name_translations.ar).toBe("المقاس");
  expect(saved.options[0].values.find(v=>v.id===id(3)).value_translations.ar).toBe("٣٦");
  expect(saved.variants.map(v=>v.id).sort()).toEqual(p.variants.map(v=>v.id).sort());
  expect(saved.variants.find(v=>v.id===id(7)).track_inventory).toBe(false);
  expect(saved.options.flatMap(o=>o.values).map(v=>v.code).sort()).toEqual(p.options.flatMap(o=>o.values).map(v=>v.code).sort());
 });
 it("size/color reorder changes order without identity churn",()=>{
  const f=formFor(product()),before=buildVariantInventoryPayload(f,"FIXED");f.variantGroups.reverse();f.variantGroups.forEach(g=>g.colors.reverse());
  const after=buildVariantInventoryPayload(f,"FIXED");expect(identities(after)).toEqual(identities(before));expect(after.options[0].values[0].id).toBe(id(3));expect(after.options[0].values[0].sort_order).toBe(0);
 });
 it("hydration has stable tie breaking regardless of query order",()=>{
  const p=product(),a=hydrateVariantGroups(p);p.options.reverse();p.variants.reverse();p.options.forEach(o=>o.values.reverse());expect(hydrateVariantGroups(p)).toEqual(a);expect(a.variantGroups.map(g=>g.name)).toEqual(["37","36"]);expect(a.variantGroups[1].colors.map(c=>c.colorName)).toEqual(["Blue","Red"]);
 });
 it("shares one color value across variants",()=>{const p=buildVariantInventoryPayload(formFor(product()),"FIXED");expect(p.options[1].values.filter(v=>v.value_translations.en==="Red")).toHaveLength(1);expect(p.variants.filter(v=>v.option_value_ids.includes(id(5)))).toHaveLength(2);});
 it("never transforms combined sizes merely by hydrating",()=>{const p=product();p.options[0].values[0].value_translations.en="36 - 37 - 38";expect(hydrateVariantGroups(p)).toEqual(hydrateVariantGroups(p));expect(hydrateVariantGroups(p).variantGroups.find(g=>g.id===id(3)).name).toBe("36 - 37 - 38");});
 it("explicit splitting conserves stock and is deterministic and idempotent",async()=>{
  vi.stubGlobal("crypto",webcrypto);
  try {
   const p=product();p.options[0].values=p.options[0].values.slice(0,1);p.options[0].values[0].value_translations.en="36 - 37 - 38";p.variants=p.variants.filter(v=>v.id!==id(8));
   const f=formFor(p),a=await splitLegacySizeGroup(f,id(3));expect(a).toEqual(await splitLegacySizeGroup(f,id(3)));expect(a.map(g=>g.name)).toEqual(["36","37","38"]);
   for(const c of f.variantGroups[0].colors)expect(a.reduce((sum,g)=>sum+g.colors.find(v=>v.valueId===c.valueId).quantity,0)).toBe(c.quantity);
   const saved=buildVariantInventoryPayload({...f,variantGroups:a},"FIXED");expect(identities(buildVariantInventoryPayload(formFor({...p,...saved}),"FIXED"))).toEqual(identities(saved));expect(await splitLegacySizeGroup({...f,variantGroups:a},a[0].id)).toEqual(a);
  } finally {vi.unstubAllGlobals();}
 });
 it("reuses matching inactive values and variants during explicit split",async()=>{
  vi.stubGlobal("crypto",webcrypto);try {
   const p=product();p.options[0].values.push({id:id(10),code:"combined",value_translations:{en:"36 - 37"}});p.variants=p.variants.map(v=>({...v,active:false}));p.variants.push({id:id(11),sku:"COMBINED",active:true,inventory_quantity:10,option_value_ids:[id(10),id(5)]});
   const a=await splitLegacySizeGroup(formFor(p),id(10));expect(a.map(g=>g.id)).toEqual([id(3),id(4)]);expect(a.map(g=>g.colors[0].id)).toEqual([id(7),id(8)]);
  } finally {vi.unstubAllGlobals();}
 });
 it("new codes/SKUs do not depend on array index",()=>{const f=formFor(product());f.variantGroups.forEach(g=>{delete g.code;g.colors.forEach(c=>{delete c.valueCode;c.sku="";});});const before=buildVariantInventoryPayload(f,"FIXED");f.variantGroups.reverse();expect(identities(buildVariantInventoryPayload(f,"FIXED"))).toEqual(identities(before));});
});
describe("conflict taxonomy",()=>{
 const t=(key,args)=>args?`${key}:${args.id}`:key;
 it.each(["PRODUCT_SKU_CONFLICT","PRODUCT_SLUG_CONFLICT","VARIANT_SKU_CONFLICT","CATALOG_SKU_CONFLICT","OPTION_CODE_CONFLICT","OPTION_NAME_CONFLICT","OPTION_VALUE_CODE_CONFLICT","OPTION_VALUE_CONFLICT","VARIANT_COMBINATION_CONFLICT","CATALOG_CHANGED_CONFLICT","CATALOG_UNIQUE_CONFLICT"])("prefers %s",code=>{expect(catalogSaveErrorMessage({code,status:409},t)).toBe(`commerce:errors.${code}`);});
 it("unknown 409 uses safe fallback and support reference",()=>{const message=catalogSaveErrorMessage({status:409,context:{reference_id:"ref-1234"}},t);expect(message).toContain("CATALOG_UNIQUE_CONFLICT");expect(message).toContain("ref-1234");});
});

it("shared color metadata edits propagate without changing quantities or UUIDs", () => {
 const f=formFor(product());const edited=editVariantColor(f.variantGroups,id(3),id(7),{colorName:"Ruby",colorValue:"#AA0000",quantity:50});
 const linked=edited.flatMap(g=>g.colors).filter(c=>c.valueId===id(5));
 expect(linked.map(c=>c.colorName)).toEqual(["Ruby","Ruby"]);
 expect(linked.find(c=>c.id===id(8)).quantity).toBe(5);
 expect(linked.find(c=>c.id===id(7)).quantity).toBe(50);
 const saved=buildVariantInventoryPayload({...f,variantGroups:edited},"FIXED");
 expect(saved.options[1].values.filter(v=>v.id===id(5))).toHaveLength(1);
});

it("sends the catalog concurrency token from hydration on variant saves",()=>{
 const p=product();p.catalog_version="a".repeat(64);
 expect(buildVariantInventoryPayload(formFor(p),"FIXED").expected_catalog_version).toBe(p.catalog_version);
});

it.each([1,3])("preserves a native %i-dimension topology on normal saves", (count) => {
 const p=product();
 if (count===1) {p.options=p.options.slice(0,1);p.variants=p.variants.map(v=>({...v,option_value_ids:v.option_value_ids.slice(0,1)})).filter(v=>v.id!==id(9));}
 else {p.options.push({id:id(20),code:"finish",display_type:"text",name_translations:{en:"Finish"},values:[{id:id(21),code:"matte",value_translations:{en:"Matte"}}]});p.variants=p.variants.map(v=>({...v,option_value_ids:[...v.option_value_ids,id(21)]}));}
 const f=formFor(p);expect(f.nativeVariantInventory).toBe(true);f.variants[0].inventory_quantity=99;
 const saved=buildVariantInventoryPayload(f,"FIXED");expect(identities(saved)).toEqual(identities(p));expect(saved.variants[0].inventory_quantity).toBe(99);
});

it("converts single-dimension legacy sizes with stable IDs and conserved stock",async()=>{
 vi.stubGlobal("crypto",webcrypto);try {
  const p=product();p.options=p.options.slice(0,1);p.options[0].values=[{id:id(30),code:"combined",value_translations:{en:"36 - 37 - 38"}}];
  p.variants=[{id:id(31),sku:"COMBINED",inventory_quantity:10,active:true,option_value_ids:[id(30)]}];
  const a=await splitLegacyOptionValue(p,id(1),id(30)),b=await splitLegacyOptionValue(p,id(1),id(30));expect(a).toEqual(b);
  const saved=buildVariantInventoryPayload(formFor({...p,...a}),"FIXED");expect(saved.options[0].values.map(v=>v.value_translations.en)).toEqual(["36","37","38"]);
  expect(saved.variants.reduce((sum,v)=>sum+v.inventory_quantity,0)).toBe(10);
  expect(identities(buildVariantInventoryPayload(formFor({...p,...saved}),"FIXED"))).toEqual(identities(saved));
 } finally {vi.unstubAllGlobals();}
});

it("native single-option hydration is deterministic without unused random identities",()=>{
 const p=product();p.options=p.options.slice(0,1);p.variants=p.variants.map(v=>({...v,option_value_ids:v.option_value_ids.slice(0,1)}));
 expect(hydrateVariantGroups(p)).toEqual(hydrateVariantGroups(p));
});

it("rejects renaming two persisted colors to one name without merging their identities",()=>{
 const f=formFor(product());f.variantGroups.forEach(g=>g.colors.forEach(c=>{c.colorName="Red";}));
 try {buildVariantInventoryPayload(f,"FIXED");throw new Error("expected conflict");} catch(error) {expect(error.code).toBe("OPTION_VALUE_CONFLICT");}
});

it("retains the concurrency guard when removing all variants",()=>{
 expect(buildVariantInventoryPayload({variantGroups:[],catalog_version:"version"},"FIXED").expected_catalog_version).toBe("version");
});

it("preserves live stock on descriptive edits and guards actual quantity changes",()=>{
 const p=product();p.catalog_version="c";p.inventory_version="i";const f=formFor(p);
 expect(buildVariantInventoryPayload(f,"FIXED")).toMatchObject({preserve_inventory:true,expected_inventory_version:"i"});
 f.variantGroups[0].colors[0].quantity++;expect(buildVariantInventoryPayload(f,"FIXED").preserve_inventory).toBe(false);
});

it("reordering a new shared-color group before existing groups retains the persisted color identity",()=>{
 const f=formFor(product());f.variantGroups.unshift({id:id(31),name:"38",colors:[{id:id(32),valueId:id(33),colorName:"Red",colorValue:"#FF0000",quantity:1}]});
 const saved=buildVariantInventoryPayload(f,"FIXED");const red=saved.options[1].values.find(v=>v.value_translations.en==="Red");
 expect(red).toMatchObject({id:id(5),code:"color-2-red"});
});
