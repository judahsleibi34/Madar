import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';
const origin = process.argv[2] || 'http://localhost:5173';
assert(['localhost','127.0.0.1','[::1]'].includes(new URL(origin).hostname));
const browser = await chromium.launch({headless:true});
let count=0;
try {
const page=await browser.newPage();
const errors=[];page.on('pageerror', e=>errors.push(e.message));
await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.pathname.startsWith('/api/')||u.origin!==origin)return route.fulfill({contentType:'application/json',body:JSON.stringify({logged_in:false,notifications:[],user:null})});return route.continue();});
await page.goto(origin+'/login');
await page.waitForSelector('#root form');
await page.evaluate(async()=>{
 const reactModule=await import('/node_modules/.vite/deps/react.js'); const React=reactModule.default || reactModule;
 const dom=await import('/node_modules/.vite/deps/react-dom_client.js'); const createRoot=dom.createRoot || dom.default.createRoot;
 const layouts=await import('/src/components/DashboardBuilder/CommerceLoadingLayouts.jsx');
 const {default:Operations}=await import('/src/components/DashboardBuilder/EcommerceOperationsSkeleton.jsx');
 document.querySelector('#root').style.display='none';
 const el=document.createElement('div');el.id='loading-test';el.className='admin-dashboard-page';document.body.append(el);
 window.renderSkeleton=(variant,lang)=>{
  el.dir=lang==='ar'?'rtl':'ltr';
  let component,props={label:'Loading'};
  if(variant==='store')component=layouts.StorePreviewSkeleton;
  else if(variant==='theme')component=layouts.ThemeSkeleton;
  else if(variant==='editor')component=layouts.ProductEditorSkeleton;
  else if(variant==='settings')component=layouts.SettingsSkeleton;
  else if(variant==='catalog')component=layouts.CatalogSkeleton;
  else {component=Operations;props.variant=variant;}
  window.loadingRoot.render(React.createElement('div',{className:variant==='settings'?'settings-page':'ecommerce-page'},React.createElement(component,props)));
 };
 window.loadingRoot=createRoot(el);
});
for(const width of [320,768,1440])for(const lang of ['en','ar'])for(const theme of ['light','dark'])for(const variant of ['store','theme','editor','settings','catalog','delivery','loyalty','orders','order-detail']){
 await page.setViewportSize({width,height:900});
 await page.evaluate(({variant,lang,theme})=>{document.documentElement.dataset.theme=theme;window.renderSkeleton(variant,lang);},{variant,lang,theme});
 await page.waitForTimeout(40);
 const result=await page.evaluate(()=>{
  const root=document.querySelector('#loading-test');
  return {statuses:root.querySelectorAll('[role=status]').length,overflow:[...root.querySelectorAll('i,section,article,[role=status]')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.left< -1||r.right>innerWidth+1);}).map(e=>e.className||e.tagName)};
 });
 assert.equal(result.statuses,1,`${variant}: one loading announcement`);
 assert.deepEqual(result.overflow,[],`${width} ${lang} ${theme} ${variant}: no overflow`);count++;
}
await page.emulateMedia({reducedMotion:'reduce'});
await page.evaluate(()=>window.renderSkeleton('theme','ar'));await page.waitForTimeout(50);
const animations=await page.locator('#loading-test i').evaluateAll(elements=>elements.map(e=>getComputedStyle(e).animationName));
assert(animations.every(a=>a==='none'),'Reduced motion disables shimmer');
assert.deepEqual(errors,[],'No browser exceptions');
let storeChecks = 0;
for (const width of [320,1440]) for (const lang of ['en','ar']) {
 const livePage = await browser.newPage({viewport:{width,height:900}});
 let releaseSettings;
 const pendingSettings = new Promise(resolve=>{releaseSettings=resolve;});
 await livePage.addInitScript(lang=>localStorage.setItem('madar.language',lang),lang);
 await livePage.route('**/*',async route=>{
  const u=new URL(route.request().url()), path=u.pathname;
  const json=data=>route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  if(path.endsWith('/auth/user_status'))return json({logged_in:true,user:{id:24,tenant_id:7,first_name:'Owner',email:'owner@example.com',user_type:'user',subscription_type:'full_platform',plan:'business'}});
  if(path.endsWith('/website/settings')){await pendingSettings;return json({website:{subdomain:'demo'}});}
  if(path.includes('/public/sites/'))return json({site:{brand:'Madar Store'},catalog:{products:[],categories:[],tags:[],pagination:{page:1,pages:1,total:0}},areas:[]});
  if(path.startsWith('/api/')||u.origin!==origin)return json({notifications:[],unread_count:0,projects:[]});
  return route.continue();
 });
 await livePage.goto(origin+'/ecommerce/store');
 await livePage.locator('.ecommerce-store-page-skeleton').waitFor();
 const before=await livePage.locator('.ecommerce-store-page-skeleton').boundingBox();
 assert(before.width<=width && before.height<=780,'Store skeleton must have bounded preview dimensions');
 assert.equal(await livePage.locator('.commerce-preview-hero').count(),1,'Store loading must show the preview structure');
 assert.equal(await livePage.locator('.ecommerce-store-frame').count(),0,'Wait for the configured address before mounting the iframe');
 releaseSettings();
 await livePage.locator('.ecommerce-store-frame').waitFor();
 await livePage.waitForFunction(()=>!document.querySelector('.ecommerce-store-frame-loading'));
 const after=await livePage.locator('.ecommerce-store-frame-shell').boundingBox();
 assert(Math.abs(after.height-before.height)<=1,'Preview skeleton and iframe reserve the same height');
 assert.equal(await livePage.locator('.ecommerce-store-frame-shell').getAttribute('aria-busy'),'false');
 await livePage.close();storeChecks++;
}
console.log(`${count} responsive skeleton checks, reduced motion, and ${storeChecks} slow Store loading lifecycles passed`);
} finally {await browser.close();}
