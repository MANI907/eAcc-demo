"""UI acceptance check. Creates one DEMO voucher in the running local workspace."""
import json,time,os
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=os.environ.get('EACC_TEST_BASE_URL','http://127.0.0.1:8000')
ACCESS=os.environ.get('EACC_TEST_ACCESS_CODE','')
OUT=Path(__file__).resolve().parents[1]/'.runtime';OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':1512,'height':982});page=context.new_page();errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto(BASE);page.locator('#access-code').fill(ACCESS);page.get_by_role('button',name='일반 사용자').click();page.wait_for_selector('.stats')
 bootstrap=page.request.get(BASE+'/api/bootstrap').json()
 source=next((t for t in bootstrap['transactions'] if not t['locked'] and not any(d.get('source_id')==t['id'] for d in bootstrap['documents'])),None)
 assert source,'No unprocessed local demo transaction remains'
 page.locator('aside [data-page="UD_0201_000"]').click()
 page.locator('[data-select="'+source['id']+'"]').check()
 page.get_by_role('button',name='선택내역 전표 작성').click()
 page.wait_for_selector('#voucher-form');page.locator('input[name="title"]').fill('브라우저 검증 · '+source['merchant'])
 page.get_by_role('button',name='전표 저장',exact=True).click();page.wait_for_selector('.document-heading')
 document_id=page.locator('.document-heading .mono').inner_text()
 page.get_by_role('button',name='결재 상신',exact=True).click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='결재중'")
 page.get_by_role('button',name='닫기',exact=True).click()
 def switch_role(name):
  page.locator('.profile').click();page.get_by_role('button',name='다른 역할로 접속').click();page.locator('#access-code').fill(ACCESS);page.get_by_role('button',name=name).click();page.wait_for_selector('.stats')
 switch_role('결재자')
 page.locator('aside [data-section="결재관리"]').click();page.locator('aside [data-page="UD_0302_000"]').click()
 page.locator(f'[data-action="view-doc"][data-id="{document_id}"]').first.click();page.get_by_role('button',name='결재 승인',exact=True).click()
 page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='승인완료'");page.get_by_role('button',name='닫기',exact=True).click()
 switch_role('회계 관리자')
 page.locator('aside [data-page="UD_0302_000"]').click();page.locator(f'[data-action="view-doc"][data-id="{document_id}"]').first.click()
 page.get_by_role('button',name='SAP 모의전기').click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='전기완료'")
 assert 'SIM-' in page.locator('#modal').inner_text();page.get_by_role('button',name='닫기',exact=True).click()
 menus=page.request.get(BASE+'/api/bootstrap').json()['menus'];visited=[]
 for menu in menus:
  button=page.locator('aside [data-page="'+menu['id']+'"]')
  if not button.count():page.locator('aside [data-section="'+menu['section']+'"]').click()
  page.locator('aside [data-page="'+menu['id']+'"]').click();page.wait_for_selector('main .page-title')
  assert page.locator('main h1').inner_text()==menu['title'],menu['id'];visited.append(menu['id'])
 page.keyboard.press('F8');page.wait_for_selector('#modal[open]');assert 'ITO 디버그' in page.locator('#modal').inner_text();page.get_by_role('button',name='닫기',exact=True).click()
 page.locator('aside [data-page="integrations"]').click();page.get_by_role('button',name='SAP 연결 검사').click()
 page.wait_for_function("!document.querySelector('[data-action=\"sap-test\"]').disabled")
 assert '미실행' in page.locator('#sap-result').inner_text()
 page.locator('aside [data-page="dashboard"]').click();page.screenshot(path=str(OUT/'dashboard-admin.png'),full_page=True)
 switch_role('일반 사용자');page.screenshot(path=str(OUT/'dashboard.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844});page.reload();page.wait_for_selector('.stats')
 page.get_by_role('button',name='메뉴 펼치기').click();page.wait_for_selector('aside.mobile-open')
 if not page.locator('aside [data-page="UD_0201_000"]').count():page.locator('aside [data-section="전표작성"]').click()
 page.locator('aside [data-page="UD_0201_000"]').click();assert page.locator('main h1').inner_text()=='법인카드'
 page.screenshot(path=str(OUT/'mobile-card.png'),full_page=True)
 assert not errors,errors
 result=dict(status='passed',menus_visited=len(visited),document_id=document_id,flow='employee save/submit → manager approve → ITO simulated posting',mobile_navigation=True,ito_f8=True,page_errors=errors)
 (OUT/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False));browser.close()
