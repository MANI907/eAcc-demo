"""Physical evidence UI regression. SQLite or LOCAL TLS PostgreSQL; Storage is a stub.
Run with system Python (Playwright). Optional EACC_EVIDENCE_TEST_DB_CONFIG points
at a generated local-only DB configuration. No deployed Supabase data is touched.
"""
import json,os,subprocess,tempfile,time,urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8021'
PNG=Path(os.environ.get('EACC_TEST_EVIDENCE_IMAGE','/workspace/generated_images/exec-ccffaeeb-2d74-490c-8765-be607e70eb54.png'))
if not PNG.is_file():raise SystemExit('Generated KTX PNG is required for this acceptance test.')
# Stub only the provider HTTP transport. DB, app, file validation and browser stay real.
WORKER="""
import server,blob_store,requests
class Response:
 def __init__(self,status,content=b''):self.status_code=status;self.content=content
 def json(self):return {}
files={}
def transport(method,url,headers,data=None,**kwargs):
 id=url.rsplit('/',1)[-1]
 if method=='POST':files[id]=data;return Response(200)
 if method=='GET':return Response(200,files[id]) if id in files else Response(404)
 if method=='DELETE':files.pop(id,None);return Response(200)
 raise RuntimeError('unexpected test method')
requests.request=transport
server.init()
server.ThreadingHTTPServer(('127.0.0.1',8021),server.Handler).serve_forever()
"""
with tempfile.TemporaryDirectory(prefix='eacc-evidence-') as temp:
 env=dict(os.environ,PORT='8021',HOST='127.0.0.1',EACC_DATA_DIR=temp,DATABASE_URL='',SUPABASE_URL='https://test-project.supabase.co',SUPABASE_SERVICE_ROLE_KEY='test-key',EACC_PUBLIC_DEPLOYMENT='',EACC_ACCESS_CODE='')
 cfg=os.environ.get('EACC_EVIDENCE_TEST_DB_CONFIG')
 if cfg:
  settings=json.loads(Path(cfg).read_text());parts=urlsplit(settings['DATABASE_URL'])
  if parts.hostname not in ['127.0.0.1','localhost'] or parts.path!='/eacc_test':raise SystemExit('Only the dedicated local test database is allowed.')
  env.update(settings)
 server=subprocess.Popen([str(ROOT/'.runtime/venv/bin/python'),'-c',WORKER],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(50):
   try:urllib.request.urlopen(BASE+'/api/health',timeout=1).close();break
   except Exception:time.sleep(.2)
  else:raise RuntimeError('Test server did not start.')
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(BASE);page.get_by_role('button',name='일반 사용자').click();page.wait_for_selector('.stats');page.locator('aside [data-page="UD_0202_001"]').click()
   def new():
    page.get_by_role('button',name='전표 작성',exact=True).click();page.locator('[name="title"]').fill('KTX 실물증빙 자동분개 검증');page.locator('[name="account"]').select_option('610200');page.locator('[name="amount"]').fill('59800')
   def attach():
    page.locator('#evidence').set_input_files(str(PNG));page.wait_for_selector('#attachment-list a');assert '업로드 완료' in page.locator('#upload-status').inner_text()
   new();assert page.locator('.line-debit').first.input_value()=='59800';attach();page.get_by_role('button',name='전표 저장',exact=True).click();page.wait_for_selector('.document-heading')
   id=page.locator('.document-heading .mono').inner_text();data=page.request.get(BASE+'/api/bootstrap').json();doc=next(d for d in data['documents'] if d['id']==id);assert doc['amount']==59800 and doc['lines'][0]['account']=='610200';assert doc['attachments']
   downloaded=page.request.get(BASE+'/api/files/'+doc['attachments'][0]);assert downloaded.status==200 and downloaded.body()==PNG.read_bytes();page.get_by_role('button',name='닫기',exact=True).click()
   # A successful save followed by failed refresh must not leave a second Save button.
   before=len(data['documents']);new();attach();page.route('**/api/bootstrap',lambda route:route.fulfill(status=503,json={'error':'저장소 연결을 확인하세요.'}))
   page.get_by_role('button',name='전표 저장',exact=True).click();page.wait_for_function("document.querySelector('#modal h2')?.textContent==='전표 저장 완료 · 화면 조회 실패'")
   assert page.get_by_role('button',name='전표 저장',exact=True).count()==0;assert '중복 작성하지 말고' in page.locator('#modal').inner_text();page.unroute('**/api/bootstrap')
   assert len(page.request.get(BASE+'/api/bootstrap').json()['documents'])==before+1;page.get_by_role('button',name='다시 조회',exact=True).click();page.wait_for_selector('.document-heading');page.get_by_role('button',name='닫기',exact=True).click()
   # Manually adjusted journal lines are preserved when the header amount changes.
   new();page.locator('.line-debit').first.fill('50000');page.locator('[name="amount"]').fill('60000');assert page.locator('.line-debit').first.input_value()=='50000';assert '분개 확인 필요' in page.locator('#journal-totals').inner_text();page.locator('#recalculate').click();assert page.locator('.line-debit').first.input_value()=='60000';page.get_by_role('button',name='닫기',exact=True).click()
   # Upload failures remain visible and block saving an unattached physical voucher.
   new();page.route('**/api/files',lambda route:route.fulfill(status=502,json={'error':'[EVIDENCE_BUCKET_NOT_FOUND] 증빙 저장 버킷을 찾을 수 없습니다.'}))
   page.locator('#evidence').set_input_files(str(PNG));page.wait_for_function("document.querySelector('#upload-status')?.textContent.includes('EVIDENCE_BUCKET_NOT_FOUND')")
   page.get_by_role('button',name='전표 저장',exact=True).click();assert '업로드가 완료되지 않았습니다' in page.locator('#form-error').inner_text();assert page.locator('#attachment-list a').count()==0
   assert not errors,errors;print(json.dumps(dict(status='passed',database='TLS PostgreSQL' if cfg else 'SQLite',png_bytes=PNG.stat().st_size,physical_save=True,download_exact=True,refresh_failure_does_not_duplicate=True,manual_journal_preserved=True,upload_error_visible=True,page_errors=errors),ensure_ascii=False));browser.close()
 finally:server.terminate();server.wait(timeout=5)
