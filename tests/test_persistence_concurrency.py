"""Connection ordering plus opt-in integration tests on a disposable PostgreSQL DB.

EACC_TEST_POSTGRES_URL must point to an isolated empty test database; never production.
DATABASE_SSL_ROOT_CERT supplies its trusted CA (TLS verification remains required).
"""
import concurrent.futures, json, os, sys, threading, unittest, uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.request import Request, urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import persistence, server

class ConnectionTests(unittest.TestCase):
 def test_lock_precedes_initialization_and_requests_do_not_change_schema(self):
  for initialize in (False,True):
   with self.subTest(initialize=initialize):
    connection=MagicMock();connection.__enter__.return_value=connection
    with patch.dict(os.environ,{'DATABASE_URL':'postgresql://test@localhost/test'}),patch('persistence.resolve_ca',return_value='/test/ca'),patch('psycopg.connect',return_value=connection):
     with persistence.connect(None,initialize=initialize):pass
    statements=[call.args[0] for call in connection.execute.call_args_list]
    expected=['SELECT pg_advisory_xact_lock(7143090701)']
    if initialize:expected+=['CREATE SCHEMA IF NOT EXISTS eacc','REVOKE ALL ON SCHEMA eacc FROM PUBLIC']
    self.assertEqual(statements,expected+['SET LOCAL search_path TO eacc'])

@unittest.skipUnless(os.environ.get('EACC_TEST_POSTGRES_URL'),'requires disposable TLS PostgreSQL')
class PostgresConcurrencyTests(unittest.TestCase):
 def test_concurrent_startup_login_reads_and_preservation(self):
  with patch.dict(os.environ,{'DATABASE_URL':os.environ['EACC_TEST_POSTGRES_URL']}):
   # Multiple independent DB connections exercise cross-process advisory locking.
   def initialize(_):server.init()
   with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    list(pool.map(initialize,range(16)))
   document_id='preserved-doc-'+uuid.uuid4().hex
   file_id='preserved-file-'+uuid.uuid4().hex
   with server.connection() as c:
    c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',(document_id,'E1001','card','draft',json.dumps({'title':'preserve me'}),'2026-11-03'))
    c.execute('INSERT INTO files VALUES(?,?,?,?,?)',(file_id,'E1001','proof.pdf','application/pdf',b'%PDF-preserved'))
   def snapshot():
    with server.connection() as c:
     return {table:[tuple(r.values()) for r in c.execute('SELECT * FROM '+table+' ORDER BY id').fetchall()] for table in ('objects','documents','files','audit','settings')}
   before=snapshot()
   http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
   thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   base='http://127.0.0.1:'+str(http.server_port)
   try:
    def read(_):
     request=Request(base+'/api/login',data=b'{"role":"employee"}',headers={'Content-Type':'application/json'})
     with urlopen(request,timeout=30) as response:cookie=response.headers['Set-Cookie'].split(';')[0]
     with urlopen(Request(base+'/api/bootstrap',headers={'Cookie':cookie}),timeout=30) as response:
      data=json.load(response)
     self.assertTrue(any(d['id']==document_id for d in data['documents']))
     self.assertTrue(data['transactions'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
     list(pool.map(read,range(48)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
     list(pool.map(initialize,range(16)))
    self.assertEqual(snapshot(),before)
   finally:
    http.shutdown();http.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
