import asyncio, pathlib, json, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright
HERE=pathlib.Path(__file__).resolve().parents[1]
class Server(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads=True
server=Server(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(HERE)))
threading.Thread(target=server.serve_forever,daemon=True).start()
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  page=await browser.new_page(viewport={'width':1365,'height':1000},accept_downloads=True)
  errors=[]
  page.on('pageerror',lambda e: errors.append(str(e)))
  await page.set_content((HERE/'proof_lab.html').read_text(), wait_until='load')
  assert await page.title() == 'PROOF LAB | AI Agents That Prove Their Work | MONTREAL.AI'
  await page.click('#compare')
  assert await page.inner_text('#stat-diffs')=='3'
  assert await page.inner_text('#stat-left')=='2'
  await page.click('#wrongFixture')
  await page.click('#verify')
  assert 'CHECKS FAIL' in await page.inner_text('#claimStatus')
  await page.click('#referenceFixture')
  await page.click('#verify')
  assert 'CHECKS PASS' in await page.inner_text('#claimStatus')
  async with page.expect_download() as d:
   await page.click('#export')
  downloaded=await d.value
  output=HERE.parent/'06_QA'/'browser_receipt.json'
  await downloaded.save_as(str(output))
  js=json.loads(output.read_text())
  assert js['verification']['status']=='CHECKS_PASS'
  assert js['inputs']['sourceA'].startswith('sku,')
  await page.locator('#evidence').screenshot(path=str(HERE.parent/'06_QA'/'proof_lab_evidence_panel.png'))
  await page.screenshot(path=str(HERE.parent/'06_QA'/'proof_lab_desktop.png'),full_page=True)
  await page.set_viewport_size({'width':390,'height':844})
  await page.screenshot(path=str(HERE.parent/'06_QA'/'proof_lab_mobile.png'),full_page=True)
  assert await page.locator('#left').is_visible()
  assert not errors,errors
  print('PASS: Offline Chrome open, comparison, wrong-claim rejection, reference acceptance, evidence download, 390px viewport, no page errors.')
  await browser.close()
asyncio.run(main())
