"""Legacy program identifiers remain stable across the new portal."""
GROUPS = [
('정보관리','법인카드관리',[('0502_000','보유카드조회','cards'),('0501_000','카드위임설정','delegations'),('0501_010','수임카드조회','delegated')]),
('전표작성','전자증빙전표',[('0201_000','법인카드','card'),('0201_010','매입세금계산서(전자)','invoice'),('0201_003','법인카드 LOCK해제(현업)','unlocks')]),
('전표작성','경비전표',[('0202_001','실물증빙','physical')]),
('전표작성','출장비전표',[('0205_000','법인카드(출장비)','trip_card'),('0205_010','실물증빙(출장비)','trip_physical')]),
('전표작성','선급전표',[('0203_001','업무상 전도금신청','advance_employee'),('0203_011','선급금 신청(거래처)','advance_vendor'),('0203_021','사업장 전도금신청','advance_site')]),
('전표작성','정산전표',[('0204_001','업무상 전도금정산','settle_employee'),('0204_011','선급금 정산(거래처)','settle_vendor'),('0204_021','사업장 전도금정산','settle_site')]),
('결재관리','결재관리',[('0302_000','결재관리','approvals')]),
('리포트','현업부서',[('0601_000','부서경비 예산조회','budget_cc'),('0601_070','PJT별 예산조회','budget_wbs'),('0601_040','업무상 전도금현황','report_employee'),('0601_050','거래처 선급금현황','report_vendor'),('0601_060','사업장 전도금현황','report_site'),('0601_020','법인카드 처리현황','report_cards')]),
('리포트','관리부서',[('0602_090','현업전기 모니터링 내역','monitor'),('0602_110','매입세금계산서 처리현황','report_invoices'),('0602_130','출장정보 관리','trips'),('0602_020','법인카드 처리현황','all_cards'),('0602_080','법인카드 지연현황','delayed')]),
('마스터관리','마스터관리',[('0701_000','공급업체 마스터 생성','vendors'),('0701_030','공급업체 마스터 변경','vendor_changes')]),
('마스터관리','관리부서',[('0602_070','법인카드 통제계정관리','account_rules'),('0602_100','부가세 통제업종관리','vat_rules'),('0602_120','업종별 계정지정 설정','industry_rules')]),
('게시판','게시판',[('0702_000','공지사항','notices'),('0702_020','매뉴얼','manuals')])]
MENUS=[dict(id='UD_'+pid,title=title,kind=kind,section=section,group=group,admin=(section=='마스터관리' and group=='관리부서') or (section=='리포트' and group=='관리부서')) for section,group,items in GROUPS for pid,title,kind in items]
