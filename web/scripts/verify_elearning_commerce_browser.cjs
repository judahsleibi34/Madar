// Local-only scenario: run_local.py --local-db --local-commerce and Vite 5173.
// Uses the existing local account; writes exact fixture IDs for guarded cleanup.
const {chromium,expect}=require('../frontend/node_modules/@playwright/test');
const fs=require('node:fs');
const fixtures=require(process.env.MADAR_COMMERCE_ACCOUNT_FIXTURE || '/tmp/madar-player-media.json');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 const origin='http://127.0.0.1:5173',created={courses:[],plans:[],checkouts:[],groups:[],tenant_id:fixtures.tenant_id,user_id:fixtures.user_id},errors=[];let settings;
 page.on('pageerror',e=>errors.push(e.message));await page.addInitScript(()=>localStorage.setItem('madar.language','en'));
 const manifest=()=>fs.writeFileSync('/tmp/madar-commerce-browser-fixtures.json',JSON.stringify(created,null,2));
 async function raw(path,data,method='GET'){const cookies=await context.cookies();return context.request.fetch(origin+'/api'+path,{method,headers:{Origin:origin,'X-CSRF-Token':cookies.find(c=>c.name==='madar_csrf_token')?.value||''},...(data?{data}:{})});}
 async function api(path,data,method='GET'){const r=await raw(path,data,method);if(!r.ok())throw Error(method+' '+path+' '+r.status()+' '+await r.text());return r.json();}
 const card=name=>typeof name==='object'?page.locator(`.elearning-plan-card[data-course-id="${name.id}"]`):page.locator('.elearning-plan-card').filter({has:page.getByRole('heading',{name,exact:true})});
 async function screenshot(name){await page.screenshot({path:'/tmp/madar-commerce-'+name+'.png',fullPage:true});}
 async function account(){return api('/elearning/my-plans');}
 async function capture(){created.checkouts=(await account()).checkouts.filter(ch=>created.plans.includes(ch.offering_id)).map(ch=>ch.id);manifest();}
 async function createPlan(name,amount,billing,scope,courses=[]){
  await page.getByRole('button',{name:'Add Plan',exact:true}).click();const d=page.getByRole('dialog');
  await d.getByLabel('Plan Name',{exact:true}).fill(name);await d.getByLabel('Price',{exact:true}).fill(amount);
  await d.getByLabel('Access Scope',{exact:true}).selectOption(scope);expect(await d.getByLabel('Billing Type',{exact:true}).inputValue()).toBe('one_time');
  await d.getByLabel('Billing Type',{exact:true}).selectOption(billing);expect(await d.getByLabel('Access Scope',{exact:true}).inputValue()).toBe(scope);
  for(const course of courses)await d.locator(`input[name="plan-course"][value="${course.id}"]`).check();await d.getByLabel('Sale Availability',{exact:true}).selectOption('active');
  await d.getByRole('button',{name:'Save',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);await expect(card(name)).toBeVisible();
  const plan=(await api('/elearning/plans')).plans.find(p=>p.name===name && !created.plans.includes(p.id));created.plans.push(plan.id);manifest();return plan;
 }
 async function standaloneBuy(plan){
  await page.locator('#dashboard-sidebar-elearning').getByRole('link',{name:'Course Catalog',exact:true}).click();await page.getByRole('button',{name:'Browse Access Plans',exact:true}).click();
  await page.locator('.elearning-plan-option').filter({has:page.getByRole('heading',{name:plan.name,exact:true})}).getByRole('button',{name:'Buy',exact:true}).click();
  await expect(page.getByRole('button',{name:'Confirm Test Payment',exact:true})).toBeVisible();await capture();await page.getByRole('button',{name:'Confirm Test Payment',exact:true}).click();await expect(page.getByRole('heading',{name:/^Checkout:/})).toHaveCount(0);
  return (await account()).checkouts.find(ch=>ch.offering_id===plan.id);
 }
 try{
  await page.goto(origin+'/dashboard');await expect(page.getByRole('button',{name:'E-Learning',exact:true})).toBeVisible();
  settings=(await api('/elearning/settings')).settings;
  expect((await api('/elearning/catalog')).local_adapter).toBe(true);
  for(const [name,access] of [['English Communication','paid'],['Digital Marketing','paid'],['Leadership Fundamentals','paid'],['Unrelated Commerce Course','paid'],['Private Commerce Course','private'],['Free Commerce Course','free']]){
   const course=(await api('/elearning/courses',{name,description:'Local commerce verification',status:'published',access_type:access},'POST')).course;created.courses.push(course.id);manifest();
   let s=await api(`/elearning/courses/${course.id}/structure/commands`,{action:'create_section',expected_revision:1,payload:{name:'Foundations',status:'published'}},'POST');
   s=await api(`/elearning/courses/${course.id}/structure/commands`,{action:'create_lesson',expected_revision:s.revision,payload:{name:'Welcome',section_id:s.sections[0].id,status:'published'}},'POST');
   course.lesson=s.sections[0].lessons[0].id;
   await api(`/elearning/courses/${course.id}/lessons/${course.lesson}/content/commands`,{action:'create',expected_revision:1,payload:{type:'text',title:'Welcome',content:{body:'Purchased learning uses the existing player.'}}},'POST');
   created[name]=course;manifest();
  }
  const english=created['English Communication'],digital=created['Digital Marketing'],leadership=created['Leadership Fundamentals'],privateCourse=created['Private Commerce Course'],unrelated=created['Unrelated Commerce Course'],free=created['Free Commerce Course'];
  await page.getByRole('button',{name:'E-Learning',exact:true}).click();await page.locator('#dashboard-sidebar-elearning').getByRole('link',{name:'Settings',exact:true}).click();await page.getByRole('link',{name:'Plans / Pricing',exact:true}).click();
  const single=await createPlan('English Communication Access','20.00','one_time','single_course',[english]);
  const lifetime=await createPlan('Lifetime All Access','49.00','one_time','all_courses');
  const monthly=await createPlan('Monthly All Access','49.00','monthly','all_courses');
  const bundle=await createPlan('Starter Bundle','35.00','one_time','selected_courses',[english,digital,leadership]);
  await page.reload();await expect(card('Starter Bundle')).toContainText('35');await screenshot('plans');console.log('Admin pricing route:',page.url());
  await page.locator('#dashboard-sidebar-elearning').getByRole('link',{name:'Course Catalog',exact:true}).click();await expect(card(english)).toBeVisible();await expect(card(privateCourse)).toHaveCount(0);
  await card(english).getByRole('button',{name:'View Plans / Buy',exact:true}).click();await expect(page.locator('.elearning-plan-option')).toHaveCount(4);
  await page.locator('.elearning-plan-option').filter({has:page.getByRole('heading',{name:single.name,exact:true})}).getByRole('button',{name:'Buy',exact:true}).click();await capture();
  let ch=(await account()).checkouts.find(c=>c.offering_id===single.id);expect((await raw('/elearning/checkout',{offering_id:single.id,idempotency_key:crypto.randomUUID(),amount:1},'POST')).status()).toBe(422);
  expect((await raw(`/elearning/catalog/${english.id}/enrollment`,null,'POST')).status()).toBe(403);
  await page.getByRole('button',{name:'Fail Test Payment',exact:true}).click();await expect(page.getByText('Payment failed. No paid access was granted.',{exact:true})).toBeVisible();expect((await account()).entitlements.some(e=>e.checkout_id===ch.id)).toBe(false);await screenshot('failed');
  await page.getByRole('button',{name:'Confirm Test Payment',exact:true}).click();await expect(page.getByRole('heading',{name:english.name,exact:true,level:1})).toBeVisible();
  await page.getByRole('link',{name:'Welcome',exact:true}).click();await expect(page.getByText('Purchased learning uses the existing player.',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Mark Complete',exact:true}).click();await expect(page.getByText(/^Course Completed/)).toBeVisible();await screenshot('learning');
  const firstCompletion=(await api(`/elearning/my-learning/courses/${english.id}`)).progress.completion.completed_at;
  let learning=(await api('/elearning/my-learning')).courses;expect(learning.some(c=>c.course.id===english.id)).toBe(true);
  const lifetimeCheckout=await standaloneBuy(lifetime);expect(lifetimeCheckout.requested_resource_id).toBe(null);
  let ent=(await account()).entitlements.find(e=>e.checkout_id===lifetimeCheckout.id);expect(ent.expires_at).toBe(null);
  learning=(await api('/elearning/my-learning')).courses;expect(learning.some(c=>c.course.id===digital.id)).toBe(false);await expect(card(digital)).toContainText('Included in Lifetime All Access');await screenshot('included');
  const paymentCount=(await account()).checkouts.length;await card(digital).getByRole('button',{name:/^Enroll in /}).click();await expect(page.getByRole('heading',{name:digital.name,exact:true,level:1})).toBeVisible();expect((await account()).checkouts.length).toBe(paymentCount);
  await page.getByRole('link',{name:'Welcome',exact:true}).click();await page.getByRole('button',{name:'Mark Complete',exact:true}).click();await expect(page.getByText(/^Course Completed/)).toBeVisible();const digitalCompletion=(await api(`/elearning/my-learning/courses/${digital.id}`)).progress.completion.completed_at;
  // Isolate recurring access after proving lifetime terms. Supported reversal
  // removes only its entitlement, retaining both enrollment and completion.
  await api(`/elearning/checkout/${lifetimeCheckout.id}/local-event`,{state:'refunded'},'POST');
  const monthlyCheckout=await standaloneBuy(monthly);
  await page.locator('#dashboard-sidebar-elearning').getByRole('link',{name:'My Plans',exact:true}).click();await expect(card(monthly.name)).toContainText('Monthly');await screenshot('purchases');console.log('Learner purchases route:',page.url());
  await card(monthly.name).getByRole('button',{name:'Test Subscription Expiry',exact:true}).click();await expect(card(monthly.name)).toContainText('Expired');expect((await raw(`/elearning/my-learning/courses/${digital.id}`)).status()).toBe(404);
  await card(monthly.name).getByRole('button',{name:'Test Subscription Reactivation',exact:true}).click();await expect(card(monthly.name)).toContainText('Active');expect((await api(`/elearning/my-learning/courses/${digital.id}`)).progress.completion.completed_at).toBe(digitalCompletion);
  const enrollment=(await api(`/elearning/courses/${digital.id}/enrollments`)).enrollments.find(e=>e.user_id===fixtures.user_id);
  await api(`/elearning/courses/${digital.id}/enrollments/${enrollment.id}/status`,{action:'suspend',expected_status:'active',confirmed:true},'POST');expect((await raw(`/elearning/my-learning/courses/${digital.id}`)).status()).toBe(404);await api(`/elearning/courses/${digital.id}/enrollments/${enrollment.id}/status`,{action:'reactivate',expected_status:'suspended'},'POST');
  const group=(await api('/elearning/groups',{name:'Commerce Verification '+Date.now(),status:'active'},'POST')).item;created.groups.push(group.id);manifest();
  await api(`/elearning/relationships/group/${group.id}/commands`,{action:'add_members',user_ids:[fixtures.user_id]},'POST');await api(`/elearning/relationships/group/${group.id}/commands`,{action:'assign_course',target_id:digital.id},'POST');
  await api(`/elearning/checkout/${monthlyCheckout.id}/local-event`,{state:'expired'},'POST');expect((await api(`/elearning/my-learning/courses/${digital.id}`)).progress.completion.completed_at).toBe(digitalCompletion);
  await api(`/elearning/checkout/${monthlyCheckout.id}/local-event`,{state:'active'},'POST');await api(`/elearning/relationships/group/${group.id}/commands`,{action:'remove_member',user_ids:[fixtures.user_id],confirmed:true},'POST');expect((await api(`/elearning/my-learning/courses/${digital.id}`)).progress.completion.completed_at).toBe(digitalCompletion);
  await api(`/elearning/courses/${english.id}/enrollments/users`,{user_ids:[fixtures.user_id],access_source:'manual'},'POST');await api(`/elearning/checkout/${ch.id}/local-event`,{state:'refunded'},'POST');await api(`/elearning/checkout/${monthlyCheckout.id}/local-event`,{state:'refunded'},'POST');expect((await api(`/elearning/my-learning/courses/${english.id}`)).progress.completion.completed_at).toBe(firstCompletion);
  await standaloneBuy(bundle);let catalog=(await api('/elearning/catalog')).courses;
  expect(catalog.find(c=>c.id===leadership.id).cta.action).toBe('enroll');expect(catalog.find(c=>c.id===unrelated.id).cta.action).toBe('buy');expect(catalog.some(c=>c.id===privateCourse.id)).toBe(false);
  await card(free).getByRole('button',{name:'Enroll Free',exact:true}).click();await expect(page.getByRole('heading',{name:free.name,exact:true,level:1})).toBeVisible();
  await page.locator('#dashboard-sidebar-elearning').getByRole('link',{name:'Course Catalog',exact:true}).click();await page.reload();await expect(card(leadership)).toContainText('Included in Starter Bundle');console.log('Learner catalog route:',page.url());await screenshot('catalog');
  const rtl=await context.newPage();await rtl.addInitScript(()=>localStorage.setItem('madar.language','ar'));await rtl.setViewportSize({width:390,height:844});await rtl.goto(origin+'/my-learning/catalog');await expect(rtl.locator('.elearning-player')).toHaveAttribute('dir','rtl');await expect(rtl.getByRole('heading',{name:'كتالوج الدورات',exact:true})).toBeVisible();expect(await rtl.locator('.elearning-player').evaluate(e=>e.scrollWidth>e.clientWidth+1)).toBe(false);await rtl.screenshot({path:'/tmp/madar-commerce-rtl-mobile.png',fullPage:true});await rtl.close();
  expect(errors).toEqual([]);console.log('PASS: four independent plans; failed checkout; confirmed single purchase and learning; lifetime All Access without bulk enrollment; no-charge enrollment; recurring expiry/reactivation; preserved completion; Bundle scope; Private exclusion; Manual/Group independence; suspension; free enrollment; refresh; mobile Arabic RTL.');
 } catch(e){console.log('Failure route:',page.url(),await page.locator('[role=alert]').allTextContents());await screenshot('error');throw e;}
 finally{
  await capture();if(settings)await api('/elearning/settings',settings,'PUT');manifest();await browser.close();
  console.log('Exact fixture IDs saved for guarded local-only Commerce ledger/course cleanup.');
 }
})().catch(e=>{console.error(e.stack);process.exitCode=1});
