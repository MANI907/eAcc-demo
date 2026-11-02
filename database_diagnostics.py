"""Credential-safe database startup diagnostics. Never log exception text or DSNs."""
import re

HINTS={
 'DB_CONFIG_INVALID':'Check DATABASE_URL format. Use only the PostgreSQL URI, URL-encode reserved password characters, and replace password placeholders.',
 'DB_CA_UNAVAILABLE':'DATABASE_SSL_ROOT_CERT must point to an existing trusted CA file. TLS verification remains enabled.',
 'DB_DNS_FAILED':'Check the copied Supabase database host. Copy the exact Shared Session pooler address; do not infer its region.',
 'DB_NETWORK_FAILED':'Database network connection failed. For IPv4 hosting use Supabase Shared Session pooler (normally port 5432); check project availability.',
 'DB_CONNECT_TIMEOUT':'Database connection timed out. Check pooler host/port, project availability and network restrictions.',
 'DB_AUTH_FAILED':'Check the database password (not the Supabase account password) and the exact pooler username from Connect.',
 'DB_POOLER_TENANT_FAILED':'Supabase pooler could not identify the tenant/user. Copy the complete pooler host and postgres.<project-ref> username from Connect.',
 'DB_TLS_HOSTNAME_FAILED':'Database certificate hostname does not match. Use the exact host from Supabase Connect; do not disable TLS verification.',
 'DB_TLS_FAILED':'Database TLS verification failed. Check the Supabase-provided CA certificate and DATABASE_SSL_ROOT_CERT; do not disable verification.',
 'DB_PERMISSION_DENIED':'Database login succeeded but access was denied. Check permission to create/use the eacc schema and existing table ownership.',
 'DB_DATABASE_NOT_FOUND':'The database name does not exist. Copy the full URI and database name from Supabase Connect.',
 'DB_DRIVER_MISSING':'The PostgreSQL driver is not installed. Install the committed requirements.txt.',
 'DB_INIT_FAILED':'Database initialization failed for an unclassified reason. Check the SQLSTATE code if present; do not share credentials.',
}
class DatabaseConfigError(ValueError):
 def __init__(self,code='DB_CONFIG_INVALID'):
  self.code=code;super().__init__(HINTS[code])

def diagnose(error):
 code=getattr(error,'code',None)
 if code not in HINTS:code=None
 state=getattr(error,'sqlstate',None)
 state=state if isinstance(state,str) and re.fullmatch('[0-9A-Z]{5}',state) else None
 # Exception text may contain passwords and is inspected ONLY in memory, never returned.
 text=str(error).lower()
 if not code:
  if state=='28P01' or 'password authentication failed' in text:code='DB_AUTH_FAILED'
  elif 'tenant or user not found' in text:code='DB_POOLER_TENANT_FAILED'
  elif state=='28000' or 'authentication failed' in text:code='DB_AUTH_FAILED'
  elif state=='42501':code='DB_PERMISSION_DENIED'
  elif state=='3D000':code='DB_DATABASE_NOT_FOUND'
  elif 'certificate' in text and ('does not match' in text or 'hostname mismatch' in text):code='DB_TLS_HOSTNAME_FAILED'
  elif any(x in text for x in ['certificate verify failed','certificate verification failed','root certificate','ssl error','tls error','server does not support ssl']):code='DB_TLS_FAILED'
  elif any(x in text for x in ['could not translate host','name or service not known','temporary failure in name resolution','nodename nor servname']):code='DB_DNS_FAILED'
  elif any(x in text for x in ['timeout expired','timed out']):code='DB_CONNECT_TIMEOUT'
  elif any(x in text for x in ['network is unreachable','no route to host','connection refused','could not connect to server']):code='DB_NETWORK_FAILED'
  elif isinstance(error,ModuleNotFoundError):code='DB_DRIVER_MISSING'
  else:code='DB_INIT_FAILED'
 return {'code':code,'sqlstate':state,'message':HINTS[code]}

def startup_message(error):
 result=diagnose(error);state='; SQLSTATE='+result['sqlstate'] if result['sqlstate'] else ''
 return 'Database initialization failed ['+result['code']+state+']. '+result['message']+' Credentials and raw errors are not printed.'
