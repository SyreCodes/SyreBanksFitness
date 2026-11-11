import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const localEnvPath = resolve(process.cwd(), '../../.env');
const localEnv = existsSync(localEnvPath)
  ? Object.fromEntries(readFileSync(localEnvPath, 'utf8').split('\n').filter(line => line.includes('=') && !line.startsWith('#')).map(line => { const index = line.indexOf('='); return [line.slice(0, index), line.slice(index + 1)]; }))
  : {};
async function login(page:Page, role:'admin'|'client') {
  const passwordKey = role === 'admin' ? 'SEED_ADMIN_PASSWORD' : 'SEED_CLIENT_PASSWORD';
  const password = process.env[passwordKey] || localEnv[passwordKey];
  if (!password) throw new Error(`Set ${passwordKey} in the environment or the local .env before running browser tests.`);
  await page.goto('/login');
  await page.getByLabel('Email address',{exact:true}).fill(`${role}@syrebanksfitness.local`);
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Log in to your account',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(role==='admin'?'/admin$':'/app$'));
}
test('public application persists and appears in the coach CRM', async ({page})=>{
  const applicant=`Acceptance ${Date.now()}`;
  await page.goto('/apply');
  await page.getByRole('button',{name:'Build Muscle',exact:true}).click();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Gym',exact:true}).click();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Monday',exact:true}).click();
  await page.getByLabel('What makes consistency difficult? (optional)').fill('Consistency with a busy schedule');
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('Your name',{exact:true}).fill(applicant);
  await page.getByLabel('Email address',{exact:true}).fill(`acceptance.${Date.now()}@example.com`);
  await page.getByLabel('Phone (optional)').fill('+250780000000');
  await page.getByRole('checkbox').check();
  await page.getByRole('button',{name:'Request enrollment',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Your next chapter starts with a conversation.'})).toBeVisible();
  await login(page,'admin');await page.goto('/admin/leads');await page.getByRole('textbox',{name:'Search applications'}).fill(applicant);await expect(page.getByRole('heading',{name:applicant,exact:true})).toBeVisible();
});
test('coach workspace loads all connected modules and saves CMS content',async({page})=>{
  await login(page,'admin');await expect(page.getByRole('heading',{name:/Good (morning|afternoon|evening)/})).toBeVisible();await page.screenshot({path:'/tmp/sbf-dashboard-desktop.png',fullPage:true});
  for(const path of ['clients','programs','exercises','checkins','messages','formchecks','calendar','payments','content','launch','feedback','users','settings','audit']){
    await page.goto(`/admin/${path}`);await expect(page.getByRole('heading',{level:1})).toBeVisible();await expect(page.getByText('We couldn’t load this.',{exact:true})).toHaveCount(0);
  }
  await page.goto('/admin/users');await page.getByRole('textbox',{name:'Search users'}).fill('admin@syrebanksfitness.local');await page.getByRole('button',{name:'Search',exact:true}).click();await expect(page.getByText('admin@syrebanksfitness.local')).toBeVisible();await page.screenshot({path:'/tmp/sbf-admin-users-desktop.png',fullPage:true});await page.getByRole('button',{name:'Review access'}).click();await expect(page.getByRole('heading',{name:'Account history'})).toBeVisible();await page.getByRole('button',{name:'Close dialog'}).click();
  await page.goto('/admin/content');const caption=page.getByLabel('Image caption',{exact:true});await expect(caption).toBeVisible();const original=await caption.inputValue();await caption.fill(original);await page.getByRole('button',{name:'Save content',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'Public content updated.'})).toBeVisible();
  await page.setViewportSize({width:390,height:844});await page.goto('/admin');await expect(page.getByRole('heading',{name:/Good (morning|afternoon|evening)/})).toBeVisible();await page.screenshot({path:'/tmp/sbf-dashboard-mobile.png',fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
test('client can log weight, submit check-in, message coach and save workout',async({page})=>{
  await login(page,'client');await page.screenshot({path:'/tmp/sbf-client-desktop.png',fullPage:true});
  await page.goto('/app/progress');await page.getByLabel('Weight (kg)',{exact:true}).fill('77.4');await page.getByRole('button',{name:'Save measurement',exact:true}).click();await expect(page.getByText('Your measurement is saved.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Open my private photos'}).click();await page.getByLabel('Caption (optional)',{exact:true}).fill('Private acceptance photo');await page.getByLabel('Photo',{exact:true}).setInputFiles(resolve(process.cwd(),'public/images/training-illustration.jpg'));await page.getByRole('button',{name:'Save private photo'}).click();await expect(page.getByText('Your photo is saved privately.')).toBeVisible();const privatePhoto=page.getByAltText('Private acceptance photo').first();await expect(privatePhoto).toBeVisible();const privatePath=(await privatePhoto.getAttribute('src'))!.split('?')[0];const anonymous=await page.context().browser()!.newContext({baseURL:process.env.PLAYWRIGHT_BASE_URL||'http://127.0.0.1:5173'});expect((await anonymous.request.get(privatePath)).status()).toBe(401);await anonymous.close();
  await page.goto('/app/checkins');await page.getByLabel('What went well?',{exact:true}).fill('Acceptance test: stayed consistent.');await page.getByRole('button',{name:'Send check-in',exact:true}).click();await expect(page.getByText('Your check-in is saved and ready for your coach to review.',{exact:true})).toBeVisible();
  await page.goto('/app/messages');const note=`Acceptance message ${Date.now()}`;await page.getByLabel('Your message',{exact:true}).fill(note);await page.getByRole('button',{name:'Send message',exact:true}).click();await expect(page.getByText(note,{exact:true})).toBeVisible();
  await page.goto('/app/workouts');await page.getByRole('button',{name:'Start session',exact:true}).first().click();const reps=page.getByRole('spinbutton',{name:/set 1 repetitions/}).first();await reps.fill('10');await page.getByRole('button',{name:/^Log .* set 1$/}).first().click();await page.getByRole('button',{name:'Finish & save session',exact:true}).click();await expect(page.getByText('Session complete. Good work.',{exact:true})).toBeVisible();
  await page.reload();await expect(page.getByText('Let’s get you back on track.')).toHaveCount(0);
});
test('client session booking and role boundaries are enforced',async({page})=>{
  await login(page,'client');
  const browserErrors:string[]=[];page.on('pageerror',error=>browserErrors.push(error.message));page.on('console',message=>{if(message.type()==='error')browserErrors.push(message.text())});
  await page.goto('/app/bookings');
  await expect(page.getByRole('button',{name:'Month',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Next period'}).click();
  await expect(page.getByRole('gridcell',{name:/[1-9]\d* available/}).first()).toBeVisible();
  await page.getByRole('gridcell',{name:/[1-9]\d* available/}).first().click();
  await page.locator('.booking-day-agenda button.booking-calendar-event.state-available').first().click();
  await expect(page.getByRole('heading',{name:'Book session'})).toBeVisible();
  await page.getByRole('button',{name:'Book session',exact:true}).click();
  await expect(page.getByText(/Session booked successfully/)).toBeVisible();
  await expect(page.locator('.booking-calendar-event.state-mine').first()).toBeVisible();
  await page.screenshot({path:'/tmp/sbf-calendar-client-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.locator('.booking-month')).toBeVisible();
  await expect(page.locator('.booking-day-agenda')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'/tmp/sbf-calendar-client-mobile.png',fullPage:true});
  await page.goto('/app');await expect(page.getByRole('heading',{name:'Your next session'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Coaching session'}).first()).toBeVisible();
  expect(browserErrors).toEqual([]);
  await page.goto('/admin');await expect(page.getByRole('alert')).toContainText('reserved for your coach');
});

test('admin uploads and replaces an exercise demonstration across reloads',async({page})=>{
  const exerciseName=`Acceptance movement ${Date.now()}`;
  await login(page,'admin');
  const browserErrors:string[]=[];page.on('pageerror',error=>browserErrors.push(error.message));page.on('console',message=>{if(message.type()==='error')browserErrors.push(message.text())});
  await page.goto('/admin/exercises');
  await page.getByRole('button',{name:'Add exercise',exact:true}).click();
  await page.getByLabel('Exercise name').fill(exerciseName);
  await page.getByLabel('Muscle group').fill('Legs');
  await page.getByLabel('Instructions').fill('Move with control.');
  await page.getByLabel('Demonstration video (optional)').setInputFiles(resolve(process.cwd(),'e2e/fixtures/exercise-demo.mp4'));
  await page.getByRole('button',{name:'Add exercise',exact:true}).last().click();
  await expect(page.getByRole('dialog').getByRole('heading',{name:exerciseName})).toBeVisible();
  const player=page.getByLabel(`${exerciseName} demonstration video`);
  await expect(player).toBeVisible();
  const original=await player.getAttribute('src');
  expect(original).toContain('/media/');
  expect((await page.request.get(original!)).ok()).toBe(true);

  await page.reload();
  await page.getByLabel('Search exercises').fill(exerciseName);
  await page.locator('.resource-card').filter({hasText:exerciseName}).getByRole('button',{name:'View movement'}).click();
  expect((await page.getByLabel(`${exerciseName} demonstration video`).getAttribute('src'))?.split('?')[0]).toBe(original?.split('?')[0]);
  await page.getByRole('button',{name:'Edit exercise or video'}).click();
  await page.getByLabel('Demonstration video (optional)').setInputFiles(resolve(process.cwd(),'e2e/fixtures/exercise-replacement.mp4'));
  await page.getByRole('button',{name:'Save exercise',exact:true}).click();
  await expect(page.getByRole('dialog').getByRole('heading',{name:exerciseName})).toBeVisible();
  const replacement=await page.getByLabel(`${exerciseName} demonstration video`).getAttribute('src');
  expect(replacement).toContain('/media/');
  expect(replacement).not.toBe(original);
  expect((await page.request.get(replacement!)).ok()).toBe(true);
  await page.reload();
  await page.getByLabel('Search exercises').fill(exerciseName);
  await page.locator('.resource-card').filter({hasText:exerciseName}).getByRole('button',{name:'View movement'}).click();
  expect((await page.getByLabel(`${exerciseName} demonstration video`).getAttribute('src'))?.split('?')[0]).toBe(replacement?.split('?')[0]);
  expect(browserErrors).toEqual([]);
});
test('public home and client portal fit a mobile viewport',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');await expect(page.getByRole('heading',{level:1})).toBeVisible();await expect.poll(()=>page.locator('.sb-hero-image').evaluate((node)=>{const image=node as HTMLImageElement;return image.complete&&image.naturalWidth>0;})).toBe(true);await page.screenshot({path:'/tmp/sbf-home-mobile.png',fullPage:false});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await login(page,'client');await expect(page.getByRole('button',{name:'Open navigation',exact:true})).toBeVisible();await page.screenshot({path:'/tmp/sbf-client-mobile.png',fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.getByRole('button',{name:'Open navigation',exact:true}).click();await expect(page.getByRole('link',{name:'My workouts',exact:true})).toBeVisible();
});
test('public pricing reflects editable products and payment state is truthful',async({page})=>{
  const response=await page.request.get('/api/v1/products');expect(response.ok()).toBe(true);
  const products=(await response.json() as {items:{id:string;name:string;currency:string;price_minor:number;billing_interval:string}[]}).items;
  await page.goto('/pricing');
  for(const product of products){
    await page.getByLabel('Show prices in').selectOption(product.currency);
    const exponent=new Intl.NumberFormat('en',{style:'currency',currency:product.currency}).resolvedOptions().maximumFractionDigits;
    const divisor=10**exponent;
    const amount=new Intl.NumberFormat('en',{style:'currency',currency:product.currency,maximumFractionDigits:product.currency==='RWF'?0:2}).format(product.price_minor/divisor);
    const article=page.locator('.package-tile').filter({has:page.locator(`a[href*="product=${product.id}"]`)});
    await expect(article.locator('.launch-price')).toContainText(amount);
    await expect(article.locator('.launch-price')).toContainText(product.billing_interval==='monthly'?'per month':product.billing_interval==='annual'?'per year':'one-time');
  }
  await page.goto('/');await expect.poll(()=>page.locator('.sb-hero-image').evaluate((node)=>{const image=node as HTMLImageElement;return image.complete&&image.naturalWidth>0;})).toBe(true);await page.screenshot({path:'/tmp/sbf-home-desktop.png',fullPage:false});
  await login(page,'client');await page.goto('/app/billing');await expect(page.getByRole('button',{name:'Payments unavailable'}).first()).toBeDisabled();await expect(page.getByText(/genuine payment/)).toBeVisible();
});
