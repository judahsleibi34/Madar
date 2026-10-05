// Local-only verification: explicit local DB/payment adapter, existing test account.
const {chromium,expect}=require('../frontend/node_modules/@playwright/test');
const fs=require('node:fs');
const origin='http://127.0.0.1:5173',out='docs/verification/academy-ux';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 const fixture={tenant_id:3,user_id:1,courses:[],plans:[],templates:[],checkouts:[],credentials:[]},errors=[];let settings;
 const manifest=()=>fs.writeFileSync('/tmp/madar-academy131-browser-fixtures.json',JSON.stringify(fixture,null,2));
 page.on('pageerror',e=>errors.push(e.message));page.on('response',async r=>{if(r.status()>=400&&r.url().includes('/builder/projects/')){console.error('Builder response',r.status(),await r.text());if(r.request().method()==='PUT')fs.writeFileSync('/tmp/academy-ux-save-payload.json',r.request().postData());}});await page.addInitScript(()=>{if(!localStorage.getItem('madar.language'))localStorage.setItem('madar.language','en');});
 async function raw(path,data,method='GET'){const cookies=await context.cookies();return context.request.fetch(origin+'/api'+path,{method,headers:{Origin:origin,'X-CSRF-Token':cookies.find(c=>c.name==='madar_csrf_token')?.value||''},...(data?{data}:{})});}
 async function api(path,data,method='GET'){const r=await raw(path,data,method);if(!r.ok())throw Error(method+' '+path+' '+r.status()+' '+await r.text());return r.json();}
 async function create(name,access='free',status='published'){
  const course=(await api('/elearning/courses',{name,description:'Local Academy verification',status,access_type:access},'POST')).course;fixture.courses.push(course.id);manifest();
  let s=await api(`/elearning/courses/${course.id}/structure/commands`,{action:'create_section',expected_revision:1,payload:{name:'Level 1',status:'published'}},'POST');
  for(const name of ['Topic 1','Topic 2'])s=await api(`/elearning/courses/${course.id}/structure/commands`,{action:'create_lesson',expected_revision:s.revision,payload:{section_id:s.sections[0].id,name,status:'published'}},'POST');
  return {...course,lessons:s.sections[0].lessons};
 }
 async function plan(name,amount,billing,scope,ids=[]){const r=await api('/elearning/plans',{name,description:'Local Academy verification',status:'active',billing_type:billing,access_scope:scope,amount,currency:'USD',course_ids:ids,revision:1},'POST');fixture.plans.push(r.saved_plan_id);manifest();return r.saved_plan_id;}
 async function captureCheckouts(){fixture.checkouts=(await api('/elearning/my-plans')).checkouts.filter(c=>fixture.plans.includes(c.offering_id)).map(c=>c.id);manifest();}
 const screenshot=async name=>page.screenshot({path:`${out}/${name}.png`,fullPage:true});
 try {
 await page.goto(origin+'/dashboard');await expect(page.getByRole('button',{name:'E-Learning',exact:true})).toBeVisible();settings=(await api('/elearning/settings')).settings;fixture.settings=settings;manifest();
 await api('/elearning/settings',{...settings,enabled:true,academy_enabled:true,academy_featured_courses:[],sequential_progression:false},'PUT');
 const free=await create('Academy Free English'),paid=await create('Academy Paid Communication','paid'),entitled=await create('Academy Included Marketing','paid'),ongoing=await create('Academy In Progress'),completed=await create('Academy Completed Safety'),privateCourse=await create('Academy Private Secret','private'),draft=await create('Academy Draft Secret','free','draft');
 fixture.named={free,paid,entitled,ongoing,completed,privateCourse,draft};manifest();
 await api(`/elearning/courses/${free.id}/lessons/${free.lessons[0].id}/content/commands`,{action:'create',expected_revision:1,payload:{type:'text',title:'Welcome',content:{body:'Academy learning uses the shared renderer.'}}},'POST');
 const single=await plan('Academy Single Course',20,'one_time','single_course',[paid.id]),lifetime=await plan('Academy Lifetime All Access',49,'one_time','all_courses'),monthly=await plan('Academy Monthly All Access',49,'monthly','all_courses');
 for(const c of [ongoing,completed])await api(`/elearning/catalog/${c.id}/enrollment`,{},'POST');
 const design={name:'Academy Standard',title:'Certificate of Completion',subtitle:'',body:'{{learner_name}} completed {{course_name}}',issuer_name:'Academy Verification',signer_name:'',signer_title:'',logo_url:'',signature_url:''};
 const template=(await api('/elearning/certificate-templates',{design},'POST')).saved_id;fixture.templates.push(template);manifest();
 await api(`/elearning/courses/${completed.id}/certificate`,{enabled:true,template_id:template,title_override:'',issuer_override:''},'PUT');
 await api(`/elearning/my-learning/courses/${ongoing.id}/lessons/${ongoing.lessons[0].id}/completion`,{},'POST');
 for(const l of completed.lessons)await api(`/elearning/my-learning/courses/${completed.id}/lessons/${l.id}/completion`,{},'POST');
 fixture.credentials=(await api('/elearning/my-certificates')).credentials.filter(c=>fixture.courses.includes(c.course_id)).map(c=>c.id);manifest();
 // Normal owner navigation exposes the hub, with no duplicate content form.
 await page.getByRole('button',{name:'E-Learning',exact:true}).click();await page.locator('.admin-sidebar').getByRole('link',{name:'Academy',exact:true}).click();await expect(page).toHaveURL(origin+'/e-learning/settings/academy');
 await expect(page.getByRole('button',{name:'Edit Landing Page',exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'Open Academy',exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'Open Student Platform',exact:true})).toBeVisible();expect(await page.getByLabel('Hero title',{exact:true}).count()).toBe(0);await screenshot('academy-hub');
 await page.getByRole('link',{name:'Open Student Platform',exact:true}).click();await expect(page).toHaveURL(origin+'/my-learning');await expect(page.locator('.learning-shell-sidebar')).toBeVisible();expect(await page.locator('.admin-sidebar').count()).toBe(0);await expect(page.getByRole('link',{name:'Back to Admin',exact:true})).toBeVisible();await screenshot('owner-student-platform');
 await page.getByRole('link',{name:'Back to Admin',exact:true}).click();await page.goto(origin+'/e-learning/settings/academy');
 await page.getByRole('button',{name:'Edit Landing Page',exact:true}).click();
 await expect(page).toHaveURL(/\/page-builder\/projects\/[^/]+\/pages\/sections$/);
 fixture.builder_project=page.url().match(/projects\/([^/]+)/)[1];manifest();
 await expect(page.getByRole('tab',{name:/^Components/})).toHaveAttribute('aria-selected','true');
 await expect(page.locator('.workspace-tabs')).toContainText('Landing Page');
 await expect(page.getByRole('heading',{name:'Inspector',exact:true})).toBeVisible();
 expect(await page.getByRole('button',{name:'Create page',exact:false}).count()).toBe(0);
 expect(await page.getByRole('button',{name:'Forms',exact:true}).count()).toBe(0);
 expect(await page.getByRole('button',{name:'Reservations',exact:true}).count()).toBe(0);
 await expect(page.getByRole('button',{name:'Featured Courses',exact:false}).first()).toBeVisible();
 expect(await page.getByRole('button',{name:'Date request',exact:false}).count()).toBe(0);
 expect(await page.getByRole('button',{name:'Form Block',exact:false}).count()).toBe(0);
 // Use native layer selection and Inspector; course data remains a live projection.
 const seeded=(await api(`/builder/projects/${fixture.builder_project}`)).project.draft_schema;
 const hero=seeded.pages[0].sections[0],heroHeading=(hero.freeElements||hero.rows.flatMap(r=>r.columns.flatMap(c=>c.elements))).find(e=>e.type==='heading');
 await page.getByRole('combobox',{name:/^Select an element/}).selectOption(heroHeading.id);await page.locator('.builder-inspector').getByRole('textbox',{name:/^Content/}).fill('Learn English With Confidence');
 const featuredSection=seeded.pages[0].sections.find(s=>s.name==='Featured Courses'),featured=(featuredSection.freeElements||featuredSection.rows.flatMap(r=>r.columns.flatMap(c=>c.elements)))[0];
 await page.getByRole('combobox',{name:/^Select an element/}).selectOption(featured.id);await page.getByLabel(free.name,{exact:true}).check();await page.getByLabel(paid.name,{exact:true}).check();
 async function nativeSection(name,text,withImage=false){await page.getByRole('button',{name:'Add section',exact:true}).click();await page.getByLabel('Section name',{exact:true}).fill(name);await page.locator('.section-component-palette').getByRole('button',{name:'Text Drag into a section',exact:true}).click();await page.locator('.builder-inspector').getByRole('textbox',{name:/^Content/}).fill(text);if(withImage)await page.locator('.section-component-palette').getByRole('button',{name:'Image Drag into a section',exact:true}).click();}
 await nativeSection('Text and Image','Practice with focused lessons.',true);await nativeSection('Testimonials','Learners build confidence through practice.');await nativeSection('FAQ','Can I learn at my own pace? Yes, resume any time.');
 await page.getByRole('button',{name:'Add section',exact:true}).click();await page.getByLabel('Section name',{exact:true}).fill('Temporary section');await page.getByRole('button',{name:'Remove Temporary section section',exact:true}).click();
 await page.getByRole('button',{name:'Move Plans / Pricing up',exact:true}).click();
 const composedOrder=await page.locator('.academy-builder-composition li > button:first-child').allTextContents();
 await page.getByRole('button',{name:'Save',exact:true}).click();
 await expect.poll(async()=>((await api(`/builder/projects/${fixture.builder_project}`)).project.draft_schema.pages[0].sections.map(s=>s.name)),{timeout:20000}).toEqual(composedOrder);
 await page.reload();await expect(page.locator('.academy-builder-composition li > button:first-child')).toHaveText(composedOrder);
 fixture.builder_project=page.url().match(/projects\/([^/]+)/)[1];manifest();await screenshot('academy-builder');await page.getByRole('button',{name:'Preview site',exact:true}).click();await expect(page.getByRole('button',{name:'Exit site preview',exact:true})).toBeVisible();await screenshot('academy-builder-preview');await page.getByRole('button',{name:'Exit site preview',exact:true}).click();
 await page.getByRole('button',{name:'Go Live',exact:true}).click();
 await expect.poll(async()=>{const project=await api(`/builder/projects/${fixture.builder_project}`);return project.project.status;},{timeout:20000}).toBe('published');
 const publicSchema=(await api(`/builder/projects/${fixture.builder_project}`)).project.published_schema;
 expect(JSON.stringify(publicSchema)).not.toContain('progress_percent');expect(JSON.stringify(publicSchema)).not.toContain('enrollment_id');
 await page.goto(origin+'/e-learning/settings/academy');
 const base='/academy/testing';await page.getByRole('link',{name:'Open Academy',exact:true}).click();await expect(page).toHaveURL(origin+base);await expect(page.getByRole('heading',{name:'Learn English With Confidence'})).toBeVisible();await expect(page.getByRole('heading',{name:'Featured Courses'})).toBeVisible();await expect(page.getByRole('heading',{name:'Continue Learning'})).toBeVisible();expect(await page.locator(`[data-course-id="${privateCourse.id}"]`).count()).toBe(0);await screenshot('home-learner');
 const projection=await api('/public/academies/testing');expect(projection.authenticated).toBe(true);expect(projection.courses.find(c=>c.id===ongoing.id).progress.progress_percent).toBe(50);expect(projection.courses.find(c=>c.id===completed.id).cta.action).toBe('certificate');expect(projection.courses.find(c=>c.id===paid.id).price.amount).toBe(20);
 // Isolated anonymous browser: disable only the launcher's automatic test login.
 const guest=await browser.newContext({viewport:{width:1440,height:1000}}),guestPage=await guest.newPage();guestPage.on('pageerror',e=>errors.push(e.message));await guestPage.route('**/api/auth/user_status',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({logged_in:false,user:null})}));await guestPage.addInitScript(()=>{if(!localStorage.getItem('madar.language'))localStorage.setItem('madar.language','en');});await guestPage.goto(origin+base);await expect(guestPage.getByRole('heading',{name:'Learn English With Confidence'})).toBeVisible();await expect(guestPage.getByRole('heading',{name:'Continue Learning'})).toHaveCount(0);await expect(guestPage.getByRole('link',{name:'My Certificates'})).toHaveCount(0);await guestPage.screenshot({path:out+'/home-guest.png',fullPage:true});
 const guestData=await (await guest.request.get(origin+'/api/public/academies/testing')).json();expect(guestData.authenticated).toBe(false);expect(guestData.courses.every(c=>!c.progress&&!c.credential&&!c.resume)).toBe(true);expect((await guest.request.get(origin+`/api/public/academies/testing/courses/${privateCourse.id}`)).status()).toBe(404);expect((await guest.request.get(origin+`/api/public/academies/testing/courses/${draft.id}`)).status()).toBe(404);expect((await guest.request.get(origin+'/api/elearning/my-certificates')).status()).toBe(401);
 await guestPage.goto(origin+`${base}/courses/${free.id}`);await guestPage.getByRole('button',{name:'Enroll Free',exact:true}).click();await expect(guestPage.getByRole('heading',{name:'Sign in'})).toBeVisible();expect(new URL(guestPage.url()).searchParams.get('returnTo')).toBe(`${base}/courses/${free.id}?resume=enroll`);
 const config=require('../frontend/node_modules/dotenv').parse(fs.readFileSync('web/.env.database.local'));
 await guestPage.getByLabel('Email',{exact:true}).fill(config.MADAR_TEST_EMAIL);
 await guestPage.getByLabel('Password',{exact:true}).fill(config.MADAR_TEST_PASSWORD);
 await guestPage.unroute('**/api/auth/user_status');
 await guestPage.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(guestPage).toHaveURL(new RegExp(`/my-learning/courses/${free.id}$`));
 await expect(guestPage.locator('.learning-shell-sidebar')).toBeVisible();
 await guestPage.screenshot({path:out+'/free-auth-resumed.png',fullPage:true});
 await page.goto(origin+`${base}/courses/${paid.id}`);await expect(page.getByRole('heading',{name:paid.name,exact:true})).toBeVisible();await screenshot('paid-course');
 const purchaser=await browser.newContext({viewport:{width:1440,height:1000}}),purchasePage=await purchaser.newPage();
 purchasePage.on('pageerror',e=>errors.push(e.message));await purchasePage.addInitScript(()=>localStorage.setItem('madar.language','en'));
 await purchasePage.route('**/api/auth/user_status',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({logged_in:false,user:null})}));
 await purchasePage.goto(origin+`${base}/courses/${paid.id}`);await purchasePage.getByRole('button',{name:'Buy',exact:true}).first().click();
 await expect(purchasePage.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
 expect(new URL(purchasePage.url()).searchParams.get('returnTo')).toContain(`resume=checkout&plan=${single}`);
 await purchasePage.getByLabel('Email',{exact:true}).fill(config.MADAR_TEST_EMAIL);await purchasePage.getByLabel('Password',{exact:true}).fill(config.MADAR_TEST_PASSWORD);await purchasePage.unroute('**/api/auth/user_status');await purchasePage.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(purchasePage.getByRole('button',{name:'Confirm Test Payment',exact:true})).toBeVisible();await captureCheckouts();await purchasePage.screenshot({path:out+'/paid-auth-resumed.png',fullPage:true});
 await purchasePage.getByRole('button',{name:'Confirm Test Payment',exact:true}).click();await expect(purchasePage).toHaveURL(new RegExp(`/my-learning/courses/${paid.id}$`));await expect(purchasePage.locator('.learning-shell-sidebar')).toBeVisible();await expect(purchasePage.locator('.admin-sidebar')).toHaveCount(0);await purchasePage.screenshot({path:out+'/learning-runtime.png',fullPage:true});await purchaser.close();
 await page.goto(origin+`${base}/plans`);const lifetimeCard=page.locator('.academy-plan').filter({has:page.getByRole('heading',{name:'Academy Lifetime All Access',exact:true})});await lifetimeCard.getByRole('button',{name:'Buy',exact:true}).click();await captureCheckouts();await page.getByRole('button',{name:'Confirm Test Payment',exact:true}).click();await expect(page).toHaveURL(/\/my-learning\/plans$/);await expect(page.getByText('Academy Lifetime All Access',{exact:true}).first()).toBeVisible();await screenshot('my-plans');
 await page.goto(origin+`${base}/courses/${entitled.id}`);await expect(page.getByText('Included in Academy Lifetime All Access',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Enroll',exact:true}).click();await expect(page).toHaveURL(new RegExp(`/my-learning/courses/${entitled.id}$`));
 await page.goto(origin+`${base}/courses/${free.id}`);await page.getByRole('link',{name:'Continue Learning',exact:true}).click();await expect(page).toHaveURL(new RegExp(`/my-learning/courses/${free.id}(/lessons/[^/]+)?$`));await page.getByRole('link',{name:'Topic 1',exact:true}).first().click();await expect(page.getByRole('button',{name:'Mark Complete',exact:true})).toBeVisible();await expect(page.getByText('Academy learning uses the shared renderer.',{exact:true})).toBeVisible();await expect(page.getByRole('navigation',{name:'Academy navigation'})).toBeVisible();await page.getByRole('button',{name:'Mark Complete',exact:true}).click();await expect(page.getByText('Completed',{exact:true}).first()).toBeVisible();await page.reload();await expect(page.getByText('Completed',{exact:true}).first()).toBeVisible();
 await page.goto(origin+'/my-learning/certificates');await expect(page.getByRole('heading',{name:'My Certificates',exact:true})).toBeVisible();await screenshot('my-certificates');await page.goto(origin+`${base}/courses/${completed.id}`);await expect(page.getByRole('heading',{name:completed.name,exact:true})).toBeVisible();await page.getByRole('link',{name:'View Certificate',exact:true}).click();await expect(page.locator('.elearning-certificate-document')).toBeVisible();await screenshot('completed-credential');
 await page.goto(origin+`${base}/courses`);await page.getByRole('searchbox').fill('Academy Free English');await expect(page.locator('.academy-card')).toHaveCount(1);await screenshot('catalog');
 for(const [name,width,height] of [['tablet',768,1024],['mobile',390,844]]){await page.setViewportSize({width,height});await page.goto(origin+base);await expect(page.locator('.academy')).toBeVisible();expect(await page.locator('.academy').evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);await screenshot('home-'+name);await page.getByRole('button',{name:'Menu',exact:true}).click();await expect(page.getByRole('link',{name:'My Learning',exact:true})).toBeVisible();}
 await page.goto(origin+`/my-learning/courses/${free.id}/lessons/${free.lessons[0].id}`);await expect(page.getByText('Academy learning uses the shared renderer.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Course outline',exact:true}).click();await expect(page.getByRole('dialog',{name:'Course outline',exact:true})).toBeVisible();await screenshot('course-mobile-outline');await page.keyboard.press('Escape');await expect(page.getByRole('dialog',{name:'Course outline',exact:true})).toHaveCount(0);
 await page.evaluate(()=>localStorage.setItem('madar.language','ar'));await page.goto(origin+base);await expect(page.locator('.academy')).toHaveAttribute('dir','rtl');expect(await page.locator('.academy').evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);await screenshot('home-rtl-mobile');await page.goto(origin+`${base}/courses/${paid.id}`);await expect(page.locator('.academy')).toHaveAttribute('dir','rtl');expect(await page.locator('.academy').evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);await screenshot('details-rtl-mobile');
 expect(errors).toEqual([]);fs.writeFileSync(out+'/browser-results.json',JSON.stringify({routes:{home:base,catalog:`${base}/courses`,paid:`${base}/courses/${paid.id}`,player:`/my-learning/courses/${free.id}/lessons/${free.lessons[0].id}`,plans:'/my-learning/plans',certificates:'/my-learning/certificates'},free:free.id,paid:paid.id,private:privateCourse.id,checks:'normal management navigation → Edit → existing Builder → Preview → Go Live; backend component allowlist; isolated guest projection; management hub; direct visual Builder composition add/remove/reorder/Inspector and saved refresh; owner opens actual student shell with Back to Admin; free/selected-plan continuation after real sign-in; $20 local checkout; lifetime entitlement; shared completion persistence; certificates; accessible mobile course drawer; tablet/mobile/RTL without overflow',errors},null,2));await guest.close();console.log('Academy browser verification passed.');
 } catch(error) { await page.screenshot({path:out+"/failure.png",fullPage:true}); console.error("Visible page:",await page.locator("body").innerText()); console.error("Page errors:",errors); throw error; } finally { try { await captureCheckouts(); } catch {} if(settings)await api('/elearning/settings',settings,'PUT');manifest();await browser.close(); }
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
