"""Add Supabase's official database CA without weakening TLS validation.

Source of OFFICIAL_CA_URL: Supabase Studio SSLConfiguration + custom-content.json:
https://github.com/supabase/supabase/blob/master/apps/studio/hooks/custom-content/custom-content.json
https://github.com/supabase/supabase/blob/master/apps/studio/components/interfaces/Settings/Database/SSLConfiguration.tsx
"""
import datetime as dt
import os,re,ssl,threading,urllib.request,tempfile
from pathlib import Path
from database_diagnostics import DatabaseConfigError

OFFICIAL_CA_URL='https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt'
SYSTEM_CA=Path('/etc/ssl/certs/ca-certificates.crt')
CACHE=Path(__file__).resolve().parent/'.runtime'/'database-trust'
_LOCK=threading.Lock()
_PEM=re.compile(rb'\s*-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\s*')

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def validate_ca(raw):
 from cryptography import x509
 from cryptography.hazmat.primitives import serialization
 try:
  if not _PEM.fullmatch(raw):raise ValueError()
  cert=x509.load_pem_x509_certificate(raw)
  if not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:raise ValueError()
  now=dt.datetime.now(dt.timezone.utc)
  if not cert.not_valid_before_utc<=now<cert.not_valid_after_utc:raise ValueError()
  pem=cert.public_bytes(serialization.Encoding.PEM)
  ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).load_verify_locations(cadata=pem.decode('ascii'))
  return pem
 except Exception:raise DatabaseConfigError('DB_CA_INVALID') from None

def download_ca():
 try:
  opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
  request=urllib.request.Request(OFFICIAL_CA_URL,headers={'Accept':'application/x-pem-file, text/plain'})
  with opener.open(request,timeout=20) as response:
   if response.geturl()!=OFFICIAL_CA_URL:raise ValueError()
   raw=response.read(65537)
  if len(raw)>65536:raise ValueError()
 except Exception:raise DatabaseConfigError('DB_CA_DOWNLOAD_FAILED') from None
 return validate_ca(raw)

def atomic_write(path,contents):
 name=None
 try:
  with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as output:
   name=output.name;output.write(contents)
  os.replace(name,path)
 finally:
  if name:Path(name).unlink(missing_ok=True)

def resolve_ca(host):
 explicit=os.environ.get('DATABASE_SSL_ROOT_CERT','')
 if explicit:
  if not Path(explicit).is_file():raise DatabaseConfigError('DB_CA_UNAVAILABLE')
  return explicit
 if not SYSTEM_CA.is_file():raise DatabaseConfigError('DB_CA_UNAVAILABLE')
 # Only known Supabase hostname suffixes use the provider-specific root.
 is_supabase=isinstance(host,str) and host.endswith(('.supabase.co','.pooler.supabase.com'))
 if not is_supabase:return str(SYSTEM_CA)
 with _LOCK:
  CACHE.mkdir(parents=True,exist_ok=True);provider=CACHE/'supabase-prod-ca-2021.crt';bundle=CACHE/'database-ca-bundle.pem'
  pem=None
  if provider.is_file():
   try:pem=validate_ca(provider.read_bytes())
   except DatabaseConfigError:pass
  if pem is None:
   pem=download_ca();atomic_write(provider,pem)
  combined=SYSTEM_CA.read_bytes().rstrip()+b'\n'+pem
  if not bundle.is_file() or bundle.read_bytes()!=combined:atomic_write(bundle,combined)
  return str(bundle)
