# 무료 데모 배포: Render + Supabase

이 문서는 준비된 배포 설정의 실행 순서입니다. 사용자가 Supabase 프로젝트를 생성했고 프로젝트 URL은 https://cnxbptpnuihhqeirslux.supabase.co 입니다. Render 서비스 생성과 실제 DB/Storage 연결은 아직 확인하지 않았습니다. 무료 플랜 제공 여부, 휴면·사용량·프로젝트 제한은 가입 화면의 최신 조건을 확인하세요. 유료 플랜, 디스크, 추가 인스턴스, 자동 과금 옵션은 이 설정에 포함하지 않았습니다.

## 구성

- Render **Free Web Service** 하나에서 Python API와 웹 화면을 함께 실행합니다. 별도 프런트엔드 서비스·CORS 설정은 필요하지 않습니다.
- Supabase **Free Project**의 PostgreSQL에 전표·결재·감사·첨부 메타데이터를 저장합니다.
- Supabase Storage의 **비공개** `eacc-evidence` 버킷에 증빙 원문을 저장합니다. Render 임시 디스크에는 업무 데이터를 쓰지 않습니다.
- 로컬에서는 기존 SQLite가 그대로 동작합니다. 기존 `.runtime/portal.db`는 변경·삭제하거나 자동으로 원격 전송하지 않습니다.
- 외부 공개 데모는 접속코드가 필요합니다. 코드를 아는 사용자는 세 역할 모두 체험할 수 있습니다. 실제 조직별 인증/권한을 대체하지 않으므로 가상 업무 데이터로만 사용하세요.

## 1. Supabase 프로젝트 준비

https://supabase.com/dashboard 에서 무료 프로젝트를 생성합니다. 프로젝트 DB 비밀번호는 안전하게 보관하고 채팅·Git에 올리지 마세요.

프로젝트가 준비되면 다음 정보를 Render 설정에 사용할 수 있도록 확인합니다.

| Render 환경변수 | Supabase에서 확인할 항목 |
| --- | --- |
| DATABASE_URL | 상단 Connect에서 Type = URI, Method = Session pooler를 선택한 뒤 표시되는 PostgreSQL 연결 문자열입니다. 기본 Method가 Direct connection이면 그 드롭다운을 변경하세요. 무료 Shared Pooler의 Session 모드(일반적으로 5432)를 사용하며 유료 Dedicated Pooler는 필요하지 않습니다. 표시된 호스트·사용자명을 그대로 사용하고 DB 비밀번호를 채웁니다. 비밀번호 특수문자는 URL 인코딩해야 합니다. |
| SUPABASE_URL | 프로젝트의 HTTPS URL |
| SUPABASE_SERVICE_ROLE_KEY | 서버 전용 legacy service_role JWT 키. anon/publishable 키를 사용하지 마세요. 이 구현은 JWT Bearer 방식이므로 새로운 sb_secret 형식 키로 자동 대체하지 마세요. |

Storage에서 `eacc-evidence` 버킷을 **Private**으로 만드세요. 공개 버킷이나 익명 사용자 읽기/쓰기 정책은 만들지 않습니다. 필요하면 파일 한도를 5MB, 허용 MIME을 PDF/PNG/JPEG로 설정하세요.

애플리케이션이 DB에 전용 `eacc` 스키마와 테이블을 생성합니다. Supabase Data API에 `eacc` 스키마를 공개하지 마세요. Render 백엔드가 TLS 검증을 켠 PostgreSQL 연결로만 접근합니다. 기존 Supabase Auth 테이블이나 다른 프로젝트 테이블은 변경하지 않습니다.

## 2. 코드 저장소 준비

배포 설정은 저장소 루트의 `render.yaml`에 있습니다. `eAcc-demo`의 새 파일을 GitHub `MANI907/eAcc-demo`에 커밋·푸시해야 Render가 읽을 수 있습니다. GitHub 게시 여부와 정확한 커밋은 실제 git push 결과로 확인합니다.

`.runtime`, `.env`, 인증정보, 원본 고객 데이터는 업로드하지 마세요. `.env.example`은 값이 비어 있는 안내 파일입니다. 전체 Git 변경을 검토한 뒤 저장소에 반영하세요.

## 3. Render 배포

