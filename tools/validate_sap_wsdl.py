"""Offline XSD validation against the user-supplied SAP tenant WSDL. Sends no requests.
Requires lxml (available in the current cloud's system Python).
All values below are fictional schema-validation examples, not verified SAP master data.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lxml import etree as E
from integrations import journal_xml
root=Path(__file__).resolve().parents[1]
parser=E.XMLParser(resolve_entities=False,no_network=True)
wsdl=E.parse(str(root/'docs/wsdl/journal-entry.wsdl'),parser)
schema=E.XMLSchema(wsdl.find('.//{http://www.w3.org/2001/XMLSchema}schema'))
document=dict(id='EA-TEST-001',kind='card',title='연동 검증용 교통비',date='2026-11-02',posting_date='2026-11-02',cost_center='110370',vat=0,lines=[dict(account='610200',debit=10000,credit=0),dict(account='211100',debit=0,credit=10000)])
envelope=E.fromstring(journal_xml(document,'1000','1000000',{'610200':'0061020000'}),parser)
schema.assertValid(envelope.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')[0])
print('PASS: generated tax-free expense payload validates against supplied WSDL/XSD. No SAP request sent.')
