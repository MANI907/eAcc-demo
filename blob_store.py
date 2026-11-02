"""Private Supabase Storage. Keys and object URLs never reach the browser."""
import os,re
from urllib.parse import urlparse
import requests

_MESSAGES={
 'EVIDENCE_BUCKET_NOT_FOUND':'증빙 저장 버킷을 찾을 수 없습니다. Supabase에 비공개 eacc-evidence 버킷을 만들고 서버의 버킷 설정을 확인하세요.',
 'EVIDENCE_STORAGE_AUTH':'증빙 저장소 인증에 실패했습니다. 서버의 Supabase service_role 키와 프로젝트 설정을 확인하세요.',
 'EVIDENCE_FILE_POLICY':'저장소의 파일 크기 또는 형식 제한에 걸렸습니다. 버킷의 허용 형식(PDF/PNG/JPEG)과 5MB 제한을 확인하세요.',
 'EVIDENCE_NOT_FOUND':'첨부파일을 저장소에서 찾을 수 없습니다.',
 'EVIDENCE_STORAGE_TLS':'증빙 저장소의 인증서 검증에 실패했습니다. 서버의 HTTPS 신뢰 설정을 확인하세요.',
 'EVIDENCE_STORAGE_NETWORK':'증빙 저장소에 연결하지 못했습니다. 잠시 후 다시 시도하세요.',
 'EVIDENCE_STORAGE_FAILED':'증빙 저장소 요청에 실패했습니다. 서버의 Storage 설정을 확인하세요.',
}
class StorageError(RuntimeError):
 def __init__(self,code):
  self.code=code if code in _MESSAGES else 'EVIDENCE_STORAGE_FAILED'
  super().__init__('['+self.code+'] '+_MESSAGES[self.code])

def enabled():return bool(os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_ROLE_KEY'))
def endpoint(id,authenticated=False):
 if not re.fullmatch('[a-f0-9]{24}',id):raise ValueError('Invalid evidence identifier.')
 url=os.environ.get('SUPABASE_URL','').rstrip('/');p=urlparse(url)
 if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment or p.port not in [None,443]:raise ValueError('SUPABASE_URL must be an HTTPS project origin.')
 bucket=os.environ.get('SUPABASE_STORAGE_BUCKET','eacc-evidence')
 if not re.fullmatch('[a-z0-9][a-z0-9-]{0,62}',bucket):raise ValueError('Invalid evidence bucket.')
 route='/storage/v1/object/authenticated/' if authenticated else '/storage/v1/object/'
 return url+route+bucket+'/'+id

def response_error(response):
 # Provider bodies can contain sensitive details. Use them only for classification.
 try:
  payload=response.json();payload=payload if isinstance(payload,dict) else {}
 except (ValueError,TypeError):payload={}
 detail=' '.join(str(payload.get(k,'')) for k in ['message','error']).lower()
 status=str(payload.get('statusCode',response.status_code))
 if 'bucket' in detail and ('not found' in detail or 'does not exist' in detail):code='EVIDENCE_BUCKET_NOT_FOUND'
 elif response.status_code in [401,403] or status in ['401','403'] or 'jwt' in detail or 'row-level security' in detail:code='EVIDENCE_STORAGE_AUTH'
 elif response.status_code==413 or status=='413' or any(x in detail for x in ['mime type','mime-type','maximum allowed size','exceeded the maximum']):code='EVIDENCE_FILE_POLICY'
 elif response.status_code==404 or status=='404':code='EVIDENCE_NOT_FOUND'
 else:code='EVIDENCE_STORAGE_FAILED'
 return StorageError(code)

def request(method,id,raw=None,mime=None):
 key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
 if not key:raise StorageError('EVIDENCE_STORAGE_AUTH')
 headers={'Authorization':'Bearer '+key,'apikey':key}
 if mime:headers['Content-Type']=mime
 try:
  r=requests.request(method,endpoint(id,authenticated=(method=='GET')),headers=headers,data=raw,timeout=(5,20),allow_redirects=False)
  if not 200<=r.status_code<300:raise response_error(r)
  return r.content
 except requests.exceptions.SSLError:raise StorageError('EVIDENCE_STORAGE_TLS') from None
 except requests.RequestException:raise StorageError('EVIDENCE_STORAGE_NETWORK') from None

def upload(id,raw,mime):request('POST',id,raw,mime)
def download(id):return request('GET',id)
def delete(id):request('DELETE',id)
