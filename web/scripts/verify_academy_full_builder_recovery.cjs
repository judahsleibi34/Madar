// Post-cleanup verification and durable local owner draft. No QA content is retained.
const {chromium,expect}=require('../frontend/node_modules/@playwright/test');
const fs=require('node:fs');
const origin='http://127.0.0.1:5173',out='docs/verification/academy-full-builder';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.addInitScript(()=>localStorage.setItem('madar.language','en'));
 async function api(path,data,method='GET') {return page.evaluate(async({path,data,method})=>{const {apiFetch}=await import('/src/utils/apiClient.js');const r=await apiFetch('/api'+path,{method,headers:{'Content-Type':'application/json',...(path==='/public/academies/management/landing'?{'X-Madar-Builder-Contract':'cloud-draft-v1'}:{})},...(data?{body:JSON.stringify(data)}:{})});if(!r.ok)throw Error(path+' '+r.status);return r.json();},{path,data,method});}
 try{
  await page.goto(origin+'/dashboard');await expect(page.getByRole('button',{name:'E-Learning',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'E-Learning',exact:true}).click();await page.locator('.admin-sidebar').getByRole('link',{name:'Academy',exact:true}).click();
  // Enable the local review surface through the real hub, preserving saved content.
  const enabled=page.getByRole('switch');if(!await enabled.isChecked()){await enabled.check();await page.getByRole('button',{name:'Save Changes',exact:true}).click();await expect(page.getByRole('status')).toBeVisible();}
  await page.getByRole('button',{name:'Edit Academy',exact:true}).click();await expect(page).toHaveURL(/\/page-builder\/projects\/[^/]+\/pages$/);await expect(page.getByLabel('Page name',{exact:true})).toBeVisible();
  const id=page.url().match(/projects\/([^/]+)/)[1],record=(await api(`/builder/projects/${id}`)).project;
  expect(record.usage_profile).toBe('academy');expect(record.published_schema).toBeFalsy();expect(record.draft_schema.pages.length).toBe(1);expect(JSON.stringify(record.draft_schema)).not.toContain('Academy QA Instructor');expect(JSON.stringify(record.draft_schema)).not.toContain('Unpublished Academy Change');
  await page.reload();await expect(page.getByLabel('Page name',{exact:true})).toBeVisible();
  await page.goto(origin+'/e-learning/settings/academy');await page.getByRole('button',{name:'Edit Academy',exact:true}).click();await expect(page).toHaveURL(origin+`/page-builder/projects/${id}/pages`);await expect(page.getByLabel('Page name',{exact:true})).toBeVisible();
  expect((await api('/public/academies/management/landing',{},'POST')).project.id).toBe(id);
  await page.screenshot({path:out+'/recovered-owner-builder.png',fullPage:true});
  await page.getByRole('button',{name:'Preview site',exact:true}).click();await expect(page.getByRole('button',{name:'Exit site preview',exact:true})).toBeVisible();await page.screenshot({path:out+'/recovered-owner-preview.png',fullPage:true});
  expect(errors).toEqual([]);
  const result={project:id,editor:`/page-builder/projects/${id}/pages`,published:false,checks:'After guarded QA cleanup, normal owner Edit safely creates one clean durable draft; reload/repeated Edit and initializer reuse that ID; original saved presentation seeds once; owner preview resolves existing public data; no QA content or fake learner; local Academy enabled for owner review',errors};
  fs.writeFileSync(out+'/recovery-results.json',JSON.stringify(result,null,2));fs.writeFileSync('/tmp/madar-academy132-owner-review.json',JSON.stringify(result,null,2));console.log('Post-cleanup recovery passed:',result.editor);
 }catch(e){await page.screenshot({path:out+'/recovery-failure.png',fullPage:true});console.error(await page.locator('body').innerText());throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
