"""Optional CODEF sandbox probe using the official SDK's public sandbox mode.
No customer credentials or live-card collection are accepted by this adapter.
"""
import json, os, subprocess, sys
PRODUCT='/v1/kr/card/b/account/approval-list'
def probe_codef():
 try:
  result=subprocess.run([sys.executable,__file__,'--worker'],capture_output=True,text=True,timeout=30,check=False)
  if result.returncode!=0:return dict(status='failed',message='CODEF SDK 또는 샌드박스 네트워크 연결을 확인하세요. 토큰·인증 응답은 로그에 노출하지 않습니다.')
  output=json.loads(result.stdout)
  return output
 except subprocess.TimeoutExpired:return dict(status='failed',message='CODEF 샌드박스 응답이 30초 안에 도착하지 않았습니다.')
 except (ValueError,OSError):return dict(status='failed',message='CODEF 샌드박스 응답 형식을 확인할 수 없습니다.')
def worker():
 try:
  from easycodefpy import Codef,ServiceType
 except ImportError:
  return dict(status='not_installed',message='공식 SDK easycodefpy==1.0.1 설치가 필요합니다.')
 import datetime as dt
 public_key=os.environ.get('CODEF_PUBLIC_KEY','')
 if not public_key:return dict(status='not_configured',message='공식 CODEF SDK는 공개 샌드박스에도 발급된 RSA 공개키를 요구합니다. CODEF_PUBLIC_KEY를 환경 설정에 등록하세요. 외부 카드 API 테스트는 아직 미실행입니다.')
 codef=Codef();codef.public_key=public_key
 # All identifiers here are non-customer sandbox examples. Live/demo mode is never used.
 day=dt.date.today().strftime('%Y%m%d')
 try:
  raw=codef.request_product(PRODUCT,ServiceType.SANDBOX,dict(organization='0306',connectedId='SANDBOX-ONLY',startDate=day,endDate=day,orderBy='0',inquiryType='1'))
  response=json.loads(raw) if isinstance(raw,str) else raw
  result=response.get('result',{})
  code=str(result.get('code','unknown'))
  ok=code=='CF-00000'
  return dict(status='connected' if ok else 'failed',provider='CODEF',mode='sandbox',product=PRODUCT,result_code=code,message='CODEF 고정 응답 샌드박스 요청 성공. 실카드 연동이나 데이터 수집 완료를 의미하지 않습니다.' if ok else 'CODEF SDK가 실패 결과를 반환했습니다. 외부 응답 여부, 상품 경로·필수 파라미터를 공식 문서와 대조해야 합니다.')
 except Exception:return dict(status='failed',message='CODEF 샌드박스 요청에 실패했습니다. 네트워크 정책 또는 SDK 지원 여부를 확인하세요.')
if __name__=='__main__':print(json.dumps(worker(),ensure_ascii=False))
