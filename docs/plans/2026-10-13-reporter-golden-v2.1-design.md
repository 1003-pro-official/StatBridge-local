# 기자 질의 통계표 탐색 골든셋 v2.1 설계

작성일: 2026-10-13. 대상: `eval/reporter-table-discovery-30/v2.1/`. 목표: v2 형식을 유지한 200문항 공개 개발용 골든셋.

## 확인한 v2 제작 기준

- 질문 소재는 `research/그림표-분석/` 보고서 31종의 그림 3,485·표 542(4,027건) 주제. 연구 문서는 화제 출처일 뿐 정답 근거가 아님(`role: journalistic_context_only_not_numeric_or_table_id_gold`).
- 정답 근거는 `src/agent/stat_dictionary/stat_language_dictionary.json`(v5.1, 349표) 메타데이터. SHA256 고정.
- 스키마 `reporter30-discovery-2`의 6블록 단계별 정답. 상태는 `resolved`/`no_match`/`need_clarification`.
- v1(전부 resolved, 57계열·26표)에서 카탈로그로 검증되지 않는 계열을 제거해 v2(39계열·17표, no_match 8)를 만들었다. 이 교정이 v2의 핵심 기준이다.
- 검증은 오프라인 검증기 + 변조 테스트, 실행은 질문만 전달하고 추론 종료 후 채점하는 별도 실행기.

## 결정 사항

| 항목 | 결정 |
|---|---|
| 범위 | 총 200문항 = v2 원본 30 + 증강 170 |
| 질문 작성 | research 주제 기반 수기·AI 작성, 정답은 카탈로그 대조로 확정 |
| 상태 분포 | v2 비율 유지 → resolved 140 / no_match 53 / need_clarification 7 (증강분 119/45/6) |
| 구성 분포 | v2 실제 구성(단일 5 : 한 표 복수 14 : 여러 표 복수 2) 비율 → 증강 resolved 119 = 단일 28 / 한 표 79 / 여러 표 11 |
| 역질문 | 카탈로그 `clarification_groups` 11개 고정 그룹에만 대응하므로 증강분은 6개 그룹 사용 |
| 진행 방식 | 25문항 배치로 작성·검증 후 확인, 나머지 145문항 이어서 작성 |
| 결과 저장 게이트(실행기) | 200/200 전건 통과 시에만 최종 결과 저장 |

## 구조

- `scripts/build.py`: 문항 스펙(질문·표·분류값 이름·research 결과물ID)에서 정답 JSONL·요약·manifest를 생성. 기간·`exact_params`·분류 코드는 `validate.py`의 함수와 카탈로그 값에서 파생한다. 런타임 예측을 읽지 않는다.
- `scripts/validate.py`: v2 검증기를 일반화. 문항 수는 manifest에서 읽고, 스키마 두 종을 허용하며, `research_references`의 행·제목·SHA256·결과물ID와 v2 원본 본문 보존을 함께 검사한다.
- `tests/`: 분류 코드 오류, 계열 누락, v2 본문 변조, 출처 해시·행 불일치, 출처 누락을 거부하는 회귀 테스트.
- 실행기(`evaluate_runtime.py`)는 API 키가 필요한 별도 단계로 두고 골드셋 확정 후 이식한다.

## 리스크

- 증강 `no_match` 45문항은 "기자에게 그럴듯하지만 카탈로그 349표로 답할 수 없는 주제"라야 한다. 표 대조 확인이 문항당 필요하다.
- research 마스터 CSV 필드 상당수가 `추정`·`불명`이므로 제목 수준으로만 소재를 취한다.
- 200문항 런타임 실행은 LLM/API 호출 비용과 시간이 크다.
