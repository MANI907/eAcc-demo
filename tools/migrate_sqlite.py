"""Copy local data to an EMPTY Supabase DB, preserving the SQLite source.
Requires hosted DATABASE_URL and private Supabase Storage configuration.
Run before deploying the web service (which would seed an empty database).
"""
import sys,os,sqlite3
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,persistence,blob_store
TABLES=['objects','documents','audit','settings','files']
def migrate(source):
 if not os.environ.get('DATABASE_URL') or not blob_store.enabled():raise RuntimeError('Configure PostgreSQL and private Supabase Storage first.')
 if not source.is_file():raise RuntimeError('SQLite source does not exist.')
 local=sqlite3.connect('file:'+quote(str(source.resolve()))+'?mode=ro',uri=True);local.row_factory=sqlite3.Row;uploaded=[];counts={}
 try:
  local.execute('BEGIN')
  with persistence.connect(None) as target:
   target.executescript(server.SCHEMA)
   if any(target.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in TABLES):raise RuntimeError('Target contains data. No overwrite or merge was attempted.')
   for table in TABLES:
    rows=local.execute('SELECT * FROM '+table).fetchall();counts[table]=len(rows)
    for row in rows:
     data=dict(row)
     if table=='files':
      if data['content'] is None:raise RuntimeError('Source already references remote evidence; this migration supports SQLite blob evidence only.')
      blob_store.upload(data['id'],bytes(data['content']),data['mime']);uploaded.append(data['id']);data['content']=None
     target.execute('INSERT INTO '+table+'('+','.join(data)+') VALUES('+','.join('?' for _ in data)+')',tuple(data.values()))
   target.execute("SELECT setval(pg_get_serial_sequence('eacc.audit','id'),COALESCE(MAX(id),0)+1,false) FROM audit")
  return counts
 except Exception:
  cleanup_failed=False
  for id in uploaded:
   try:blob_store.delete(id)
   except Exception:cleanup_failed=True
  if cleanup_failed:print('Warning: uploaded objects may remain orphaned in the private bucket; inspect before retrying.',file=sys.stderr)
  raise
 finally:local.close()
if __name__=='__main__':
 try:
  source=Path(sys.argv[1]) if len(sys.argv)>1 else server.DB
  print(migrate(source))
 except Exception:raise SystemExit('Migration did not complete. Source SQLite was preserved. Check target emptiness, database/storage access and private bucket configuration.')
