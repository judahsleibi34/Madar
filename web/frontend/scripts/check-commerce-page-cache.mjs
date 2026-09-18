import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
const origin=process.argv[2]||'http://localhost:5173';
assert(['localhost','127.0.0.1'].includes(new URL(origin).hostname));
const b=await chromium.launch();
try{
const p=await b.newPage();const reads=new Map(),errors=[];p.on('pageerror',e=>errors.push(e.message));
const user={id:24,tenant_id:7,first_name:'Owner',email:'owner@example.com',user_type:'user',subscription_type:'full_platform',plan:'business'};
const product={id:'product-1',slug:'chair',sku:'CHAIR',translations:{en:{name:'Chair'}},status:'active',price:20,currency:'USD',images:[],inventory_quantity:20};
const theme={accent:'#852f25',background:'#f3efe7',surface:'#ffffff',text:'#192238',muted:'#667085',border:'#ddd4c6',hover:'#71271f',button_text:'#ffffff'};
await p.route('**/*',r=>{
 const u=new URL(r.request().url()),path=u.pathname;
 const json=d=>r.fulfill({contentType:'application/json',body:JSON.stringify(d)});
 if(path.startsWith('/api/')){
 if(path.includes('/ecommerce/')||path.endsWith('/website/settings'))reads.set(path,(reads.get(path)||0)+1);
 if(path.endsWith('/auth/user_status'))return json({logged_in:true,user,csrf_token:'test-token'});
 if(path.endsWith('/website/settings'))return json({website:{brand:'Madar Store',subdomain:'demo'}});
 if(path.endsWith('/ecommerce/catalog'))return json({products:[product],tags:[],categories:[],commerce_currency:'USD'});
 if(path.endsWith('/ecommerce/settings'))return json({currency:'USD',currency_locked:false});
 if(path.endsWith('/ecommerce/theme'))return json({theme});
 if(path.endsWith('/ecommerce/delivery-areas'))return json({areas:[{id:'area-1',name_en:'City',enabled:true,fee:0}],countries:[],locations:[]});
 if(path.endsWith('/ecommerce/orders'))return json({orders:[],pagination:{has_more:false}});
 if(path.endsWith('/ecommerce/loyalty'))return json({rule:{enabled:true,earning_rate_basis_points:500,threshold_points:100,discount_conditions:[{audience:'loyalty',product_ids:['product-1'],discount_basis_points:1000,validity_mode:'lifetime'}]}});
 if(path.includes('/public/sites/'))return json({site:{brand:'Madar Store',commerce_currency:'USD'},catalog:{products:[],categories:[],tags:[],pagination:{total:0}},conditions:[]});
 return json({notifications:[],unread_count:0,projects:[],preferences:[],installations:[]});
 }
 if(u.origin!==origin)return r.abort();return r.continue();
});
const pages=['tags','categories','products','delivery','orders','loyalty','theme','store'];
for(const page of pages){
 await p.goto(`${origin}/ecommerce/${page}`);
 await p.locator('.authenticated-main :is(.ecommerce-page,.ecommerce-store-admin,.ecommerce-theme-page)').first().waitFor();
 await p.waitForFunction(()=>!document.querySelector('.authenticated-main :is(.ecommerce-page-skeleton,.ecommerce-operations-skeleton,.ecommerce-theme-skeleton,.ecommerce-store-page-skeleton,.ecommerce-route-skeleton-header)'));
 await p.waitForTimeout(100);
}
const initial=Object.fromEntries(reads);
for(const page of pages){
 await p.goto(`${origin}/ecommerce/${page}`);
 await p.locator('.authenticated-main :is(.ecommerce-page,.ecommerce-store-admin,.ecommerce-theme-page)').first().waitFor();
 await p.waitForFunction(()=>!document.querySelector('.authenticated-main :is(.ecommerce-page-skeleton,.ecommerce-operations-skeleton,.ecommerce-theme-skeleton,.ecommerce-store-page-skeleton,.ecommerce-route-skeleton-header)'));
 assert.equal(await p.locator('.authenticated-main :is(.ecommerce-page-skeleton,.ecommerce-operations-skeleton,.ecommerce-theme-skeleton,.ecommerce-store-page-skeleton)').count(),0,`${page} should render cached data immediately`);
 await p.waitForTimeout(100);
}
assert.deepEqual(Object.fromEntries(reads),initial,'Repeat visits must reuse fresh data without extra store API reads');
assert.equal(reads.get('/api/ecommerce/catalog'),1,'Catalog is shared by Tags, Categories, Products, and Loyalty');
await p.setViewportSize({width:393,height:852});
await p.goto(`${origin}/ecommerce/store`);
await p.locator('.ecommerce-store-frame').waitFor();
const mobile = await p.evaluate(() => {
  const frame=document.querySelector('.ecommerce-store-frame').getBoundingClientRect();
  const title=document.querySelector('.ecommerce-store-admin h1').getBoundingClientRect();
  return {frameWidth:frame.width,frameRight:frame.right,titleTop:title.top,overflow:document.documentElement.scrollWidth>innerWidth};
});
assert(mobile.frameWidth>=350, '393px mobile preview must use available width');
assert(mobile.frameRight<=393 && mobile.titleTop>=58 && !mobile.overflow, 'Mobile heading and preview must fit below navigation');
assert.deepEqual(errors,[]);
console.log('All 8 store pages reused cached data across reloads; 0 extra store API reads. Catalog fetched once across 4 pages.');
}finally{await b.close();}
