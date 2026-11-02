# 검증 기록 · 2026-11-02

- Python HTTP 통합 테스트: **18개 통과**, 실패/스킵 0개. 임시 SQLite DB와 실제 HTTP 서버를 사용했습니다.
- Chromium 업무 검증: **34개 PROGRAM ID 화면 방문 통과**. 일반 사용자 저장·상신 → 결재자 승인 → ITO 모의전기까지 검증했습니다. `SIM-` 참조와 전기완료 상태를 확인했습니다.
- ITO F8 디버그, 390px 모바일 메뉴 및 법인카드 화면: 통과. JavaScript pageerror 0개.
- 역할 전환 후 기존 화면이 남던 오류를 수정하고 브라우저 흐름을 재실행했습니다.
- 예산 화면의 코스트센터/계정 컬럼 표시를 추가 검증했습니다.
- 설치 스크립트 반복 실행, Python 컴파일, JavaScript 문법 검사: 통과.
- 기존 energy-eAcc 체크아웃: tracked/untracked 변경 없음. 새 구현은 eAcc-demo에 저장했습니다. 저장된 저장소 선택은 변경하지 않았습니다.
- REA 정적 분석: 애플리케이션 JavaScript 39개 파싱 성공, 실패 0개. JSP/ABAP/실제 기존 시스템의 동적 동등성 검증은 별도입니다.
- 실제 SAP: **미실행**. WSDL URL과 Basic 인증 바인딩이 없고 API 호스트의 네트워크 요청은 프록시 403으로 차단됐습니다. 모의전기는 실제 SAP 성공 증거가 아닙니다.
- CODEF: **외부 상품 성공 응답 미확인**. SDK의 로컬 RSA 공개키 미설정 오류를 확인하고 not_configured로 구분했습니다. 발급 공개키와 네트워크 적용 후 재검사가 필요합니다.
- 환경 초안 저장 성공. install_script/start_skill/연동 요구사항/허용 도메인을 저장했으나 게시 및 새 작업 복원은 검증하지 않았습니다.

브라우저 결과와 화면은 `.runtime/browser-results.json`, `.runtime/dashboard.png`, `.runtime/dashboard-admin.png`, `.runtime/mobile-card.png`에 있습니다. 브라우저 검증에서 가상 전표가 생성되며 해당 상태는 데모 DB에 남습니다.

## 무료 배포 준비 검증 추가

SQLite 및 TLS 검증된 PostgreSQL에서 업무 테스트 18개와 배포 경계 테스트 7개가 모두 통과했습니다. Supabase Storage 업로드/다운로드/실패·복구는 HTTP 스텁으로 검증했으며 실제 Supabase 연결은 미실행입니다. 별도 로컬 DB와 접속코드를 사용한 Chromium 검증에서 전체 34개 메뉴·모바일·결재 흐름이 통과했고 기존 로컬 업무 데이터는 변경하지 않았습니다. SQLite → 별도 PostgreSQL 테스트 DB 이관, 원본 보존 및 비어 있지 않은 대상 거부도 확인했습니다. 실제 Render 게시·무료 플랜 가용성·Supabase 재시작 보존·SAP 연결은 미검증입니다.
