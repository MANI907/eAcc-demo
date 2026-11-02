"""Private Supabase Storage. Keys and object URLs never reach the browser."""
import os,re
from urllib.parse import urlparse
import requests

def enabled():return bool(os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_ROLE_KEY'))
def endpoint(id):
 if not re.fullmatch('[a-f0-9]{24}',id):raise ValueError('Invalid evidence identifier.')
 url=os.environ.get('SUPABASE_URL','').rstrip('/');p=urlparse(url)
 if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment or p.port not in [None,443]:raise ValueError('SUPABASE_URL must be an HTTPS project origin.')
 bucket=os.environ.get('SUPABASE_STORAGE_BUCKET','eacc-evidence')
 if not re.fullmatch('[a-z0-9][a-z0-9-]{0,62}',bucket):raise ValueError('Invalid evidence bucket.')
 return url+'/storage/v1/object/'+bucket+'/'+id

def request(method,id,raw=None,mime=None):
 key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
 if not key:raise RuntimeError('Supabase Storage is not configured.')
 headers={'Authorization':'Bearer '+key,'apikey':key}
 if mime:headers['Content-Type']=mime
 try:
  r=requests.request(method,endpoint(id),headers=headers,data=raw,timeout=(5,20),allow_redirects=False)
  if not 200<=r.status_code<300:raise RuntimeError('Supabase Storage request failed (HTTP '+str(r.status_code)+').')
  return r.content
 except requests.RequestException:raise RuntimeError('Supabase Storage connection failed.') from None

def upload(id,raw,mime):request('POST',id,raw,mime)
def download(id):return request('GET',id)
def delete(id):request('DELETE',id)