[Render에서 이 저장소로 배포](https://render.com/deploy?repo=https://github.com/MANI907/eAcc-demo) 링크를 이용하거나 https://dashboard.render.com/ 에서 Blueprint 생성 흐름으로 `MANI907/eAcc-demo`를 연결하고 루트의 `render.yaml`을 선택합니다.

- 서비스: `eacc-demo`, Python, **Free**
- 빌드: `pip install -r requirements.txt`
- 실행: `python server.py`
- 상태 검사: `/api/health`
- HOST: `0.0.0.0`, PORT는 Render가 제공
- Python: 3.12.14
- 자동 배포는 꺼져 있어 Git 푸시마다 서비스가 자동 갱신되지는 않습니다.

SUPABASE_URL은 제공받은 프로젝트 주소로 미리 설정했습니다. Render에는 DATABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 비밀 환경변수로 등록합니다. `SUPABASE_STORAGE_BUCKET=eacc-evidence`는 미리 설정돼 있습니다.

`EACC_ACCESS_CODE`는 Blueprint에서 임의 값으로 생성됩니다. 배포 담당자가 Render의 환경 설정에서 확인해 테스트 참여자에게 안전하게 공유하세요. 직접 설정할 경우 충분히 긴 무작위 값(16자 이상)을 사용합니다. 브라우저 로그인 화면의 **데모 접속코드**에 입력합니다.

필수 설정이 빠져 있으면 앱이 시작을 거부합니다. DB 연결에 실패하면 상태 검사는 503을 반환합니다. Render 로그에는 DB 연결 문자열·비밀번호를 출력하지 않습니다.

화면에서 플랜이 Free인지 확인한 뒤 배포하세요. Free를 선택할 수 없거나 결제를 요구하면 유료로 진행하지 말고 현재 조건을 다시 확인하세요. Render/Supabase의 실제 생성·배포·과금 상태는 해당 대시보드에서 확인해야 합니다.

## 4. 배포 후 확인

1. Render가 제공한 HTTPS 주소를 열어 접속코드를 입력합니다.
2. 일반 사용자로 가상 카드전표 저장·상신 → 결재자 승인 → ITO 모의전기를 수행합니다.
3. 작은 PDF/PNG/JPEG 증빙을 첨부한 실물전표를 저장하고, 증빙을 다시 다운로드합니다.
4. Render 서비스를 재시작한 뒤에도 전표와 첨부가 유지되는지 확인합니다. 세션은 메모리에 있으므로 재로그인은 정상입니다.
5. Supabase Storage 버킷이 Private이며 비로그인 사용자는 증빙에 접근할 수 없는지 확인합니다.

휴면 복귀 시 첫 접속이 느릴 수 있고 Supabase 프로젝트도 비활성 상태에 따라 중지될 수 있습니다. 무료 한도를 넘기거나 실제 회계 업무를 운영할 단계에는 백업·가용성·운영 인증을 별도로 설계해야 합니다.

## 5. SAP는 나중에 설정

지금 SAP 비밀번호를 입력할 필요는 없습니다. Render 서비스가 동작한 뒤 서버 환경변수 `SAP_AUTHORIZATION`에 전체 Basic 인증 헤더를 등록하면 됩니다. `SAP_ALLOWED_HOST`와 WSDL 후보 URL은 Blueprint에 포함돼 있습니다. 파일로 확보한 WSDL과 달리 `?wsdl` 원격 URL은 아직 검증되지 않았습니다.

브라우저용 환경변수 또는 웹 파일에는 SAP 인증정보와 Supabase service_role 키를 넣지 않습니다. 모의전기는 배포 후에도 모의전기로 남으며 실제 SAP 전기로 자동 전환되지 않습니다.

## 기존 로컬 데이터 이관 (선택)

원격 DB를 처음 시드하기 **전**, 신뢰할 수 있는 실행 환경에서 DB/Storage 환경변수를 안전하게 주입하고 다음을 실행할 수 있습니다.

```sh
.runtime/venv/bin/python tools/migrate_sqlite.py /workspace/eAcc-demo/.runtime/portal.db
```

- 원본 SQLite는 읽기 전용으로 열며 그대로 보존합니다.
- 원격 `eacc` 테이블에 이미 데이터가 있으면 덮어쓰지 않고 중단합니다. 웹 서비스를 먼저 실행하면 가상 시드가 생성되므로 이 경우 자동 이관할 수 없습니다.
- 첨부는 비공개 Storage로 복사하며 메타데이터는 PostgreSQL 트랜잭션으로 저장합니다.
- 실패하면 새로 올린 파일의 삭제를 시도합니다. 네트워크 실패로 정리가 안 되면 비공개 버킷의 고아 객체를 점검해야 합니다.
- 이관 도구는 배포 중인 Render 서버를 자동 정지하거나 원격 데이터를 지우지 않습니다. 빈 대상 프로젝트로 이관해야 합니다.

## 현재 검증 범위

- 기존 업무 HTTP 테스트 18개: SQLite 및 TLS PostgreSQL에서 통과.
- 배포 경계 테스트 7개: SQLite 및 TLS PostgreSQL에서 통과. 접속코드·Secure 쿠키·만료·스토리지 실패·DB 롤백 시 파일 정리를 확인했습니다.
- 실제 PostgreSQL 테스트는 공식 PostgreSQL 17 컨테이너와 로컬 테스트 인증서를 사용했으며 sslmode=verify-full을 유지했습니다.
- Storage 테스트는 HTTP 응답 스텁을 사용했습니다. 실제 Supabase 계정/버킷 연결은 아직 하지 않았습니다.
- 로컬 SQLite → 별도의 TLS PostgreSQL 테스트 DB 이관 및 비어 있지 않은 대상 거부를 검증했습니다. Storage 이관 부분은 스텁입니다.
- Render 실제 빌드·게시·무료 플랜 가용성·재시작 후 보존 및 실제 SAP 연결은 배포 계정 설정 후 검증해야 합니다.

공식 안내: https://render.com/docs/free · https://render.com/docs/blueprint-spec · https://supabase.com/docs/guides/database/connecting-to-postgres · https://supabase.com/docs/guides/storage/buckets/creating-buckets


## Render에서 Database initialization failed가 발생할 때

빌드 성공 후 이 문구가 나오면 DB 초기화 단계의 실패입니다. 이 단계는 Storage 또는 service_role 키를 사용하지 않습니다. 새 버전은 비밀정보나 원문 오류 대신 고정 진단 코드를 출력합니다.

| 로그 코드 | 확인할 사항 |
| --- | --- |
| DB_CONFIG_INVALID | URI만 복사했는지, 비밀번호 자리표시자 교체 및 URL 인코딩 |
| DB_DNS_FAILED | 실제 Connect 화면의 정확한 pooler 호스트 |
| DB_NETWORK_FAILED / DB_CONNECT_TIMEOUT | 무료 Shared Session pooler / 5432, 프로젝트 가동 상태 및 네트워크 제한 |
| DB_AUTH_FAILED | Supabase 계정 암호가 아닌 프로젝트 DB 암호, 복사한 사용자명 |
| DB_POOLER_TENANT_FAILED | Connect의 postgres.<project-ref> 사용자명과 실제 pooler 호스트 조합 |
| DB_TLS_FAILED / DB_CA_UNAVAILABLE | Supabase의 DB 인증서 다운로드, Render Secret File에 등록 후 DATABASE_SSL_ROOT_CERT에 파일 경로 지정 |
| DB_TLS_HOSTNAME_FAILED | Connect 화면의 실제 호스트 사용 여부 |
| DB_PERMISSION_DENIED | eacc 스키마 생성/사용 권한 및 기존 스키마 소유권 |
| DB_DATABASE_NOT_FOUND | URI의 DB 이름 (일반적으로 postgres) |
| DB_INIT_FAILED | 함께 표시된 SQLSTATE를 확인하고 비밀값 없이 진단 |

인증서가 필요하면 Supabase 프로젝트의 Database/SSL 설정에서 제공하는 CA를 사용하세요. Render에 등록한 파일이 예를 들어 /etc/secrets/supabase-ca.crt이면 DATABASE_SSL_ROOT_CERT를 그 경로로 설정합니다. sslmode=verify-full을 끄거나 sslmode=require로 완화하지 않습니다.

자동 배포는 꺼져 있으므로 수정 커밋을 올린 뒤 Render 서비스에서 **Manual Deploy → Deploy latest commit**을 실행해야 합니다. 기존 92863bb를 다시 배포하면 이전의 일반 메시지가 계속 표시됩니다. 코드만으로 실제 DB 비밀번호·연결주소를 바꾸거나 오류 원인을 확정할 수는 없습니다.
