import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {chromium} from '@playwright/test';
const origin=process.argv[2]||'https://madarportal.com';
assert(['https://madarportal.com','http://localhost:5173'].includes(origin));
const mock=process.env.RESPONSIVE_MOCK==='1';
assert(!mock||new URL(origin).hostname==='localhost','Mock data is allowed only on loopback');
const browser=await chromium.launch({headless:true});
const results=[];
const browserErrors=[];
const routes=['','/catalog','/categories','/contact','/product/nike-t-shirt','/checkout'];
try{
for(const width of [320,390,768,1024,1440])for(const lang of ['en','ar']){
 const context=await browser.newContext({viewport:{width,height:900}});const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>{errors.push(e.message);browserErrors.push({width,lang,message:e.message});});
 await page.addInitScript(lang=>{
 localStorage.setItem('madar.language',lang);
 localStorage.setItem('madar-store-cart:madar-demo',JSON.stringify([{id:'4e298339-4a33-45f1-b89d-d60e40e34581',slug:'nike-t-shirt',name:'Nike T shirt',price:80,currency:'USD',quantity:1,images:[]}]));
 },lang);
 await page.route('**/*',r=>{
 const u=new URL(r.request().url()),p=u.pathname;
 if(mock && p.startsWith('/api/')){
 const json=d=>r.fulfill({contentType:'application/json',body:JSON.stringify(d)});
 const site={brand:'Madar Store With A Longer Bilingual Name',brand_ar:'\u0645\u062a\u062c\u0631 \u0645\u062f\u0627\u0631',description:'A long description that should wrap across narrow screens.',commerce_currency:'USD',contact_email:'shop@example.com',phone:'+15550102026'};
 const product={id:'4e298339-4a33-45f1-b89d-d60e40e34581',slug:'nike-t-shirt',name:'Nike T shirt with a longer product name',price:80,currency:'USD',in_stock:true,images:[]};
 const categories=[{id:'category-1',slug:'studio-wear',name:'Studio Wear and Everyday Movement Accessories',description:'A longer category description that should wrap.'}];
 if(p.includes('/catalog/products/'))return json({site,product,category:categories[0],options:[],variants:[],attributes:[],tags:[]});
 if(p.endsWith('/delivery-areas'))return json({areas:[{id:'area-1',name_en:'City',name_ar:'City',fee:0}]});
 if(p.endsWith('/store-profile'))return json({site});
 if(p.endsWith('/loyalty/me'))return json({eligible:false});
 if(p.endsWith('/discounts'))return json({conditions:[]});
 if(p.includes('/auth/'))return json({logged_in:false,user:null});
 return json({site,catalog:{products:[product],categories,tags:[],pagination:{page:1,pages:1,total:1,limit:12}}});
 }
 if(mock && u.origin!==origin)return r.abort();
 return ['GET','HEAD','OPTIONS'].includes(r.request().method())?r.continue():r.abort();
 });
 for(const suffix of routes){
 const path='/site/madar-demo/shop'+suffix;
 await page.goto(origin+path,{waitUntil:'domcontentloaded'});
 await page.locator('.live-store-header').waitFor({timeout:25000});
 await page.locator('.live-store-skeleton').waitFor({state:'detached',timeout:25000});
 await page.waitForTimeout(300);
 await page.evaluate(()=>{for(const a of document.getAnimations()){const t=a.effect?.getComputedTiming();if(t&&Number.isFinite(t.endTime))try{a.finish();}catch{}}});
 const inspect=()=>page.evaluate(()=>{
 const visible=e=>e.checkVisibility({checkVisibilityCSS:true,checkOpacity:true})&&e.getBoundingClientRect().width>0;
 const root=document.querySelector('.live-store');
 const issues=[...root.querySelectorAll('h1,h2,h3,input,select,textarea,button,a,.live-store-header-inner,.live-store-cart-drawer,.live-store-checkout-form,.live-store-footer')].filter(visible).flatMap(e=>{
 const r=e.getBoundingClientRect();const wide=r.left< -1||r.right>innerWidth+1;
 const clipped=e.matches('button,input,select')&&e.scrollWidth>e.clientWidth+2;
 return wide||clipped?[{element:e.className||e.tagName,text:(e.textContent||'').trim().slice(0,50),left:Math.round(r.left),right:Math.round(r.right),client:e.clientWidth,scroll:e.scrollWidth}]:[];
 });
 const header=[...root.querySelectorAll('.live-store-header-inner > *')].filter(visible);const overlaps=[];
 for(let i=0;i<header.length;i++)for(let j=i+1;j<header.length;j++){const a=header[i].getBoundingClientRect(),b=header[j].getBoundingClientRect();if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>2&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2)overlaps.push([header[i].className||header[i].tagName,header[j].className||header[j].tagName]);}
 return {issues,overlaps,dir:root.dir,horizontal:document.documentElement.scrollWidth>innerWidth+1,loading:!!root.querySelector('.live-store-skeleton')};
 });
 const state=await inspect();
 assert.equal(await page.locator('.live-store-state.is-error').count(),0,'Store data must load before responsiveness checks');
 if(await page.locator('.live-store-mobile-menu').isVisible()){
 await page.locator('.live-store-mobile-menu').click();state.menu=await inspect();await page.locator('.live-store-menu-panel >header button').click();
 }
 await page.locator('.live-store-cart').click();await page.locator('.live-store-cart-drawer').waitFor();state.cart=await inspect();
 if(mock && width<=760){
 const small=await page.locator('.live-store-mobile-menu,.live-store-header-search button,.live-store-cart-drawer >header button,.live-store-cart-item-actions button').evaluateAll(es=>es.filter(e=>e.checkVisibility()).filter(e=>{const r=e.getBoundingClientRect();return r.width<44||r.height<44;}).map(e=>e.className||e.getAttribute('aria-label')));
 assert.deepEqual(small,[],'Mobile icon controls must be at least 44px');
 }
 const failures=state.issues.length+state.overlaps.length+Number(state.horizontal)+(state.menu?.issues.length||0)+(state.menu?.overlaps.length||0)+state.cart.issues.length+state.cart.overlaps.length;
 if(state.dir!==(lang==='ar'?'rtl':'ltr'))state.directionFailure=true;
 results.push({width,lang,path,failures,directionFailure:state.directionFailure,state});
 console.log(`${failures||state.directionFailure?'FAIL':'PASS'} ${width} ${lang} ${suffix||'/'} ${failures}`);
 }
 await context.close();
}
const failures=results.filter(r=>r.failures||r.directionFailure);const report=process.env.RESPONSIVE_REPORT||path.join(os.tmpdir(),'madar-storefront-responsive.json');
await fs.writeFile(report,JSON.stringify({origin,checks:results.length,errors:browserErrors,failures},null,2));
console.log(JSON.stringify({checks:results.length,failed:failures.length,browserErrors:browserErrors.length,report}));
process.exitCode=failures.length||browserErrors.length?1:0;
}finally{await browser.close();}
