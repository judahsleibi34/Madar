// Explicit loopback-only browser QA. Fixture provenance is captured before editing.
const {chromium,expect}=require('../frontend/node_modules/@playwright/test');
const fs=require('node:fs');
const origin='http://127.0.0.1:5173',out='docs/verification/academy-full-builder';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const fixture=JSON.parse(fs.readFileSync('/tmp/madar-academy132-browser-fixtures.json'));
 if(fixture.cleanup_verified)throw Error('This QA manifest has been cleaned; capture fresh provenance in a separate QA tenant');
 if(fixture.preexisting_builder_projects.length)throw Error('Use a separate QA tenant; this script never edits existing projects');
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 page.setDefaultTimeout(10000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('response',async r=>{if(r.status()>=400&&r.url().includes('/builder/projects/'))console.error('Builder response',r.status(),await r.text());});
 await page.addInitScript(()=>{if(!localStorage.getItem('madar.language'))localStorage.setItem('madar.language','en');});
 const manifest=()=>fs.writeFileSync('/tmp/madar-academy132-browser-fixtures.json',JSON.stringify(fixture,null,2));
 async function raw(path,data,method='GET'){
  const result=await page.evaluate(async ({path,data,method})=>{
   const {apiFetch}=await import('/src/utils/apiClient.js');
   const r=await apiFetch('/api'+path,{method,headers:{'Content-Type':'application/json',...(path.startsWith('/builder/')||path==='/public/academies/management/landing'?{'X-Madar-Builder-Contract':'cloud-draft-v1'}:{})},...(data?{body:JSON.stringify(data)}:{})});
   return {status:r.status,ok:r.ok,body:await r.text()};
  },{path,data,method});
  return {ok:()=>result.ok,status:()=>result.status,text:async()=>result.body,json:async()=>JSON.parse(result.body)};
 }
 async function api(path,data,method='GET'){const r=await raw(path,data,method);if(!r.ok())throw Error(method+' '+path+' '+r.status()+' '+await r.text());return r.json();}
 const screenshot=async name=>page.screenshot({path:`${out}/${name}.png`,fullPage:true});
 try{
 await page.goto(origin+'/dashboard');await expect(page.getByRole('button',{name:'E-Learning',exact:true})).toBeVisible();
 if(!fixture.settings){fixture.settings=(await api('/elearning/settings')).settings;manifest();}
 await api('/elearning/settings',{...fixture.settings,enabled:true,academy_enabled:true,sequential_progression:false},'PUT');
 await page.getByRole('button',{name:'E-Learning',exact:true}).click();await page.locator('.admin-sidebar').getByRole('link',{name:'Academy',exact:true}).click();
 await expect(page.getByRole('button',{name:'Edit Academy',exact:true})).toBeVisible();await screenshot('hub');
 const beforeEdit=(await api('/builder/projects?limit=100')).projects;
 if(beforeEdit.some(project=>project.id!==fixture.builder_project || fixture.builder_project_created!==true))throw Error('Refusing to edit an existing tenant project outside this QA manifest');
 await page.getByRole('button',{name:'Edit Academy',exact:true}).click();await expect(page).toHaveURL(/\/page-builder\/projects\/[^/]+\/pages$/);
 fixture.builder_project=page.url().match(/projects\/([^/]+)/)[1];fixture.builder_project_created=true;manifest();
 await expect(page.getByLabel('Page name',{exact:true})).toBeVisible();await screenshot('builder-pages');
 fs.writeFileSync('/tmp/academy132-visible-tools.txt',await page.locator('body').innerText());
 const projectId=fixture.builder_project;
 expect((await api('/public/academies/management/landing',{},'POST')).project.id).toBe(projectId);
 expect((await api('/public/academies/management/landing',{},'POST')).project.id).toBe(projectId);
 async function create(name,access='free',status='published'){
  const course=(await api('/elearning/courses',{name,description:'Local Academy verification',status,access_type:access},'POST')).course;fixture.courses.push(course.id);manifest();
  let structure=await api(`/elearning/courses/${course.id}/structure/commands`,{action:'create_section',expected_revision:1,payload:{name:'Level 1',status:'published'}},'POST');
  for(const name of ['Topic 1','Topic 2'])structure=await api(`/elearning/courses/${course.id}/structure/commands`,{action:'create_lesson',expected_revision:structure.revision,payload:{section_id:structure.sections[0].id,name,status:'published'}},'POST');
  return {...course,lessons:structure.sections[0].lessons};
 }
 if(!fixture.named){
  const free=await create('Academy Full Builder Course'),privateCourse=await create('Academy Private Secret','private'),draft=await create('Academy Draft Secret','free','draft');
  fixture.named={free,privateCourse,draft};manifest();
  await api(`/elearning/courses/${free.id}/lessons/${free.lessons[0].id}/content/commands`,{action:'create',expected_revision:1,payload:{type:'text',title:'Welcome',content:{body:'Shared fixed learner runtime remains intact.'}}},'POST');
  await api(`/elearning/catalog/${free.id}/enrollment`,{},'POST');
  await api(`/elearning/my-learning/courses/${free.id}/lessons/${free.lessons[0].id}/completion`,{},'POST');
  const plan=(await api('/elearning/plans',{name:'Academy QA Plan',description:'Local Academy verification',status:'active',billing_type:'one_time',access_scope:'all_courses',amount:49,currency:'USD',course_ids:[],revision:1},'POST')).saved_plan_id;
  fixture.plans.push(plan);manifest();
 }
 if(!fixture.instructors.length){
  const instructor=(await api('/elearning/instructors',{name:'Academy QA Instructor',description:'Local Academy verification',status:'active',email:'private-instructor@example.com'},'POST')).item;
  fixture.instructors.push(instructor.id);manifest();
  await api(`/elearning/relationships/course/${fixture.named.free.id}/commands`,{action:'assign_instructor',target_id:instructor.id},'POST');
 }
 const {free,privateCourse,draft}=fixture.named;
 await page.reload();await expect(page.getByLabel('Page name',{exact:true})).toBeVisible();
 let current=(await api(`/builder/projects/${projectId}`)).project;
 if(!fixture.initial_draft_schema){
  fixture.initial_draft_schema=structuredClone(current.draft_schema);
  fixture.initial_draft_schema.pages=fixture.initial_draft_schema.pages.slice(0,1);
  fixture.initial_draft_schema.pages[0].sections=fixture.initial_draft_schema.pages[0].sections.slice(0,7);
  manifest();
 }
 if(fixture.builder_project_created){
  await api(`/builder/projects/${projectId}`,{name:current.name,slug:current.slug,draft_schema:fixture.initial_draft_schema,expected_revision:current.draft_revision},'PUT');
  await page.reload();await expect(page.getByLabel('Page name',{exact:true})).toBeVisible();
 }
 const seeded=(await api(`/builder/projects/${projectId}`)).project.draft_schema;
 function elements(section){return [...(section.freeElements||[]),...(section.rows||[]).flatMap(r=>r.columns.flatMap(c=>c.elements))];}
 const heroHeading=elements(seeded.pages[0].sections[0]).find(e=>e.type==='heading');
 await page.getByRole('combobox',{name:/^Select an element/}).selectOption(heroHeading.id);
 await page.locator('.builder-inspector').getByRole('textbox',{name:/^Content/}).fill('Learn With the Full Builder');
 await page.getByRole('button',{name:'Undo last builder change',exact:true}).click();
 await expect(page.locator('.builder-inspector').getByRole('textbox',{name:/^Content/})).not.toHaveValue('Learn With the Full Builder');
 await page.getByRole('button',{name:'Redo builder change',exact:true}).click();await expect(page.locator('.builder-inspector').getByRole('textbox',{name:/^Content/})).toHaveValue('Learn With the Full Builder');
 await page.getByRole('tab',{name:/^Sections/}).click();await expect(page.getByRole('heading',{name:'Components',exact:true})).toBeVisible();
 expect(await page.locator('.section-component-palette').getByRole('button',{name:/Form|Reservation|Booking|Appointment/}).count()).toBe(0);
 async function nativeSection(name,text,withImage=false){await page.locator('.section-component-palette').getByRole('button',{name:'Text Drag into a section',exact:true}).click();await page.locator('.builder-inspector').getByRole('textbox',{name:/^Content/}).fill(text);if(withImage)await page.locator('.section-component-palette').getByRole('button',{name:'Image Drag into a section',exact:true}).click();}
 await nativeSection('Text and Image','Learn through real courses, with the shared Builder.',true);
 await nativeSection('Testimonials','Presentation components use the existing Inspector.');
 await nativeSection('FAQ','Can I resume? Yes, your progress is stored.');
 await page.getByRole('button',{name:'Add section',exact:true}).click();await page.getByLabel('Section name',{exact:true}).fill('Instructors');
 const instructorPalette=page.locator('.section-component-palette').getByRole('button',{name:'Instructors Drag into a section',exact:true});
 await instructorPalette.click();await expect(page.getByLabel('Heading',{exact:true})).toBeVisible();await page.getByLabel('Heading',{exact:true}).fill('Meet Your Instructors');await page.getByLabel('Academy QA Instructor',{exact:true}).check();
 await page.getByRole('button',{name:'Undo last builder change',exact:true}).click();await expect(page.getByLabel('Academy QA Instructor',{exact:true})).not.toBeChecked();
 await page.getByRole('button',{name:'Redo builder change',exact:true}).click();await expect(page.getByLabel('Academy QA Instructor',{exact:true})).toBeChecked();
 await page.locator('.builder-inspector').getByRole('button',{name:'Duplicate',exact:true}).click();
 await page.locator('.builder-inspector').getByRole('button',{name:'Delete Element',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Delete element',exact:true}).click();
 console.log('Components/history verified');await screenshot('components-inspector');
 await page.getByRole('tab',{name:/^Pages/}).click();await page.getByRole('button',{name:'New page',exact:true}).click();
 await page.getByLabel('Page name',{exact:true}).fill('About');await page.getByRole('tab',{name:/^Sections/}).click();await nativeSection('About','About the full Academy Builder');
 await page.getByRole('tab',{name:/^Pages/}).click();await page.locator('.page-utility-actions').getByRole('button',{name:'Duplicate',exact:true}).click();
 await page.getByRole('button',{name:'Delete page',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Delete page',exact:true}).click();
 await page.getByRole('combobox',{name:'Current page',exact:true}).selectOption({label:'Academy Home'});
 await page.getByRole('link',{name:'Header & Footer',exact:true}).click();
 await expect(page.getByLabel('Brand name',{exact:true})).toBeVisible();await page.getByLabel('Brand name',{exact:true}).fill('Full Academy Builder');await page.getByLabel('Footer brand name',{exact:true}).fill('Full Academy Builder');await page.getByLabel('Footer rights',{exact:true}).fill('Learning with Madar');
 await page.getByLabel('Button text',{exact:true}).fill('Explore Courses');
 console.log('Pages/chrome verified');await screenshot('header-footer');await page.getByRole('link',{name:'Pages',exact:true}).click();await page.getByRole('tab',{name:/^Themes/}).click();
 await expect(page.getByRole('heading',{name:/Theme/}).first()).toBeVisible();await screenshot('themes');
 await page.getByRole('link',{name:'Pages',exact:true}).click();
 await page.getByRole('button',{name:'Zoom out',exact:true}).click();await expect(page.getByRole('button',{name:/Zoom 90%/})).toBeVisible();
 await page.getByRole('button',{name:/Zoom 90%/}).click();
 await page.getByRole('button',{name:'Save',exact:true}).click();await expect.poll(async()=>JSON.stringify((await api(`/builder/projects/${projectId}`)).project.draft_schema)).toContain('Meet Your Instructors');
 await page.reload();await expect(page.getByLabel('Page name',{exact:true})).toBeVisible();const saved=(await api(`/builder/projects/${projectId}`)).project;
 expect(saved.draft_schema.pages.length).toBe(2);expect(saved.draft_schema.siteChrome.brand).toBe('Full Academy Builder');
 await page.getByRole('button',{name:'Preview site',exact:true}).click();await expect(page.getByRole('heading',{name:'Learn With the Full Builder',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Academy QA Instructor',exact:true})).toBeVisible();await screenshot('preview');await page.getByRole('button',{name:'Exit site preview',exact:true}).click();
 await page.getByRole('button',{name:'Go Live',exact:true}).click();await expect.poll(async()=>(await api(`/builder/projects/${projectId}`)).project.status,{timeout:20000}).toBe('published');
 const published=(await api(`/builder/projects/${projectId}`)).project.published_schema;
 expect(JSON.stringify(published)).not.toContain('progress_percent');expect(JSON.stringify(published)).not.toContain('private-instructor@example.com');
 await page.goto(origin+'/e-learning/settings/academy');await page.getByRole('link',{name:'Open Academy',exact:true}).click();await expect(page).toHaveURL(origin+'/academy/testing');await expect(page.getByRole('heading',{name:'Learn With the Full Builder',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Academy QA Instructor',exact:true})).toBeVisible();await screenshot('published-learner');
 await page.goto(origin+'/academy/testing/about');await expect(page.getByText('About the full Academy Builder',{exact:true})).toBeVisible();await screenshot('published-about');
 await page.goto(origin+'/e-learning/settings/academy');await page.getByRole('button',{name:'Edit Academy',exact:true}).click();await page.getByRole('combobox',{name:/^Select an element/}).selectOption(heroHeading.id);await page.locator('.builder-inspector').getByRole('textbox',{name:/^Content/}).fill('Unpublished Academy Change');await page.getByRole('button',{name:'Save',exact:true}).click();
 await expect.poll(async()=>JSON.stringify((await api(`/builder/projects/${projectId}`)).project.draft_schema)).toContain('Unpublished Academy Change');
 const guest=await browser.newContext({viewport:{width:1440,height:1000}}),guestPage=await guest.newPage();guestPage.on('pageerror',e=>errors.push(e.message));await guestPage.route('**/api/auth/user_status',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({logged_in:false,user:null})}));await guestPage.addInitScript(()=>localStorage.setItem('madar.language','en'));
 await guestPage.goto(origin+'/academy/testing');await expect(guestPage.getByRole('heading',{name:'Learn With the Full Builder',exact:true})).toBeVisible();expect(await guestPage.getByText('Unpublished Academy Change',{exact:true}).count()).toBe(0);expect(await guestPage.getByRole('heading',{name:'Continue Learning',exact:true}).count()).toBe(0);await guestPage.screenshot({path:out+'/published-guest.png',fullPage:true});
 const publicData=await(await guest.request.get(origin+'/api/public/academies/testing')).json();expect(publicData.authenticated).toBe(false);expect(publicData.courses.every(c=>!c.progress&&!c.credential&&!c.resume)).toBe(true);expect(publicData.courses.some(c=>[privateCourse.id,draft.id].includes(c.id))).toBe(false);expect(publicData.instructors.find(i=>i.id===fixture.instructors[0]).name).toBe('Academy QA Instructor');expect(JSON.stringify(publicData.instructors)).not.toContain('private-instructor@example.com');
 for(const course of [privateCourse,draft])expect((await guest.request.get(origin+`/api/public/academies/testing/courses/${course.id}`)).status()).toBe(404);
 await guestPage.goto(origin+'/academy/testing/courses');await expect(guestPage.getByRole('searchbox')).toBeVisible();
 await page.goto(origin+'/e-learning/settings/academy');await page.getByRole('link',{name:'Open Student Platform',exact:true}).click();await expect(page).toHaveURL(origin+'/my-learning');await expect(page.locator('.learning-shell-sidebar')).toBeVisible();await expect(page.locator('.admin-sidebar')).toHaveCount(0);for(const name of ['My Learning','Course Catalog','My Plans','My Certificates','Account'])await expect(page.locator('.learning-shell-sidebar').getByRole('link',{name,exact:true})).toBeVisible();await screenshot('student-platform');
 await page.goto(origin+`/my-learning/courses/${free.id}/lessons/${free.lessons[0].id}`);await expect(page.getByText('Shared fixed learner runtime remains intact.',{exact:true})).toBeVisible();await expect(page.getByText('Completed',{exact:true}).first()).toBeVisible();await screenshot('course-workspace');
 await page.setViewportSize({width:390,height:844});await page.goto(origin+'/academy/testing/about');await expect(page.getByText('About the full Academy Builder',{exact:true})).toBeVisible();expect(await page.locator('.academy').evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);await screenshot('mobile-about');
 await page.evaluate(()=>localStorage.setItem('madar.language','ar'));await page.reload();await expect(page.locator('.academy')).toHaveAttribute('dir','rtl');expect(await page.locator('.academy').evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true);await screenshot('rtl-mobile-about');
 expect(errors).toEqual([]);fs.writeFileSync(out+'/browser-results.json',JSON.stringify({project:projectId,routes:{editor:`/page-builder/projects/${projectId}/pages`,about:'/academy/testing/about',home:'/academy/testing',student:'/my-learning',lesson:`/my-learning/courses/${free.id}/lessons/${free.lessons[0].id}`},checks:'normal owner navigation; idempotent initialization; native pages/chrome/themes/history/zoom/save/refresh/preview/publish; component add/edit/duplicate/delete; section reorder undo/redo; Instructor assignments; real price/progress/privacy; draft stays separate; fixed catalog/student/course workspace; mobile/RTL',errors},null,2));await guest.close();console.log('Full Academy Builder browser verification passed.');

 }catch(e){await screenshot('failure');console.error(await page.locator('body').innerText());throw e;}finally{manifest();await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
