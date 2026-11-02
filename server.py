"""eAcc local development portal. Production SSO is deliberately not simulated."""
import base64, csv, datetime as dt, hashlib, io, json, mimetypes, os, secrets, sqlite3, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from catalog import MENUS
import persistence, blob_store
from database_diagnostics import startup_message
import time
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('EACC_DATA_DIR',ROOT/'.runtime')); DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'portal.db'
SESSIONS={}; SESSION_TIMES={}; LOGIN_FAILURES={}; LOCK=threading.RLock()
USERS={'employee':dict(id='E1001',name='김하늘',team='재무기획팀',role='employee'), 'manager':dict(id='E1002',name='박서준',team='재무기획팀',role='manager'), 'ito':dict(id='E1003',name='이서연',team='회계팀',role='ito')}
LABELS={'draft':'작성중','submitted':'결재중','approved':'승인완료','rejected':'반려','posted':'전기완료'}
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def today(): return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
def connection():
 return persistence.connect(DB)
def audit(c,user,action,entity,detail=''):
 c.execute('INSERT INTO audit(at,actor,action,entity,detail) VALUES(?,?,?,?,?)',(now(),user['id'],action,str(entity),detail))
SCHEMA='''CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY,kind TEXT NOT NULL,owner TEXT NOT NULL,data TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,owner TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT,actor TEXT,action TEXT,entity TEXT,detail TEXT);
  CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT);
  CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,owner TEXT,name TEXT,mime TEXT,content BLOB);
  '''
