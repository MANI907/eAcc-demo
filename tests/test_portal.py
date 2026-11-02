import base64, copy, json, os, sys, tempfile, threading, unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from integrations import probe_sap,journal_xml
class PortalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();server.DB=Path(cls.temp.name)/'test.db';server.init()
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base='http://127.0.0.1:'+str(cls.http.server_port)
  cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
 def setUp(self):
  with server.connection() as c:
   for k in ['documents','files','audit']:c.execute('DELETE FROM '+k)
   c.execute("DELETE FROM objects WHERE kind IN ('delegations','unlocks','vendor_requests')")
   tx=server.obj(c,'TX-0005');tx['locked']=True;server.save_obj(c,tx)
   c.execute('UPDATE settings SET data=?',(json.dumps(dict(favorites=True,notifications=True,auto_manager=True,dashboard=True,refresh_version=1)),))
  self.cookies={}
  for role in server.USERS:
   r=urlopen(Request(self.base+'/api/login',data=json.dumps(dict(role=role)).encode(),headers={'Content-Type':'application/json'}));self.cookies[role]=r.headers['Set-Cookie'].split(';')[0]
 def call(self,path,body=None,role='employee',origin=None):
  headers={'Cookie':self.cookies[role],'Content-Type':'application/json'}
  if origin:headers['Origin']=origin
  req=Request(self.base+'/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
  try:
   with urlopen(req) as r:return r.status,json.loads(r.read())
  except HTTPError as e:return e.code,json.loads(e.read())
 def payload(self,**updates):
  d=dict(kind='card',source_id='TX-0001',title='교통비 전표',date=server.today(),posting_date=server.today(),company='1000',cost_center='110370',wbs='ENERGY-2026-01',account='610200',tax_code='EXEMPT',amount=59800,vat=0,lines=[dict(account='610200',debit=59800,credit=0),dict(account='211100',debit=0,credit=59800)],vendor='V1000',attachments=[],approvers=[])
  d.update(updates);return d
 def make(self,**updates):
  status,d=self.call('documents',self.payload(**updates));self.assertEqual(status,200,d);return d['id']
 def approve(self,id):
  self.assertEqual(self.call(f'documents/{id}/submit',{})[0],200)
  status,d=self.call(f'documents/{id}/approve',{},'manager');self.assertEqual(status,200,d)
 def test_full_workflow_and_idempotent_simulation(self):
  id=self.make();self.approve(id)
  self.assertEqual(self.call(f'documents/{id}/post',{},'employee')[0],403)
  status,d=self.call(f'documents/{id}/post',{},'ito');self.assertEqual(status,200);self.assertEqual(d['state'],'posted');self.assertTrue(d['sap_reference'].startswith('SIM-'))
  self.assertEqual(self.call(f'documents/{id}/post',{},'ito')[1]['sap_reference'],d['sap_reference'])
  self.assertEqual(len(self.call('audit',role='ito')[1]),4)
 def test_document_read_is_scoped_and_shows_committed_approval(self):
  id=self.make()
  self.assertEqual(self.call('documents/'+id)[0],200)
  self.assertEqual(self.call('documents/'+id,role='manager')[0],403)
  self.call(f'documents/{id}/submit',{})
  self.assertEqual(self.call('documents/'+id,role='manager')[1]['state'],'submitted')
 def test_submit_requires_explicit_approver_when_auto_disabled(self):
  id=self.make();self.call('settings',dict(auto_manager=False),'ito')
  self.assertEqual(self.call(f'documents/{id}/submit',{})[0],400)
  status,r=self.call(f'documents/{id}/submit',dict(approvers=['E1002']))
  self.assertEqual(status,200);self.assertEqual(r['approvers'],['E1002'])
 def test_unbalanced_journal_is_rejected(self):
  p=self.payload();p['lines'][1]['credit']-=1;status,r=self.call('documents',p);self.assertEqual(status,400);self.assertIn('차변',r['error'])
 def test_source_amount_immutable_and_duplicate_prevented(self):
  self.make();self.assertEqual(self.call('documents',self.payload())[0],400)
  self.assertEqual(self.call('documents',self.payload(source_id='TX-0002',amount=1))[0],400)
 def test_reject_reason_and_resubmit(self):
  id=self.make();self.call(f'documents/{id}/submit',{})
  self.assertEqual(self.call(f'documents/{id}/reject',{},'manager')[0],400)
  self.assertEqual(self.call(f'documents/{id}/reject',dict(reason='계정 확인'), 'manager')[1]['state'],'rejected')
  self.assertEqual(self.call(f'documents/{id}/submit',{})[1]['state'],'submitted')
 def test_employee_cannot_self_approve_or_edit_posted(self):
  id=self.make();self.call(f'documents/{id}/submit',{})
  self.assertEqual(self.call(f'documents/{id}/approve',{})[0],403)
  self.assertEqual(self.call('documents',self.payload(id=id))[0],400)
 def test_owner_scope_and_delegation_revocation(self):
  self.assertEqual(len(self.call('bootstrap',role='manager')[1]['transactions']),0)
  status,r=self.call('delegations',dict(card='CARD-001',delegate='E1002',start=server.today(),end=server.today()));self.assertEqual(status,200)
  self.assertGreater(len(self.call('bootstrap',role='manager')[1]['transactions']),0)
  self.assertEqual(self.call('delegations/revoke',dict(id=r['id']))[0],200)
  self.assertEqual(len(self.call('bootstrap',role='manager')[1]['transactions']),0)
 def test_locked_card_requires_independent_approval(self):
  self.assertEqual(self.call('documents',self.payload(source_id='TX-0005'))[0],400)
  status,r=self.call('unlocks',dict(transaction='TX-0005',reason='증빙 지연'));self.assertEqual(status,200)
  self.assertEqual(self.call('unlocks/approve',dict(id=r['id']))[0],403)
  self.assertEqual(self.call('unlocks/approve',dict(id=r['id']),'manager')[0],200)
 def test_sequential_approval_and_no_withdraw_after_first(self):
  id=self.make(approvers=['E1002','E1003']);self.call(f'documents/{id}/submit',{})
  self.assertEqual(self.call(f'documents/{id}/approve',{},'ito')[0],403)
  self.assertEqual(self.call(f'documents/{id}/approve',{},'manager')[1]['state'],'submitted')
  self.assertEqual(self.call(f'documents/{id}/withdraw',{})[0],400)
  self.assertEqual(self.call(f'documents/{id}/approve',{},'ito')[1]['state'],'approved')
 def test_advance_and_over_settlement(self):
  p=self.payload(kind='advance_employee',source_id='',account='136000',lines=[dict(account='136000',debit=59800,credit=0),dict(account='211100',debit=0,credit=59800)])
  status,r=self.call('documents',p);self.assertEqual(status,200,r);id=r['id'];self.approve(id)
  p=self.payload(kind='settle_employee',source_id='',advance_id=id,lines=[dict(account='610200',debit=59800,credit=0),dict(account='136000',debit=0,credit=59800)])
  status,r=self.call('documents',p);self.assertEqual(status,200,r)
  self.assertEqual(self.call('documents',p)[0],400)
 def test_trip_limit_enforced(self):
  p=self.payload(kind='trip_card',trip_id='TRIP-001',expense_category='meal')
  status,r=self.call('documents',p);self.assertEqual(status,400);self.assertIn('한도',r['error'])
 def test_evidence_required_and_mime_checked(self):
  self.assertEqual(self.call('documents',self.payload(kind='physical',source_id=''))[0],400)
  self.assertEqual(self.call('files',dict(name='fake.pdf',mime='application/pdf',content=base64.b64encode(b'not a pdf').decode()))[0],400)
  status,r=self.call('files',dict(name='receipt.pdf',mime='application/pdf',content=base64.b64encode(b'%PDF-1.4\nlocal test').decode()));self.assertEqual(status,200)
  self.assertEqual(self.call('documents',self.payload(kind='physical',source_id='',attachments=[r['id']]))[0],200)
 def test_tax_control_rule(self):
  p=self.payload(kind='invoice',source_id='INV-001',amount=1100000,vat=100000,tax_code='VAT10',account='610300',lines=[dict(account='610300',debit=1000000,credit=0),dict(account='135100',debit=100000,credit=0),dict(account='211100',debit=0,credit=1100000)])
  status,r=self.call('documents',p);self.assertEqual(status,400);self.assertIn('통제',r['error'])
 def test_vendor_approval_and_self_approval_denied(self):
  status,r=self.call('vendors',dict(name='테스트 공급업체',business_number='1234567890',type='법인'));self.assertEqual(status,200)
  self.assertEqual(self.call('vendors/approve',dict(id=r['id']))[0],403)
  self.assertEqual(self.call('vendors/approve',dict(id=r['id']),'manager')[1]['status'],'승인완료')
 def test_ito_only_settings_and_csrf_origin(self):
  self.assertEqual(self.call('settings',dict(dashboard=False))[0],403)
  self.assertEqual(self.call('settings',dict(dashboard=False),'ito')[1]['dashboard'],False)
  self.assertEqual(self.call('settings',dict(dashboard=True),'ito',origin='https://attacker.example')[0],403)
 def test_sap_not_configured_is_not_success(self):
  with patch.dict(os.environ,{},clear=True):
   r=probe_sap();self.assertEqual(r['status'],'not_configured')
 def test_sap_wsdl_only_allowed_https_host(self):
  with patch.dict(os.environ,dict(SAP_JOURNAL_WSDL_URL='https://other.example/?wsdl',SAP_ALLOWED_HOST='tenant.example',SAP_AUTHORIZATION='Basic local-test')):
   with self.assertRaises(ValueError):probe_sap()
 def test_sap_wsdl_semantics_and_basic_header(self):
  from integrations import NoRedirect
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,*args):return b'<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"/>'
  class Opener:
   def open(self,req,timeout):
    assert req.get_header('Authorization')=='Basic local-test';return Response()
  with patch.dict(os.environ,dict(SAP_JOURNAL_WSDL_URL='https://tenant.example/service?wsdl',SAP_ALLOWED_HOST='tenant.example',SAP_AUTHORIZATION='Basic local-test')),patch('urllib.request.build_opener',return_value=Opener()):
   self.assertEqual(probe_sap()['status'],'connected')
 def test_journal_payload_is_xml_escaped_and_requires_mapping(self):
  d=self.payload();d['id']='EA-TEST';d['title']='교통비 & <검토>'
  xml=journal_xml(d,'1000','1000000',{'610200':'0061020000'})
  self.assertIn(b'&amp;',xml);self.assertIn(b'CreditorItem',xml)
  with self.assertRaises(ValueError):journal_xml(dict(d,vat=1),'1000','1000000',{'610200':'0061020000'})
if __name__=='__main__':unittest.main(verbosity=2)
