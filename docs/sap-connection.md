# 사용자 제공 SAP 서비스

- 시나리오: SAP_COM_0002
- 인증: 통신 사용자 Basic
- 사용자 제공 서비스 URL: https://my434089-api.s4hana.cloud.sap/sap/bc/srt/scs_ext/sap/journalentrycreaterequestconfi
- WSDL 후보: 위 URL에 ?wsdl 추가. 실제 WSDL 주소라는 보장은 없으며 Communication Arrangement의 WSDL 다운로드/링크와 대조가 필요합니다.
- SAP_ALLOWED_HOST 및 SAP_JOURNAL_WSDL_URL의 비밀정보가 아닌 제안값을 환경 초안에 저장했습니다. 이미 저장된 값이 있으면 자동 덮어쓰기되지 않으므로 설정에서 확인해야 합니다.
- 현재 런타임에는 SAP 인증 바인딩이 없으므로 인증된 WSDL 조회와 실제 전표 전기는 미검증입니다.

## 첨부 WSDL 검증

사용자가 제공한 WSDL 원본을 `docs/wsdl/journal-entry.wsdl`에 보관했습니다.
- PortType: JournalEntryCreateRequestConfirmation_In
- 요청: JournalEntryBulkCreateRequest
- 응답: JournalEntryBulkCreateConfirmation
- SOAP 1.1 및 SOAP 1.2 binding 모두 정의됨.
- WSDL 내부 address는 사용자 제공 서비스 URL과 일치함.
- 현재 journal_xml이 생성하는 가상 세금없음 비용/공급업체 전표 예시를 첨부된 XSD로 검증: 통과.
- 재검증: `python3 tools/validate_sap_wsdl.py` (현재 환경의 시스템 Python에 lxml 제공됨).
- 위 결과는 XML 형식 검증이며 실테넌트 마스터 유효성·인증·네트워크·실제 전기 성공을 의미하지 않음.
- `?wsdl` 온라인 경로 확인 없이도 첨부 파일로 로컬 스키마 검증 가능. 원격 WSDL 조회 검사는 여전히 별도의 연결 검증임.
