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


## 실물증빙 저장·조회 오류 대응

보고된 `저장소 연결을 확인하세요.`는 기존 GET 예외 처리에서만 출력되며, 전표 저장창 하단에 표시됐다면 저장 POST 성공 뒤 bootstrap 재조회가 실패하는 흐름과 일치합니다. 실제 배포 DB의 실패 원인은 아직 확인하지 못했습니다.

- KTX PNG(1,611,818 bytes)로 기존 화면에서 금액 입력 후 분개가 0원으로 남는 별도 문제를 재현하고 수정했습니다. 자동 분개는 금액·계정·세금 변경을 반영하고 직접 수정한 분개는 보존합니다.
- 저장 POST 성공과 이후 화면 조회 실패를 구분합니다. 저장된 전표번호를 표시하고 재조회만 가능하게 하여 같은 전표를 중복 작성하지 않도록 했습니다.
- 첨부 업로드 진행/성공/실패를 첨부 영역에 지속 표시합니다. 업로드 미완료 상태의 실물증빙 저장을 차단합니다.
- Storage 응답을 안전한 고정 오류 코드로 구분하고, 조회 실패 로그에는 비밀값 대신 요청 구분·오류 종류·앱 코드 위치를 기록합니다.
- 39개 통합·보안 테스트 통과. 실제 TLS PostgreSQL과 KTX PNG를 사용한 브라우저 검증에서 저장·원본 다운로드·조회 실패 후 중복 방지·수동 분개 보존·업로드 실패 표시가 통과했습니다. Storage HTTP는 스텁이며 실제 Supabase 계정은 사용하지 않았습니다.
- 재현: `EACC_TEST_EVIDENCE_IMAGE=/path/to/demo.png python3 tests/browser_evidence.py` (Playwright/Chromium 필요). 기본은 임시 SQLite이며 로컬 전용 TLS PG 설정 파일을 EACC_EVIDENCE_TEST_DB_CONFIG로 지정할 수 있습니다.
- 기존 전표와 첨부를 삭제하거나 실제 SAP 전기를 수행하지 않았습니다. 실제 배포 서비스 오류 해소는 재배포 후 확인해야 합니다.


## 결재 상신 모달 오류·상태 갱신 개선

- 브라우저의 native dialog 최상위 레이어 때문에 body toast가 상세창 뒤에 가려지는 문제를 수정했습니다. 열린 창 안에 지속되는 알림을 표시하며 메시지를 HTML로 해석하지 않습니다.
- 상신·승인·회수·반려·모의전기의 서버 응답으로 전표 상태를 즉시 반영합니다. 이후 전체 목록 조회가 실패해도 성공한 처리가 실패처럼 보이지 않도록 전체 bootstrap 재조회에 의존하지 않습니다.
- 작성중/반려 전표 상세에 결재선 선택을 표시하고 팀장 자동 설정 여부를 안내합니다. 상신 중 중복 클릭을 차단하며, 명시적 결재자 지정이 필요할 때 창 안에서 안내합니다.
- 단건 상태 조회 API는 전표 소유자·지정 결재자·ITO로 접근을 제한합니다. 늦게 온 조회 응답은 다른 사용자나 닫힌 창을 다시 열지 않습니다.
- 41개 통합·보안 테스트 통과. 실제 로컬 HTTP/브라우저 검증에서 오류가 모달 안에 유지되고, bootstrap을 의도적으로 실패시켜도 상신 완료가 결재중으로 반영되는지 확인했습니다. 결재선 자동설정 OFF 때 직접 선택, 회수·반려·재상신·승인·모의전기도 통과했습니다.
- 재현 스크립트: python3 tests/browser_approvals.py. 임시 SQLite를 사용하며 배포된 DB를 변경하지 않습니다. 실제 사용자가 받은 상신 실패의 원문은 가려져 확인하지 못했으므로 실제 서비스 결과는 재배포 후 확인해야 합니다.

## PostgreSQL 연결 초기화 경합 수정 · 2026-11-03

- 일반 연결에서 `CREATE SCHEMA`와 `REVOKE`를 제거하고 서버 `init()`에서만 실행합니다. 초기화·일반 연결 모두 동일한 트랜잭션 advisory lock을 첫 SQL로 획득합니다. 잠금은 commit/rollback 때 해제되고 `search_path`는 트랜잭션에만 적용됩니다.
- 스키마·테이블 생성은 기존 `IF NOT EXISTS`를 유지하며 데이터 삭제·재생성·이관은 하지 않습니다. 기존 전표와 증빙을 유지합니다.
- 전체 회귀 테스트: 43개 중 42개 통과, 선택적 PostgreSQL 테스트 1개 스킵. 해당 테스트는 별도 실행에서 2개 모두 통과했습니다.
- 격리된 PostgreSQL 17과 호스트명 검증을 포함한 TLS 연결에서 8개 작업자로 초기화 16회, 12개 작업자로 로그인·bootstrap 조회 48회, 초기화 추가 16회를 실행했습니다. 모든 요청이 성공하고 objects/documents/files/audit/settings 전체 행이 검증 전후 동일했습니다.
- 재현: 빈 전용 테스트 DB를 준비한 뒤 `EACC_TEST_POSTGRES_URL=postgresql://... DATABASE_SSL_ROOT_CERT=/path/to/trusted-ca.pem .runtime/venv/bin/python -m unittest discover -s tests -p test_persistence_concurrency.py -v`. 이 테스트는 전용 DB에 테스트 전표·증빙을 생성하므로 운영 DB를 지정하지 않습니다.
- 실제 배포 DB에는 접근하지 않았습니다. GitHub 반영 후 배포 서비스 재배포와 실제 로그인 조회 확인은 별도입니다.
