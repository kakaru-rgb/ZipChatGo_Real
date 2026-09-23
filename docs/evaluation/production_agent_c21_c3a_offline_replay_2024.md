# C2.1 + C3a evaluation-only offline replay

- 입력: `C:\ajb\git\ZipChatGo_Real\docs\evaluation\production_agent_passthrough_integrated_a_b_c1_c2_2024_q6_9_21_27_37_30_35_36_39_40_gpt-5.6-sol.csv` (READ ONLY)
- OpenAI API 호출: 없음
- Vector Store API 호출: 없음
- 운영 코드/기존 C2 변경: 없음

## C2.1 결과

- 9번: 기존 C2 `rejected` → C2.1 `PASS`
- 21번: 기존 C2 `rejected` → C2.1 `PASS`

9번은 동일한 `공인중개사법 시행규칙 제4조` parent pair의 모든 청크를 검사하여, 다른 동일-pair 청크에 실제 존재한 `「상법」 제614조`를 종속 cross-reference로 인정했다.

21번은 `공인중개사법` family 문맥을 유지해 `시행령 제31조`를 `공인중개사법 시행령 제31조`로 해석했다.

## C3a 결과

- 6번: `PASS`; required=['공인중개사법']; matched=['공인중개사법']; source=explicit_stem; reason=-
- 9번: `PASS`; required=['공인중개사법']; matched=['공인중개사법', '공인중개사법 시행규칙', '공인중개사법 시행령']; source=explicit_stem; reason=-
- 21번: `PASS`; required=['공인중개사법']; matched=['공인중개사법', '공인중개사법 시행령']; source=explicit_stem; reason=-
- 27번: `PASS`; required=['부동산 거래신고 등에 관한 법률']; matched=['부동산 거래신고 등에 관한 법률', '부동산 거래신고 등에 관한 법률 시행규칙', '부동산 거래신고 등에 관한 법률 시행령']; source=explicit_stem; reason=-
- 37번: `PASS`; required=['주택임대차보호법']; matched=['주택임대차보호법']; source=explicit_stem; reason=-
- 30번: `REJECT`; required=['민사집행법']; matched=[]; source=explicit_stem; reason=required_law_not_retrieved
- 35번: `PASS`; required=[]; matched=[]; source=not_detected; reason=-
- 36번: `REJECT`; required=['부동산 실권리자명의 등기에 관한 법률']; matched=[]; source=human_reviewed_annotation; reason=required_law_not_retrieved
- 40번: `REJECT`; required=['장사 등에 관한 법률']; matched=[]; source=explicit_stem; reason=required_law_not_retrieved

36번 원문 stem에는 법률명이 직접 쓰여 있지 않다. 따라서 불안정한 문맥 추론 대신, 이번 frozen 문항에 한해 사람이 확인한 governing law를 사후 평가 annotation으로 사용했다. 이 annotation은 Agent 입력이나 retrieval에 전달되지 않는다.

30·40번은 stem에 명시된 핵심 법률이 검색되지 않아 REJECT, 35번은 명시 법률이 없어 gate 미적용이다. 6·9·21·27·37번은 필요한 law family가 검색되어 모두 PASS했다.

## 결론

C2.1과 C3a는 targeted offline 조건에서 안정적으로 동작했다. 다음 단계 D는 별도 승인 후 진행한다.
