"""Approval UI regressions: visible dialog errors, committed state and approver choice.
Uses an isolated SQLite DB and real local HTTP API. No deployed data is touched.
"""
import json,os,subprocess,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8022'
with tempfile.TemporaryDirectory(prefix='eacc-approvals-') as temporary:
 env=dict(os.environ,PORT='8022',HOST='127.0.0.1',EACC_DATA_DIR=temporary,DATABASE_URL='',SUPABASE_URL='',SUPABASE_SERVICE_ROLE_KEY='',EACC_PUBLIC_DEPLOYMENT='',EACC_ACCESS_CODE='')
 proc=subprocess.Popen([str(ROOT/'.runtime/venv/bin/python'),str(ROOT/'server.py')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(40):
   try:urllib.request.urlopen(BASE+'/api/health',timeout=1).close();break
   except Exception:time.sleep(.2)
  else:raise RuntimeError('Test server did not start.')
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(BASE);page.get_by_role('button',name='일반 사용자').click();page.wait_for_selector('.stats')
   def create(source,account):
    bootstrap=page.request.get(BASE+'/api/bootstrap').json();tx=next(x for x in bootstrap['transactions'] if x['id']==source)
    response=page.request.post(BASE+'/api/documents',data=dict(kind='card',source_id=source,title=tx['merchant'],date=bootstrap['today'],posting_date=bootstrap['today'],company='1000',cost_center='110370',wbs='ENERGY-2026-01',account=account,tax_code='EXEMPT',amount=tx['amount'],vat=0,lines=[dict(account=account,debit=tx['amount'],credit=0),dict(account='211100',debit=0,credit=tx['amount'])],vendor='V1000',attachments=[],approvers=[]));assert response.status==200,response.text();return response.json()['id']
   def show(id):
    page.reload();page.wait_for_selector('.stats');page.locator('aside [data-section="결재관리"]').click();page.locator('aside [data-page="UD_0302_000"]').click();page.locator(f'[data-action="view-doc"][data-id="{id}"]').first.click();page.wait_for_selector('.document-heading')
   id=create('TX-0001','610200');show(id)
   assert page.locator('[name="detail_approver"]').input_value()=='auto'
   path='**/api/documents/'+id+'/submit';message='상신 검증 오류: <img src=x onerror=alert(1)> 결재선을 확인하세요.'
   page.route(path,lambda route:route.fulfill(status=400,json={'error':message}))
   page.get_by_role('button',name='결재 상신',exact=True).click();notice=page.locator('#modal .dialog-notice.error');notice.wait_for();assert notice.locator('span').inner_text()==message
   assert notice.locator('img').count()==0;assert page.locator('#toast.visible').count()==0
   assert notice.evaluate('(el)=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}')
   page.wait_for_timeout(4200);assert notice.is_visible();page.screenshot(path=str(ROOT/'.runtime/approval-visible-error.png'),full_page=True);page.unroute(path)
   # A failed bootstrap must not turn a committed submit into an apparent failure.
   page.route('**/api/bootstrap',lambda route:route.fulfill(status=503,json={'error':'test bootstrap unavailable'}));posts=[]
   def submit(route):posts.append(route.request.url);time.sleep(.2);route.continue_()
   page.route(path,submit)
   page.locator('[data-action="submit"]').evaluate('(button)=>{button.click();button.click();}')
   page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='결재중'");assert len(posts)==1;assert page.locator('#modal .dialog-notice.success').is_visible();assert page.locator('#modal [data-action="submit"]').count()==0
   page.get_by_role('button',name='상태 다시 조회',exact=True).click();page.wait_for_function("document.querySelector('#modal .dialog-notice')?.textContent.includes('최신 전표 상태')");assert page.locator('#modal .badge').inner_text()=='결재중'
   page.unroute(path);page.unroute('**/api/bootstrap');page.get_by_role('button',name='닫기',exact=True).click()
   admin=p.request.new_context(base_url=BASE);admin.post('/api/login',data={'role':'ito'});assert admin.post('/api/settings',data={'auto_manager':False}).status==200
   second=create('TX-0006','610100');show(second);assert page.locator('[name="detail_approver"]').input_value()==''
   page.get_by_role('button',name='결재 상신',exact=True).click();assert '결재자를 선택' in page.locator('.dialog-notice.error').inner_text();assert page.locator('#modal .badge').inner_text()=='작성중'
   page.locator('[name="detail_approver"]').select_option('E1002');page.get_by_role('button',name='결재 상신',exact=True).click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='결재중'");assert '박서준' in page.locator('.detail-grid').inner_text()
   page.get_by_role('button',name='상신 회수',exact=True).click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='작성중'")
   page.get_by_role('button',name='결재 상신',exact=True).click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='결재중'")
   def switch(role):
    page.get_by_role('button',name='닫기',exact=True).click();page.locator('.profile').click();page.get_by_role('button',name='다른 역할로 접속').click();page.get_by_role('button',name=role,exact=False).click();page.wait_for_selector('.stats');show(second)
   switch('결재자');page.get_by_role('button',name='반려',exact=True).click();page.locator('#reject-form [name="reason"]').fill('증빙 검토 후 재상신 테스트');page.get_by_role('button',name='반려 처리',exact=True).click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='반려'")
   switch('일반 사용자');page.get_by_role('button',name='결재 상신',exact=True).click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='결재중'")
   switch('결재자');page.get_by_role('button',name='결재 승인',exact=True).click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='승인완료'")
   switch('회계 관리자');page.get_by_role('button',name='SAP 모의전기',exact=True).click();page.wait_for_function("document.querySelector('#modal .badge')?.textContent==='전기완료'");assert 'SIM-' in page.locator('.detail-grid').inner_text()
   # A slow document refresh must not reopen a dialog the user has closed.
   page.evaluate("""()=>{const original=window.fetch;window.fetch=async(...args)=>{const response=await original(...args);if(String(args[0]).includes('/api/documents/'))return new Promise(resolve=>{window.releaseDocumentRefresh=()=>resolve(response)});return response;};window.restoreFetch=()=>{window.fetch=original;};}""")
   page.get_by_role('button',name='상태 다시 조회',exact=True).click();page.wait_for_function("typeof window.releaseDocumentRefresh==='function'");page.get_by_role('button',name='닫기',exact=True).click();page.evaluate('window.releaseDocumentRefresh()');page.wait_for_function('pendingDocumentActions.size===0');assert not page.locator('#modal').is_visible();page.evaluate('window.restoreFetch()')
   assert not errors,errors;print(json.dumps(dict(status='passed',modal_error_visible=True,modal_error_persistent=True,error_text_escaped=True,submit_response_updates_state=True,no_duplicate_submit=True,single_document_refresh=True,explicit_approver_with_auto_off=True,withdraw_reject_resubmit_approve_simulate=True,closed_dialog_not_reopened=True,page_errors=errors),ensure_ascii=False));admin.dispose();browser.close()
 finally:proc.terminate();proc.wait(timeout=5)