def init():
 with connection() as c:
  c.executescript(SCHEMA)
  if not c.execute('SELECT 1 FROM settings').fetchone():
   c.execute('INSERT INTO settings VALUES(1,?)',(json.dumps(dict(favorites=True,notifications=True,auto_manager=True,dashboard=True,refresh_version=1)),))
  if c.execute('SELECT 1 FROM objects').fetchone():return
  def put(kind,id,data,owner='E1001'):c.execute('INSERT INTO objects VALUES(?,?,?,?)',(id,kind,owner,json.dumps(data,ensure_ascii=False)))
  put('cards','CARD-001',dict(name='업무용 법인카드',number='신한 •••• 4821',holder='김하늘',shared=False,vendor='V1000',limit=5000000))
  put('cards','CARD-002',dict(name='부서 공용카드',number='국민 •••• 7190',holder='재무기획팀',shared=True,vendor='V1001',limit=10000000))
  for i,(merchant,industry,amount,days,card) in enumerate([('서울역 KTX','교통',59800,0,'CARD-001'),('그린테이블','음식점',77000,2,'CARD-001'),('비즈니스 호텔','숙박',110000,3,'CARD-001'),('오피스 서플라이','사무용품',330000,4,'CARD-002'),('한강 레스토랑','음식점',165000,16,'CARD-001'),('에너지 컨퍼런스','교육',220000,5,'CARD-001')]):
   day=(dt.date.fromisoformat(today())-dt.timedelta(days=days)).isoformat()
   taxable=industry not in ['교통','교육']; vat=amount//11 if taxable else 0
   put('transactions',f'TX-{i+1:04}',dict(date=day,merchant=merchant,industry=industry,amount=amount,supply=amount-vat,vat=vat,card=card,approval=f'982401{i:02}',locked=days>10,source='demo',deleted=False))
  for i,(merchant,amount) in enumerate([('한빛솔루션',1100000),('에코에너지 서비스',550000),('디지털워크',330000)]):
   put('invoices',f'INV-{i+1:03}',dict(date=today(),merchant=merchant,amount=amount,supply=amount-amount//11,vat=amount//11,approval=f'DEMO-TAX-{i+1}',source='demo',deleted=False))
  put('vendors','V1000',dict(name='신한카드 정산',business_number='DEMO-001',type='카드사',status='승인완료'))
  put('vendors','V1001',dict(name='국민카드 정산',business_number='DEMO-002',type='카드사',status='승인완료'))
  put('vendors','V2000',dict(name='한빛솔루션',business_number='DEMO-003',type='법인',status='승인완료'))
  put('trips','TRIP-001',dict(name='여수 사업장 업무 협의',traveler='김하늘',start=today(),end=today(),country='KR',purpose='사업장 운영 점검',deleted=False))
  put('notices','NOTICE-001',dict(title='11월 경비 마감 및 증빙 제출 안내',body='전표 작성 시 증빙일자와 전기일자를 확인해 주세요. 지연 법인카드는 해제 승인 후 처리할 수 있습니다.',date=today(),pinned=True))
  put('manuals','MANUAL-001',dict(title='법인카드 전표 작성 가이드',body='1. 승인내역을 선택합니다.\n2. 계정과 코스트센터, 세금코드를 확인합니다.\n3. 증빙을 첨부하고 결재선을 지정합니다.\n4. 상신 후 결재관리에서 처리 결과를 확인합니다.',date=today()))
  put('budgets','BUD-001',dict(name='재무기획팀',cost_center='110370',wbs='ENERGY-2026-01',account='610100',budget=50000000))
  put('budgets','BUD-002',dict(name='신재생사업팀',cost_center='120100',wbs='SOLAR-2026-02',account='610200',budget=80000000))
  put('vat_rules','RULE-001',dict(name='유흥업종 불공제',industry='유흥',account='',tax_code='NON',active=True))
  put('industry_rules','RULE-002',dict(name='교통비 자동 계정',industry='교통',account='610200',tax_code='EXEMPT',active=True))
  put('account_rules','RULE-003',dict(name='접대비 불공제',industry='',account='610300',tax_code='NON',active=True))
def objects(c,kind):return [dict(json.loads(r['data']),id=r['id'],owner=r['owner']) for r in c.execute('SELECT * FROM objects WHERE kind=?',(kind,))]
def obj(c,id,kind=None):
 r=c.execute('SELECT * FROM objects WHERE id=?',(id,)).fetchone()
 if not r or (kind and r['kind']!=kind):raise ValueError('대상을 찾을 수 없습니다.')
 return dict(json.loads(r['data']),id=r['id'],owner=r['owner'],_kind=r['kind'])
def save_obj(c,item):
 d={k:v for k,v in item.items() if k not in ['id','owner','_kind']};c.execute('UPDATE objects SET data=? WHERE id=?',(json.dumps(d,ensure_ascii=False),item['id']))
def doc(c,id):
 r=c.execute('SELECT * FROM documents WHERE id=?',(id,)).fetchone()
 if not r:raise ValueError('전표를 찾을 수 없습니다.')
 return dict(json.loads(r['data']),id=r['id'],owner=r['owner'],kind=r['kind'],state=r['state'],created=r['created'])
def docs(c):return [doc(c,r[0]) for r in c.execute('SELECT id FROM documents ORDER BY created DESC')]
def require(user,*roles):
 if user['role'] not in roles:raise PermissionError('해당 기능의 권한이 없습니다.')
def available_cards(c,user):
 ids={x['id'] for x in objects(c,'cards') if x['owner']==user['id']}
 for d in objects(c,'delegations'):
  if d['delegate']==user['id'] and d['start']<=today()<=d['end']:ids.add(d['card'])
 return ids
def own_document(d,user):
 if d['owner']!=user['id']:raise PermissionError('본인 전표만 수정할 수 있습니다.')
def editable(d,user):
 own_document(d,user)
 if d['state'] not in ['draft','rejected']:raise ValueError('작성중 또는 반려 전표만 수정할 수 있습니다.')
def positive_int(value,label,zero=False):
 if isinstance(value,bool) or not isinstance(value,int) or value<(0 if zero else 1) or value>10**12:raise ValueError(label+' 금액을 확인하세요.')
 return value
def validate(d,c):
 if not str(d.get('title','')).strip():raise ValueError('전표 제목을 입력하세요.')
 for field in ['date','posting_date']:
  try:dt.date.fromisoformat(d.get(field,''))
  except (ValueError,TypeError):raise ValueError('증빙일자와 전기일자를 확인하세요.')
 if not d.get('cost_center') or not d.get('account'):raise ValueError('계정과 코스트센터가 필요합니다.')
 if d.get('company')!='1000':raise ValueError('데모 회사코드는 1000입니다.')
 lines=d.get('lines',[])
 if not 1<=len(lines)<=100:raise ValueError('분개는 1~100행이어야 합니다.')
 debit=credit=0
 for line in lines:
  if not line.get('account'):raise ValueError('각 분개의 계정이 필요합니다.')
  a=positive_int(line.get('debit',0),'차변',True);b=positive_int(line.get('credit',0),'대변',True)
  if bool(a)==bool(b):raise ValueError('각 분개는 차변 또는 대변 한쪽에 금액을 입력하세요.')
  debit+=a;credit+=b
 if debit!=credit:raise ValueError('차변과 대변 합계가 일치하지 않습니다.')
 amount=positive_int(d.get('amount'),'총')
 if amount!=debit:raise ValueError('전표금액과 분개 합계가 일치하지 않습니다.')
 vat=positive_int(d.get('vat',0),'세액',True)
 if vat>amount:raise ValueError('세액은 총액을 초과할 수 없습니다.')
 tax=d.get('tax_code')
 if tax not in ['VAT10','NON','EXEMPT']:raise ValueError('세금코드를 확인하세요.')
 if tax in ['NON','EXEMPT'] and vat:raise ValueError('불공제·면세는 부가세 대급금을 별도 계상할 수 없습니다.')
 for rule in objects(c,'account_rules')+objects(c,'vat_rules'):
  if rule.get('active') and ((rule.get('account') and rule['account']==d['account']) or (rule.get('industry') and rule['industry']==d.get('industry'))) and tax=='VAT10':raise ValueError('통제계정 또는 통제업종은 불공제로 처리하세요.')
 if d['kind'].startswith('trip_'):
  trip=obj(c,d.get('trip_id',''),'trips')
  if trip['owner']!=d['owner'] or trip.get('deleted'):raise ValueError('유효한 본인 출장정보를 선택하세요.')
  category=d.get('expense_category','meal');limit={'meal':30000,'hotel':100000,'transport':None}.get(category)
  days=(dt.date.fromisoformat(trip['end'])-dt.date.fromisoformat(trip['start'])).days+1
  if limit:
   spent=sum(x['amount'] for x in docs(c) if x['id']!=d['id'] and x['state']!='rejected' and x.get('trip_id')==trip['id'] and x.get('expense_category')==category)
   if spent+amount>limit*days:raise ValueError(f'출장비 한도 초과: {days}일 기준 {limit*days:,}원 (기존 {spent:,}원)')
 if d['kind'].startswith('settle_'):
  advance=doc(c,d.get('advance_id',''))
  if advance['owner']!=d['owner'] or advance['kind']!='advance_'+d['kind'][7:] or advance['state'] not in ['approved','posted']:raise ValueError('동일 유형의 승인된 본인 선급전표를 선택하세요.')
  used=sum(x['amount'] for x in docs(c) if x['id']!=d['id'] and x.get('advance_id')==advance['id'] and x['state']!='rejected')
  if used+amount>advance['amount']:raise ValueError('미정산 잔액을 초과했습니다.')
 for fid in d.get('attachments',[]):
  f=c.execute('SELECT owner FROM files WHERE id=?',(fid,)).fetchone()
  if not f or f['owner']!=d['owner']:raise ValueError('첨부 증빙의 소유자를 확인하세요.')
 if d['kind'].startswith('advance_'):
  expected='136100' if d['kind']=='advance_vendor' else '136000'
  if d['account']!=expected or vat or tax=='VAT10':raise ValueError('선급금은 선급 계정과 세금없음으로 신청하세요.')
  if sum(x['debit'] for x in lines if x['account']==expected)!=amount:raise ValueError('선급금 차변 계정을 확인하세요.')
 if d['kind'].startswith('settle_'):
  expected='136100' if d['kind']=='settle_vendor' else '136000'
  if sum(x['credit'] for x in lines if x['account']==expected)!=amount:raise ValueError('정산 대변은 해당 선급 계정이어야 합니다.')
 if sum(x['debit'] for x in lines if x['account']=='135100')!=vat:raise ValueError('부가세 대급금 분개와 세액이 다릅니다.')
 if not d['kind'].startswith(('advance_','settle_')) and sum(x['debit'] for x in lines if x['account']==d['account'])!=amount-vat:raise ValueError('비용계정 차변과 공급가액을 확인하세요.')
 vendor=obj(c,d.get('vendor',''),'vendors')
 if vendor.get('status')!='승인완료':raise ValueError('승인된 공급업체만 사용할 수 있습니다.')
 return debit
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,data,ctype='application/json; charset=utf-8'):
  payload=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,(dict,list)) else data
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(payload)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(payload)
 def user(self):
  token=dict(x.strip().split('=',1) for x in self.headers.get('Cookie','').split(';') if '=' in x).get('eacc_session')
  user=SESSIONS.get(token)
  if token and token in SESSION_TIMES and time.time()-SESSION_TIMES[token]>28800:
   SESSIONS.pop(token,None);SESSION_TIMES.pop(token,None);user=None
  if not user:raise PermissionError('로그인이 필요합니다.')
  return user
 def do_GET(self):
  try:
   path=urlparse(self.path).path;qs=parse_qs(urlparse(self.path).query)
   if path=='/api/health':
    try:
     with connection() as c:c.execute('SELECT 1').fetchone()
     return self.send(200,dict(status='ok',mode='hosted-demo' if os.environ.get('DATABASE_URL') else 'local-demo',date=today()))
    except Exception:return self.send(503,dict(status='unavailable'))
   if not path.startswith('/api/'):
    files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
    if path not in files:return self.send(404,dict(error='페이지가 없습니다.'))
    p=ROOT/'web'/files[path];return self.send(200,p.read_bytes(),mimetypes.guess_type(str(p))[0]+'; charset=utf-8')
   user=self.user()
   with connection() as c:
    if path=='/api/bootstrap':
     all_docs=docs(c);my_docs=[x for x in all_docs if x['owner']==user['id'] or user['role']=='ito' or (user['id'] in x.get('approvers',[]))]
     kinds=['cards','transactions','invoices','delegations','unlocks','vendors','trips','budgets','notices','manuals','account_rules','vat_rules','industry_rules']
     data={k:objects(c,k) for k in kinds};cards=available_cards(c,user)
     if user['role']!='ito':
      data['cards']=[x for x in data['cards'] if x['id'] in cards]
      data['transactions']=[x for x in data['transactions'] if x['card'] in cards]
      data['trips']=[x for x in data['trips'] if x['owner']==user['id']]
      data['delegations']=[x for x in data['delegations'] if x['owner']==user['id'] or x['delegate']==user['id']]
      data['unlocks']=[x for x in data['unlocks'] if x['owner']==user['id'] or user['role']=='manager']
     return self.send(200,dict(user=user,users=list(USERS.values()),menus=MENUS,settings=json.loads(c.execute('SELECT data FROM settings').fetchone()[0]),documents=my_docs,today=today(),**data))
    if path=='/api/audit':
     require(user,'ito');return self.send(200,[dict(x) for x in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200')])
    if path=='/api/export':
     out=io.StringIO();w=csv.writer(out);w.writerow(['전표번호','유형','제목','상태','금액','전기일자'])
     for d in docs(c):
      if user['role']=='ito' or d['owner']==user['id']:w.writerow([d['id'],d['kind'],"'"+d['title'] if d['title'][:1] in '=+-@' else d['title'],LABELS[d['state']],d['amount'],d['posting_date']])
     return self.send(200,('\ufeff'+out.getvalue()).encode(),'text/csv; charset=utf-8')
    if path.startswith('/api/files/'):
     r=c.execute('SELECT * FROM files WHERE id=?',(path.rsplit('/',1)[-1],)).fetchone()
     if not r or (r['owner']!=user['id'] and user['role'] not in ['manager','ito']):raise PermissionError('첨부파일 권한이 없습니다.')
     return self.send(200,bytes(r['content']) if r['content'] is not None else blob_store.download(r['id']),r['mime'])
    return self.send(404,dict(error='API를 찾을 수 없습니다.'))
  except PermissionError as e:self.send(403,dict(error=str(e)))
  except ValueError as e:self.send(400,dict(error=str(e)))
  except Exception:self.send(503,dict(error='저장소 연결을 확인하세요.'))
 def do_POST(self):
  try:
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'):raise PermissionError('다른 출처의 요청은 허용되지 않습니다.')
   size=int(self.headers.get('Content-Length','0'))
   if size>8*1024*1024:raise ValueError('요청 용량을 초과했습니다.')
   body=json.loads(self.rfile.read(size) or '{}');path=urlparse(self.path).path
   if path=='/api/login':
    code=os.environ.get('EACC_ACCESS_CODE','')
    client=self.client_address[0];cutoff=time.time()-300
    attempts=[t for t in LOGIN_FAILURES.get(client,[]) if t>cutoff]
    if len(attempts)>=10:raise PermissionError('로그인 시도 횟수를 초과했습니다. 5분 후 다시 시도하세요.')
    if code and not secrets.compare_digest(str(body.get('access_code','')).encode(),code.encode()):
     LOGIN_FAILURES[client]=attempts+[time.time()];raise PermissionError('데모 접속코드를 확인하세요.')
    LOGIN_FAILURES.pop(client,None)
    user=USERS.get(body.get('role'))
    if not user:raise ValueError('데모 역할을 선택하세요.')
    token=secrets.token_urlsafe(32);SESSIONS[token]=dict(user);SESSION_TIMES[token]=time.time()
    payload=json.dumps(user,ensure_ascii=False).encode();self.send_response(200);self.send_header('Set-Cookie',f'eacc_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+('; Secure' if os.environ.get('EACC_PUBLIC_DEPLOYMENT')=='1' else ''));self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
   user=self.user()
   self.uploaded_blob=None
   try:
    with LOCK,connection() as c:
     result=self.mutate(c,user,path,body)
   except Exception:
    if self.uploaded_blob:
     try:blob_store.delete(self.uploaded_blob)
     except Exception:pass
    raise
   self.send(200,result)
  except PermissionError as e:self.send(403,dict(error=str(e)))
  except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:self.send(400,dict(error=str(e)))
  except Exception:self.send(500,dict(error='처리 중 오류가 발생했습니다. 서버 로그를 확인하세요.'))
 def mutate(self,c,u,path,b):
  if path=='/api/logout':
   for key in list(SESSIONS):
    if SESSIONS[key]==u:SESSIONS.pop(key,None);SESSION_TIMES.pop(key,None)
   return dict(ok=True)
  if path=='/api/settings':
   require(u,'ito');s=json.loads(c.execute('SELECT data FROM settings').fetchone()[0])
   for k in ['favorites','notifications','auto_manager','dashboard']:
    if k in b:
     if not isinstance(b[k],bool):raise ValueError('설정 값은 ON/OFF입니다.')
     s[k]=b[k]
   if b.get('refresh'):s['refresh_version']+=1
   c.execute('UPDATE settings SET data=?',(json.dumps(s),));audit(c,u,'settings','ITO');return s
  if path=='/api/files':
   raw=base64.b64decode(b.get('content',''),validate=True)
   mime=b.get('mime');name=Path(b.get('name','증빙')).name
   if not raw or len(raw)>5*1024*1024:raise ValueError('증빙은 5MB 이하입니다.')
   if mime not in ['application/pdf','image/png','image/jpeg']:raise ValueError('PDF, PNG, JPEG만 첨부할 수 있습니다.')
   if not ((mime=='application/pdf' and raw.startswith(b'%PDF-')) or (mime=='image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (mime=='image/jpeg' and raw.startswith(b'\xff\xd8'))):raise ValueError('파일 내용과 형식이 일치하지 않습니다.')
   id=secrets.token_hex(12)
   if blob_store.enabled():
    blob_store.upload(id,raw,mime);self.uploaded_blob=id;content=None
   else:content=raw
   c.execute('INSERT INTO files VALUES(?,?,?,?,?)',(id,u['id'],name,mime,content));audit(c,u,'upload',id);return dict(id=id,name=name)
  if path=='/api/documents':
   kind=b.get('kind');valid={x['kind'] for x in MENUS if x['section']=='전표작성'}-{'unlocks'}
   if kind not in valid:raise ValueError('지원하지 않는 전표유형입니다.')
   id=b.get('id');old=doc(c,id) if id else None
   if old:editable(old,u)
   source=b.get('source_id','')
   if old and source!=old.get('source_id',''):raise ValueError('증빙 원천은 변경할 수 없습니다.')
   original=None
   if kind in ['card','trip_card','invoice']:
    original=obj(c,source,'invoices' if kind=='invoice' else 'transactions')
    if kind!='invoice' and original['card'] not in available_cards(c,u):raise PermissionError('카드 처리 권한이 없습니다.')
    if kind!='invoice' and b.get('vendor')!=obj(c,original['card'],'cards')['vendor']:raise ValueError('카드의 정산 공급업체와 전표 공급업체가 다릅니다.')
    if original.get('locked') or original.get('deleted'):raise ValueError('LOCK 또는 삭제된 증빙은 처리할 수 없습니다.')
    if any(x.get('source_id')==source and x['id']!=id for x in docs(c)):raise ValueError('이미 전표가 작성된 증빙입니다.')
   d={k:b.get(k) for k in ['title','date','posting_date','company','cost_center','wbs','account','tax_code','amount','vat','lines','trip_id','expense_category','advance_id','vendor','industry']}
   d.update(id=id or 'EA-'+dt.date.fromisoformat(today()).strftime('%Y%m')+'-'+secrets.token_hex(3).upper(),owner=u['id'],kind=kind,source_id=source,attachments=b.get('attachments',[]),approvers=b.get('approvers',[]),history=old.get('history',[]) if old else [])
   if original:
    if d['amount']!=original['amount']:raise ValueError('원천 증빙금액과 전표금액이 다릅니다.')
    d['industry']=original.get('industry','')
    if d['tax_code']=='VAT10' and d['vat']!=original['vat']:raise ValueError('원천 증빙의 세액과 일치해야 합니다.')
   if kind in ['physical','trip_physical'] and not d['attachments']:raise ValueError('실물증빙 파일을 첨부하세요.')
   validate(d,c)
   payload=json.dumps(d,ensure_ascii=False)
   if old:c.execute('UPDATE documents SET state=?,data=? WHERE id=?',('draft',payload,d['id']))
   else:c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',(d['id'],u['id'],kind,'draft',payload,now()))
   audit(c,u,'save',d['id']);return doc(c,d['id'])
  if path.startswith('/api/documents/'):
   _,_,_,id,action=path.split('/');d=doc(c,id);state=d['state'];history=d.get('history',[])
   if action=='submit':
    editable(d,u);validate(d,c)
    approvers=b.get('approvers',d.get('approvers',[]));s=json.loads(c.execute('SELECT data FROM settings').fetchone()[0])
    if not approvers and s['auto_manager']:approvers=['E1002']
    allowed={x['id'] for x in USERS.values() if x['role'] in ['manager','ito']}
    if not approvers or len(approvers)>10 or len(set(approvers))!=len(approvers) or any(x not in allowed or x==u['id'] for x in approvers):raise ValueError('본인을 제외한 유효한 결재선을 지정하세요. 최대 10명입니다.')
    d['approvers']=approvers;d['step']=0;state='submitted'
   elif action in ['approve','reject']:
    require(u,'manager','ito')
    if state!='submitted' or d['approvers'][d.get('step',0)]!=u['id']:raise PermissionError('현재 결재자만 처리할 수 있습니다.')
    if action=='reject':
     if not b.get('reason','').strip():raise ValueError('반려 사유를 입력하세요.')
     state='rejected'
    else:
     d['step']=d.get('step',0)+1;state='approved' if d['step']==len(d['approvers']) else 'submitted'
   elif action=='withdraw':
    own_document(d,u)
    if state!='submitted' or d.get('step',0)>0:raise ValueError('결재 전 상신만 회수할 수 있습니다.')
    state='draft'
   elif action=='post':
    require(u,'ito')
    if state=='posted':return d
    if state!='approved':raise ValueError('승인된 전표만 전기할 수 있습니다.')
    validate(d,c)
    # Demo posting stays distinct from live SAP. Live writes require verified tenant-specific mapping.
    d['sap_reference']='SIM-'+secrets.token_hex(5).upper();d['sap_mode']='simulation';state='posted'
   else:raise ValueError('지원하지 않는 전표 처리입니다.')
   history.append(dict(at=now(),actor=u['name'],action=action,reason=b.get('reason','')));d['history']=history
   c.execute('UPDATE documents SET state=?,data=? WHERE id=?',(state,json.dumps(d,ensure_ascii=False),id));audit(c,u,action,id,b.get('reason',''));return doc(c,id)
  if path=='/api/cards':
   require(u,'ito')
   owner=b.get('holder_id')
   if owner not in {x['id'] for x in USERS.values()}:raise ValueError('카드 소유자를 선택하세요.')
   last4=b.get('last4','')
   if len(last4)!=4 or not last4.isdigit():raise ValueError('카드번호는 마지막 4자리만 등록하세요.')
   vendor=obj(c,b.get('vendor',''),'vendors')
   if vendor.get('status')!='승인완료':raise ValueError('승인된 정산 공급업체가 필요합니다.')
   name=b.get('name','').strip();issuer=b.get('issuer','').strip()
   if not name or not issuer:raise ValueError('카드명과 카드사를 입력하세요.')
   amount=positive_int(b.get('limit'),'한도')
   r=self.create(c,u,'cards',dict(name=name,number=issuer+' •••• '+last4,holder=next(x['name'] for x in USERS.values() if x['id']==owner),shared=b.get('shared') is True,vendor=vendor['id'],limit=amount),['name','number','holder','shared','vendor','limit'])
   c.execute('UPDATE objects SET owner=? WHERE id=?',(owner,r['id']));r['owner']=owner;return r
  if path=='/api/delegations/revoke':
   r=obj(c,b['id'],'delegations')
   if r['owner']!=u['id']:raise PermissionError('본인 위임만 해제할 수 있습니다.')
   c.execute('DELETE FROM objects WHERE id=?',(r['id'],));audit(c,u,'revoke_delegation',r['id']);return dict(ok=True)
  if path=='/api/delegations':
   card=obj(c,b['card'],'cards')
   if card['owner']!=u['id']:raise PermissionError('본인 소유 카드만 위임할 수 있습니다.')
   if b.get('delegate') not in {x['id'] for x in USERS.values()} or b['delegate']==u['id']:raise ValueError('다른 수임자를 선택하세요.')
   start=dt.date.fromisoformat(b['start']);end=dt.date.fromisoformat(b['end'])
   if end<start:raise ValueError('위임기간을 확인하세요.')
   return self.create(c,u,'delegations',b,['card','delegate','start','end'])
  if path=='/api/unlocks':
   tx=obj(c,b['transaction'],'transactions')
   if tx['card'] not in available_cards(c,u):raise PermissionError('본인 또는 수임 카드만 요청할 수 있습니다.')
   if not tx.get('locked') or not b.get('reason','').strip():raise ValueError('LOCK 내역과 해제 사유를 확인하세요.')
   if any(x['transaction']==tx['id'] and x['status']=='요청중' for x in objects(c,'unlocks')):raise ValueError('이미 요청중입니다.')
   return self.create(c,u,'unlocks',dict(b,status='요청중'),['transaction','reason','status'])
  if path=='/api/unlocks/approve':
   require(u,'manager','ito');r=obj(c,b['id'],'unlocks')
   if r['owner']==u['id']:raise PermissionError('본인 해제요청은 승인할 수 없습니다.')
   if r['status']!='요청중':raise ValueError('이미 처리된 요청입니다.')
   tx=obj(c,r['transaction'],'transactions');tx['locked']=False;save_obj(c,tx);r['status']='승인완료';save_obj(c,r);audit(c,u,'unlock',tx['id']);return r
  if path=='/api/trips':
   start=dt.date.fromisoformat(b['start']);end=dt.date.fromisoformat(b['end'])
   if start>end:raise ValueError('출장기간을 확인하세요.')
   return self.create(c,u,'trips',dict(b,traveler=u['name'],deleted=False),['name','traveler','start','end','country','purpose','deleted'])
  if path=='/api/trips/delete':
   require(u,'ito');r=obj(c,b['id'],'trips')
   if not b.get('reason','').strip():raise ValueError('삭제 사유를 입력하세요.')
   r.update(deleted=True,deleted_at=now(),deleted_by=u['name'],delete_reason=b['reason']);save_obj(c,r);audit(c,u,'trip_delete',r['id'],b['reason']);return r
  if path in ['/api/vendors','/api/vendor_changes']:
   data=dict(b,status='결재중')
   if path.endswith('vendor_changes'):
    r=obj(c,b['target'],'vendors');data['target']=r['id']
   if not b.get('name') or len(''.join(x for x in b.get('business_number','') if x.isdigit()))!=10:raise ValueError('공급업체명과 10자리 사업자번호가 필요합니다.')
   return self.create(c,u,'vendor_requests',data,['name','business_number','type','status','target'])
  if path=='/api/vendors/approve':
   require(u,'manager','ito');r=obj(c,b['id'],'vendor_requests')
   if r['owner']==u['id']:raise PermissionError('본인 공급업체 요청은 승인할 수 없습니다.')
   if r['status']!='결재중':raise ValueError('처리된 요청입니다.')
   if r.get('target'):
    target=obj(c,r['target'],'vendors');target.update({k:r[k] for k in ['name','business_number','type']});save_obj(c,target)
   else:self.create(c,u,'vendors',dict(r,status='승인완료'),['name','business_number','type','status'])
   r['status']='승인완료';save_obj(c,r);audit(c,u,'vendor_approve',r['id']);return r
  if path=='/api/vendor_requests':return objects(c,'vendor_requests')
  if path=='/api/integrations/codef':
   require(u,'ito')
   from codef_adapter import probe_codef
   result=probe_codef();audit(c,u,'codef_sandbox_test','CODEF',result['status']);return result
  if path=='/api/integrations/test':
   require(u,'ito')
   from integrations import probe_sap
   result=probe_sap()
   audit(c,u,'sap_readonly_test','SAP',result['status'])
   return result
  if path.startswith('/api/objects/'):
   kind=path.rsplit('/',1)[-1]
   if kind not in ['notices','manuals','account_rules','vat_rules','industry_rules']:raise ValueError('지원하지 않는 관리대상입니다.')
   require(u,'ito')
   if b.get('delete'):
    r=obj(c,b['id'],kind);c.execute('DELETE FROM objects WHERE id=?',(r['id'],));audit(c,u,'delete',r['id']);return dict(ok=True)
   fields=['title','body','date'] if kind in ['notices','manuals'] else ['name','industry','account','tax_code','active']
   if not b.get(fields[0]):raise ValueError('필수 항목을 입력하세요.')
   if b.get('id'):
    r=obj(c,b['id'],kind);r.update({k:b.get(k) for k in fields});save_obj(c,r);audit(c,u,'update',r['id']);return r
   return self.create(c,u,kind,b,fields)
  raise ValueError('지원하지 않는 API입니다.')
 def create(self,c,u,kind,b,fields):
  id=kind.upper()+'-'+secrets.token_hex(4).upper();d={k:b.get(k) for k in fields};c.execute('INSERT INTO objects VALUES(?,?,?,?)',(id,kind,u['id'],json.dumps(d,ensure_ascii=False)));audit(c,u,'create',id);return dict(d,id=id,owner=u['id'])
def check_deployment():
 if os.environ.get('EACC_PUBLIC_DEPLOYMENT')=='1':
  required=['DATABASE_URL','SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','EACC_ACCESS_CODE']
  missing=[name for name in required if not os.environ.get(name)]
  if missing:raise RuntimeError('Required hosted configuration is missing: '+', '.join(missing))
  if len(os.environ['EACC_ACCESS_CODE'])<16:raise RuntimeError('EACC_ACCESS_CODE must be at least 16 characters.')
  if os.environ['DATABASE_URL'].split(':',1)[0] not in ['postgresql','postgres']:raise RuntimeError('Hosted deployment requires PostgreSQL.')
if __name__=='__main__':
 check_deployment()
 try:init()
 except Exception as error:raise SystemExit(startup_message(error)) from None
 port=int(os.environ.get('PORT','8000'));host=os.environ.get('HOST','127.0.0.1');print(f'eAcc listening on port {port}',flush=True);ThreadingHTTPServer((host,port),Handler).serve_forever()
