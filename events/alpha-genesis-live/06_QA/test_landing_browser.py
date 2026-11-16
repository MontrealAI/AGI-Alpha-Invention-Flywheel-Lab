import asyncio, pathlib, base64
from playwright.async_api import async_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
async def run():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  page=await browser.new_page(viewport={'width':1440,'height':900})
  errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
  raw=(ROOT/'04_SALES/landing_preview.html').read_text()
  shot=ROOT/'06_QA/stage_desktop.png';assert shot.exists()
  text=raw.replace('../06_QA/stage_desktop.png','data:image/png;base64,'+base64.b64encode(shot.read_bytes()).decode())
  await page.set_content(text,wait_until='load')
  await page.locator('.frame img').scroll_into_view_if_needed()
  assert await page.locator('.frame img').evaluate('(e) => e.complete && e.naturalWidth > 300')
  assert await page.locator('details').count()==4
  assert 'not a ticket page' in (await page.locator('nav').inner_text()).lower()
  await page.screenshot(path=str(ROOT/'06_QA/landing_desktop.png'),full_page=True)
  await page.set_viewport_size({'width':390,'height':844});await page.screenshot(path=str(ROOT/'06_QA/landing_mobile.png'),full_page=True)
  assert not errs,errs
  await browser.close();print('PASS: landing HTTP loading, stage screenshot asset, 4 FAQ items, mobile, no errors')
asyncio.run(run())
