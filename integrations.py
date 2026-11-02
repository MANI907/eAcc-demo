"""SAP_COM_0002 read-only connectivity. No legacy RFC or credentials in browser."""
import os, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def probe_sap():
 url=os.environ.get('SAP_JOURNAL_WSDL_URL','')
 authorization=os.environ.get('SAP_AUTHORIZATION','')
 if not url or not authorization:
  return dict(status='not_configured',message='SAP_JOURNAL_WSDL_URL과 SAP_AUTHORIZATION(Basic 인증 헤더)이 필요합니다. 실제 SAP 연결 테스트는 미실행입니다.')
 p=urlparse(url);host=os.environ.get('SAP_ALLOWED_HOST','')
 if p.scheme!='https' or p.hostname!=host or p.username or p.password or p.port not in [None,443] or p.fragment or ('wsdl' not in (p.query+p.path).lower()):
  raise ValueError('SAP_ALLOWED_HOST와 일치하는 HTTPS WSDL URL만 허용합니다. Communication Arrangement의 실제 서비스 WSDL 주소를 입력하세요.')
 if '\r' in authorization or '\n' in authorization:raise ValueError('인증 헤더에 줄바꿈을 포함할 수 없습니다.')
 # Forward proxy-backed bindings unchanged; a placeholder is not a missing credential.
 request=urllib.request.Request(url,headers={'Authorization':authorization,'Accept':'text/xml, application/wsdl+xml'})
 try:
  opener=urllib.request.build_opener(NoRedirect())
  with opener.open(request,timeout=20) as response:
   raw=response.read(2*1024*1024+1);status=response.status
  if len(raw)>2*1024*1024:return dict(status='unexpected_response',http_status=status,message='WSDL 응답 크기가 검사 한도를 초과했습니다.')
  try:
   root=ET.fromstring(raw);valid=root.tag in ['{http://schemas.xmlsoap.org/wsdl/}definitions','{http://www.w3.org/ns/wsdl}description']
  except ET.ParseError:valid=False
  return dict(status='connected' if valid else 'unexpected_response',http_status=status,wsdl_valid=valid,message='SOAP WSDL 조회 성공. 실제 전표 전기와 SAP 업무 검증은 아직 수행하지 않았습니다.' if valid else 'HTTP 응답은 수신했지만 유효한 WSDL이 아닙니다.')
 except urllib.error.HTTPError as e:
  return dict(status='failed',http_status=e.code,message='SAP 인증·권한·WSDL 경로를 확인하세요. 리다이렉트는 인증정보 보호를 위해 따르지 않습니다.')
 except (urllib.error.URLError,TimeoutError):
  return dict(status='failed',message='SAP 네트워크, 테넌트 호스트 또는 TLS 인증서를 확인하세요.')

def journal_xml(document,company_code,creditor_id,gl_mapping):
 """Reviewable SAP journal payload; not sent. Tenant mapping + WSDL validation required."""
 if not company_code or not creditor_id:raise ValueError('SAP 회사코드와 공급업체 매핑이 필요합니다.')
 if document['kind'].startswith(('advance_','settle_')):raise ValueError('특별 G/L 선급·정산은 테넌트별 매핑을 먼저 검증해야 합니다.')
 if document.get('vat',0):raise ValueError('부가세 세금코드와 ProductTaxItem 매핑을 먼저 검증해야 합니다.')
 uri='http://sap.com/xi/SAPSCORE/SFIN';ns='http://schemas.xmlsoap.org/soap/envelope/'
 ET.register_namespace('soapenv',ns);ET.register_namespace('sfin',uri)
 root=ET.Element('{'+ns+'}Envelope');body=ET.SubElement(root,'{'+ns+'}Body');bulk=ET.SubElement(body,'{'+uri+'}JournalEntryBulkCreateRequest')
 import datetime as dt
 stamp=dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
 def add(parent,name,value):ET.SubElement(parent,name).text=str(value)
 header=ET.SubElement(bulk,'MessageHeader');add(header,'ID',document['id']);add(header,'CreationDateTime',stamp)
 entry=ET.SubElement(bulk,'JournalEntryCreateRequest');header=ET.SubElement(entry,'MessageHeader');add(header,'ID',document['id']);add(header,'CreationDateTime',stamp)
 journal=ET.SubElement(entry,'JournalEntry')
 for k,v in [('OriginalReferenceDocumentType','BKPFF'),('BusinessTransactionType','RFBU'),('AccountingDocumentType','KR'),('DocumentReferenceID',document['id'][-16:]),('DocumentHeaderText',document['title'][:25]),('CreatedByUser','EACC'),('CompanyCode',company_code),('DocumentDate',document['date']),('PostingDate',document['posting_date'])]:add(journal,k,v)
 for i,line in enumerate(document['lines'],1):
  if line['debit']:
   mapped=gl_mapping.get(line['account'])
   if not mapped:raise ValueError('SAP G/L 계정 매핑이 없습니다: '+line['account'])
   item=ET.SubElement(journal,'Item');add(item,'ReferenceDocumentItem',i);add(item,'GLAccount',mapped);amount=ET.SubElement(item,'AmountInTransactionCurrency',currencyCode='KRW');amount.text=str(line['debit']);add(item,'DebitCreditCode','S');assignment=ET.SubElement(item,'AccountAssignment');add(assignment,'CostCenter',document['cost_center'])
  else:
   item=ET.SubElement(journal,'CreditorItem');add(item,'ReferenceDocumentItem',i);add(item,'Creditor',creditor_id);amount=ET.SubElement(item,'AmountInTransactionCurrency',currencyCode='KRW');amount.text=str(-line['credit']);add(item,'DebitCreditCode','H')
 return ET.tostring(root,encoding='utf-8',xml_declaration=True)
