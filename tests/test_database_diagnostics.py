"""Safe startup failures must remain actionable without exposing secret-bearing errors."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database_diagnostics import DatabaseConfigError,diagnose,startup_message
import persistence
class DiagnosticsTests(unittest.TestCase):
 def test_errors_are_classified_without_echoing_sensitive_text(self):
  cases=[
   ('password authentication failed','DB_AUTH_FAILED'),
   ('Tenant or user not found','DB_POOLER_TENANT_FAILED'),
   ('could not translate host name','DB_DNS_FAILED'),
   ('Network is unreachable','DB_NETWORK_FAILED'),
   ('connection timeout expired','DB_CONNECT_TIMEOUT'),
   ('SSL error: certificate verify failed','DB_TLS_FAILED'),
   ('server certificate does not match host name','DB_TLS_HOSTNAME_FAILED'),
   ('unknown driver failure','DB_INIT_FAILED'),
  ]
  for message,code in cases:
   with self.subTest(code=code):
    error=Exception(message+' postgresql://user:NEVER-PRINT-THIS@host/db')
    self.assertEqual(diagnose(error)['code'],code)
    output=startup_message(error);self.assertNotIn('NEVER-PRINT-THIS',output);self.assertNotIn('postgresql://',output)
 def test_sqlstates_identify_database_permission_and_auth_failures(self):
  for state,expected in [('42501','DB_PERMISSION_DENIED'),('3D000','DB_DATABASE_NOT_FOUND'),('28P01','DB_AUTH_FAILED')]:
   error=Exception('sensitive raw text');error.sqlstate=state
   self.assertEqual(diagnose(error)['code'],expected);self.assertIn(state,startup_message(error))
 def test_malformed_sqlstate_is_not_logged(self):
  error=Exception('raw');error.sqlstate='credential-value'
  self.assertNotIn('credential-value',startup_message(error))
 def test_password_placeholder_and_bad_uri_rejected_before_network(self):
  for url in ['postgresql://user:[YOUR-PASSWORD]@example.com/postgres','postgresql://user:%5BYOUR-PASSWORD%5D@example.com/postgres',"postgresql://user:secret@example.com/db\n",'postgresql://broken:%zz@example.com/db']:
   with self.subTest(url_type='invalid'),patch.dict(os.environ,{'DATABASE_URL':url}),patch('psycopg.connect') as connect:
    with self.assertRaises(DatabaseConfigError):
     with persistence.connect(None):pass
    connect.assert_not_called()
 def test_tls_verification_cannot_be_disabled_by_connection_uri(self):
  with tempfile.NamedTemporaryFile() as ca:
   mocked=MagicMock()
   with patch.dict(os.environ,dict(DATABASE_URL='postgresql://user:secret@localhost/db?sslmode=disable',DATABASE_SSL_ROOT_CERT=ca.name)),patch('psycopg.connect',return_value=mocked) as connect:
    with persistence.connect(None):pass
    self.assertEqual(connect.call_args.kwargs['sslmode'],'verify-full')
    self.assertEqual(connect.call_args.kwargs['sslrootcert'],ca.name)
if __name__=='__main__':unittest.main(verbosity=2)
