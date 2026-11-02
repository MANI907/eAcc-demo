"""SQLite for local development; TLS-verified PostgreSQL for Render/Supabase."""
from contextlib import contextmanager
import os, sqlite3
from pathlib import Path

class Record(dict):
 def __getitem__(self,key):
  return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)
def row_factory(cursor):
 columns=[column.name for column in (cursor.description or [])]
 return lambda values:Record(zip(columns,values))
class Postgres:
 def __init__(self,conn):self.conn=conn
 def execute(self,sql,parameters=()):return self.conn.execute(sql.replace('?', '%s'),parameters)
 def executescript(self,sql):
  # Only application-owned DDL, never arbitrary input.
  sql=sql.replace('id INTEGER PRIMARY KEY,at TEXT','id BIGSERIAL PRIMARY KEY,at TEXT').replace('content BLOB','content BYTEA')
  for statement in sql.split(';'):
   if statement.strip():self.conn.execute(statement)

@contextmanager
def connect(sqlite_path):
 url=os.environ.get('DATABASE_URL','')
 if not url:
  c=sqlite3.connect(sqlite_path,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
  try:
   with c:yield c
  finally:c.close()
  return
 import psycopg
 ca=os.environ.get('DATABASE_SSL_ROOT_CERT','/etc/ssl/certs/ca-certificates.crt')
 if not Path(ca).is_file():raise RuntimeError('PostgreSQL CA trust file is unavailable.')
 # Explicit kwargs override URL options, so the URL cannot turn TLS verification off.
 with psycopg.connect(url,sslmode='verify-full',sslrootcert=ca,connect_timeout=10,prepare_threshold=None,row_factory=row_factory) as conn:
  conn.execute('CREATE SCHEMA IF NOT EXISTS eacc')
  conn.execute('REVOKE ALL ON SCHEMA eacc FROM PUBLIC')
  conn.execute('SET LOCAL search_path TO eacc')
  # Database-level transaction serialization also protects multiple server processes.
  conn.execute('SELECT pg_advisory_xact_lock(7143090701)')
  yield Postgres(conn)
