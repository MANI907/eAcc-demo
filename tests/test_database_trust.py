"""Verify provider trust provisioning and real TLS handshakes without Supabase secrets."""
import datetime as dt,os,sys,ssl,socket,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import database_trust as trust
from database_diagnostics import DatabaseConfigError

def certificate(key,issuer=None,issuer_key=None,ca=True,expired=False):
 name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Local acceptance CA' if ca else 'localhost')]);now=dt.datetime.now(dt.timezone.utc)
 builder=x509.CertificateBuilder().subject_name(name).issuer_name(issuer.subject if issuer else name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(days=2)).not_valid_after(now-dt.timedelta(days=1) if expired else now+dt.timedelta(days=2)).add_extension(x509.BasicConstraints(ca=ca,path_length=None),critical=True)
 if not ca:builder=builder.add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False)
 return builder.sign(issuer_key or key,hashes.SHA256())
def pem(cert):return cert.public_bytes(serialization.Encoding.PEM)
class TrustTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048);cls.root=certificate(cls.key)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.env=patch.dict(os.environ,{'DATABASE_SSL_ROOT_CERT':''});self.env.start();self.addCleanup(self.env.stop)
  self.cache=patch.object(trust,'CACHE',Path(self.temp.name)/'cache');self.cache.start();self.addCleanup(self.cache.stop)
 def test_official_download_uses_verified_https_without_redirects(self):
  response=Mock();response.geturl.return_value=trust.OFFICIAL_CA_URL;response.read.return_value=pem(self.root)
  opener=Mock();opener.open.return_value.__enter__=Mock(return_value=response);opener.open.return_value.__exit__=Mock(return_value=False)
  with patch('database_trust.urllib.request.build_opener',return_value=opener) as build:
   self.assertEqual(trust.download_ca(),pem(self.root))
   handlers=build.call_args.args;context=next(h._context for h in handlers if isinstance(h,trust.urllib.request.HTTPSHandler))
   self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED);self.assertTrue(context.check_hostname)
   self.assertTrue(any(isinstance(h,trust.NoRedirect) for h in handlers))
 def test_download_failure_never_uses_unverified_fallback(self):
  with patch('database_trust.urllib.request.build_opener',side_effect=OSError('network blocked')):
   with self.assertRaises(DatabaseConfigError) as result:trust.resolve_ca('aws-example.pooler.supabase.com')
   self.assertEqual(result.exception.code,'DB_CA_DOWNLOAD_FAILED')
 def test_leaf_expired_and_non_certificate_payloads_rejected(self):
  for value in [b'<html>error</html>',pem(certificate(self.key,ca=False)),pem(certificate(self.key,expired=True)),pem(self.root)+pem(self.root)]:
   with self.subTest(kind='invalid provider response'),self.assertRaises(DatabaseConfigError):trust.validate_ca(value)
 def test_provider_certificate_cached_and_system_roots_preserved(self):
  with patch('database_trust.download_ca',return_value=pem(self.root)) as download:
   path=Path(trust.resolve_ca('aws-example.pooler.supabase.com'));trust.resolve_ca('aws-example.pooler.supabase.com')
   download.assert_called_once();combined=path.read_bytes();self.assertIn(pem(self.root),combined);self.assertIn(trust.SYSTEM_CA.read_bytes().strip(),combined)
 def test_explicit_ca_and_other_hosts_do_not_download(self):
  with patch('database_trust.download_ca') as download:
   self.assertEqual(trust.resolve_ca('localhost'),str(trust.SYSTEM_CA))
   with patch.dict(os.environ,{'DATABASE_SSL_ROOT_CERT':str(trust.SYSTEM_CA)}):self.assertEqual(trust.resolve_ca('aws-example.pooler.supabase.com'),str(trust.SYSTEM_CA))
   download.assert_not_called()
 def test_real_tls_handshake_succeeds_and_wrong_hostname_is_rejected(self):
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048);leaf=certificate(key,issuer=self.root,issuer_key=self.key,ca=False)
  directory=Path(self.temp.name);(directory/'server.crt').write_bytes(pem(leaf));(directory/'server.key').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
  context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(str(directory/'server.crt'),str(directory/'server.key'))
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2);listener.settimeout(5)
  def serve():
   try:
    for _ in range(2):
     client,_=listener.accept()
     try:
      with context.wrap_socket(client,server_side=True) as secured:secured.sendall(b'ok')
     except ssl.SSLError:client.close()
   finally:listener.close()
  worker=threading.Thread(target=serve,daemon=True);worker.start()
  with patch('database_trust.download_ca',return_value=pem(self.root)):
   bundle=trust.resolve_ca('aws-example.pooler.supabase.com')
  client=ssl.create_default_context(cafile=bundle)
  with socket.create_connection(('127.0.0.1',listener.getsockname()[1]),timeout=5) as raw:
   with client.wrap_socket(raw,server_hostname='localhost') as secured:self.assertEqual(secured.recv(2),b'ok')
  with socket.create_connection(('127.0.0.1',listener.getsockname()[1]),timeout=5) as raw:
   with self.assertRaises(ssl.SSLCertVerificationError):client.wrap_socket(raw,server_hostname='wrong.example')
  worker.join(5);self.assertFalse(worker.is_alive())
if __name__=='__main__':unittest.main(verbosity=2)
