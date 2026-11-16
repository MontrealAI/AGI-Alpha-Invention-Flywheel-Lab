import asyncio,json,pathlib
from playwright.async_api import async_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
STAGE=ROOT/'00_STAGE'/'output'/'ALPHA_GENESIS_MISSION_STUDIO.html'
QA=ROOT/'06_QA'
async def run():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  page=await browser.new_page(viewport={'width':1440,'height':900},accept_downloads=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.set_content(STAGE.read_text(),wait_until='load')
  await page.wait_for_selector('#choices .scenario')
  assert await page.locator('#choices .scenario').count()==3
  assert '2' in await page.locator('#baseline-stats').inner_text()
  assert 'SCRIPTED PREVIEW' in await page.locator('#agent-meta').inner_text()
  assert (await page.locator('#scenario-stats').inner_text()).count('8')>=1
  await page.click('[data-choice="combined"]')
  assert '8' in await page.locator('#scenario-stats').inner_text()
  await page.click('#show-evidence')
  assert '8 ready and 0 held' in await page.locator('#test-result').inner_text()
  async with page.expect_download() as req:await page.click('#download')
  download=await req.value; fn=QA/'stage_export.json';await download.save_as(str(fn))
  exported=json.loads(fn.read_text())
  assert exported['selected']['totals']['readyCount']==8
  await page.click('#show-lineage')
  assert await page.locator('#lineage .hash').count()==4
  await page.screenshot(path=str(QA/'stage_desktop.png'),full_page=True)
  await page.set_viewport_size({'width':390,'height':844});await page.screenshot(path=str(QA/'stage_mobile.png'),full_page=True)
  assert await page.locator('h1').is_visible()
  assert not errors, errors
  print('PASS: stage renders, 3 strategies selectable, combined scenario=8 hypothetical ready, evidence check, exported JSON, 4 source hashes, mobile, no JS errors')
  await browser.close()
asyncio.run(run())
