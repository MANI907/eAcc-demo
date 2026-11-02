# eAcc 회계포탈

기존 UniDOCU WAR와 제공된 업무 명세를 참고해 새로 작성한 **로컬 동작 데모**입니다. Python 3.12 + SQLite + HTML/CSS/JavaScript로 실행됩니다. 외부 JavaScript CDN이나 기존 RealGrid/ActiveX/SAP JCo가 필요하지 않습니다.

```sh
cd /workspace/eAcc-demo
sh tools/setup.sh
.runtime/venv/bin/python server.py
```

기본 포트는 8000이며 루프백에 바인딩됩니다. 로그인 화면에서 일반 사용자(김하늘), 결재자(박서준), ITO 회계 관리자(이서연)를 선택합니다. 이 역할 선택은 데모용이며 운영 인증이 아닙니다. 사용자 간 권한 검사는 서버 세션에서 수행합니다.

- 일반 사용자: 법인카드 승인내역 1건 선택 → 전표 작성 → 저장 → 상세에서 결재 상신.
- 결재자: 결재관리 → 해당 전표 상세 → 승인 또는 사유를 입력해 반려.
- ITO: 승인된 전표 상세 → **SAP 모의전기**. `SIM-` 번호는 실제 SAP 전표번호가 아닙니다.
- 실물증빙은 PDF/PNG/JPEG 첨부가 필요합니다. 출장비는 출장 선택과 식비/숙박비 한도 검증을 수행합니다.
- 전도금·선급금은 승인 후 동일 유형 정산이 가능하며 초과정산을 차단합니다.
- ITO 설정과 F8 디버그, 카드등록, 통제규칙, 공지·매뉴얼, 감사이력을 제공합니다.

DB와 증빙은 `.runtime/portal.db`에 보관합니다. 파일이나 DB를 삭제하면 로컬 업무 데이터가 사라집니다. 소스 저장소에 고객 인증정보·원본 WAR·기존 라이선스를 복사하지 않았습니다.

```sh
.runtime/venv/bin/python -m unittest discover -s tests -v
# 실행 중인 로컬 서버 + 환경에 제공된 Playwright/Chromium 필요
python3 tests/browser_smoke.py
```

첫 명령은 임시 DB에서 HTTP 통합 테스트를 실행합니다. 브라우저 검증은 로컬 DB에 가상 전표 1건을 생성·상신·승인·모의전기하고 전체 메뉴를 방문합니다. 재실행 시 다른 미처리 승인내역을 사용합니다.

SAP 및 CODEF 연결 조건, 정확한 구현 범위는 [구현 현황](docs/implementation.md), 역공학 증거는 [REA 분석 요약](docs/rea-summary.json), 전체 메뉴 매핑은 [메뉴 목록](docs/menu-coverage.md)을 참고하세요.

각 클라우드 작업은 이미 격리되어 있습니다. 기존 체크아웃을 사용하며 별도 요청 없이 Git worktree를 만들지 않습니다.

## 무료 데모 배포

Render Free + Supabase PostgreSQL/비공개 Storage를 지원하는 [배포 가이드](docs/free-deployment.md)와 [Blueprint 설정](render.yaml)을 추가했습니다. DATABASE_URL이 없으면 기존 로컬 SQLite를 사용합니다. 외부 공개 모드에서는 DB·Storage·접속코드가 모두 필요합니다. SAP 인증정보는 배포 후 Render 서버 환경변수에 등록할 수 있습니다. 실제 외부 배포는 아직 수행하지 않았습니다.

[Render Free Blueprint로 배포](https://render.com/deploy?repo=https://github.com/MANI907/eAcc-demo)

Supabase 연결 문자열은 프로젝트 상단 **Connect → Type: URI → Method: Session pooler**에서 복사합니다. `Direct connection` 기본값을 변경해야 표시될 수 있습니다. 무료 Shared Pooler를 사용하며 Dedicated Pooler는 필요하지 않습니다. DB 비밀번호와 서버 키는 Render 환경변수에만 저장하세요.
