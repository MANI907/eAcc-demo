"""Hosting boundaries: access code, secure cookies, private uploads and rollback."""
import base64,os,json,unittest
from unittest.mock import patch,Mock
from urllib.request import Request,urlopen
import test_portal
import server,blob_store
class HostingTests(unittest.TestCase):
 setUpClass=classmethod(test_portal.PortalTests.setUpClass.__func__)
 tearDownClass=classmethod(test_portal.PortalTests.tearDownClass.__func__)
 setUp=test_portal.PortalTests.setUp
 call=test_portal.PortalTests.call
 def test_access_code_and_secure_cookie(self):
  with patch.dict(os.environ,dict(EACC_ACCESS_CODE='test-access-code-123456',EACC_PUBLIC_DEPLOYMENT='1')):
   self.assertEqual(self.call('login',dict(role='ito'))[0],403)
   request=Request(self.base+'/api/login',data=json.dumps(dict(role='ito',access_code='test-access-code-123456')).encode(),headers={'Content-Type':'application/json'})
   with urlopen(request) as r:
    cookie=r.headers['Set-Cookie'];self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie);self.assertIn('Max-Age=28800',cookie)
 def test_expired_session(self):
  token=self.cookies['employee'].split('=',1)[1]
  server.SESSION_TIMES[token]=0
  self.assertEqual(self.call('bootstrap')[0],403)
 def test_public_deployment_refuses_ephemeral_database(self):
  with patch.dict(os.environ,dict(EACC_PUBLIC_DEPLOYMENT='1'),clear=True):
   with self.assertRaises(RuntimeError):server.check_deployment()
 def test_storage_upload_private_download(self):
  raw=b'%PDF-1.4\nEvidence test';response=Mock(status_code=200,content=raw)
  with patch.dict(os.environ,dict(SUPABASE_URL='https://test-project.supabase.co',SUPABASE_SERVICE_ROLE_KEY='test-server-only-key')),patch('blob_store.requests.request',return_value=response) as request:
   status,r=self.call('files',dict(name='receipt.pdf',mime='application/pdf',content=base64.b64encode(raw).decode()));self.assertEqual(status,200,r)
   with server.connection() as c:self.assertIsNone(c.execute('SELECT content FROM files WHERE id=?',(r['id'],)).fetchone()[0])
   with urlopen(Request(self.base+'/api/files/'+r['id'],headers={'Cookie':self.cookies['employee']})) as download:self.assertEqual(download.read(),raw)
   self.assertEqual([x.args[0] for x in request.call_args_list],['POST','GET'])
   self.assertFalse(request.call_args.kwargs['allow_redirects'])
 def test_storage_failure_does_not_commit_metadata(self):
  raw=b'%PDF-1.4\nEvidence test'
  with patch.dict(os.environ,dict(SUPABASE_URL='https://test-project.supabase.co',SUPABASE_SERVICE_ROLE_KEY='test-key')),patch('blob_store.requests.request',return_value=Mock(status_code=403,content=b'')):
   self.assertEqual(self.call('files',dict(name='receipt.pdf',mime='application/pdf',content=base64.b64encode(raw).decode()))[0],500)
   with server.connection() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM files').fetchone()[0],0)
 def test_database_failure_removes_new_storage_object(self):
  raw=b'%PDF-1.4\nEvidence test'
  with patch.dict(os.environ,dict(SUPABASE_URL='https://test-project.supabase.co',SUPABASE_SERVICE_ROLE_KEY='test-key')),patch('blob_store.requests.request',return_value=Mock(status_code=200,content=b'')) as request,patch('server.audit',side_effect=RuntimeError('test rollback')):
   self.assertEqual(self.call('files',dict(name='receipt.pdf',mime='application/pdf',content=base64.b64encode(raw).decode()))[0],500)
   self.assertEqual([x.args[0] for x in request.call_args_list],['POST','DELETE'])
   with server.connection() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM files').fetchone()[0],0)
 def test_storage_redirect_rejected(self):
  with patch.dict(os.environ,dict(SUPABASE_URL='https://test-project.supabase.co',SUPABASE_SERVICE_ROLE_KEY='test-key')),patch('blob_store.requests.request',return_value=Mock(status_code=302)):
   with self.assertRaises(RuntimeError):blob_store.download('a'*24)
if __name__=='__main__':unittest.main(verbosity=2)
