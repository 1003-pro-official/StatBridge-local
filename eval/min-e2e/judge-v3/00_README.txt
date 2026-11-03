StatBridge LLM Judge 공유 자료 · 2026-11-02 · ai-assisted

먼저 01_평가_요약.md를 읽으세요. latest_observations_index.json은 결과 파일을 찾는 참고 색인입니다.
이 묶음은 여러 실행과 후속 증거의 결과를 구분해 보존합니다. 단일 실행 10/10 성능으로 인용하면 안 됩니다.

폴더
judge_criteria/: Claude가 확정한 v3 문항 정의·루브릭 정책·공통 Judge 프롬프트·결과 스키마.
qualitative_initial/: 14:35 최초 10문항 정성평가 확정본, 이전 초안과 수정 이력.
qualitative_reassessed/: Q05·Q06 수정 후 평가와 Q10 스크롤 보완 평가, 작성 코드와 수정 이력.
accuracy_initial/: 최초 실행 10문항의 정확성 결과·상세 비교·검증 코드 v1·검증기 변조 시험 기록.
accuracy_patched/: 수정 후 Q05·Q06 정확성 결과·검증 코드 v2·v1 대비 diff·변조 시험 기록.
actual_outputs/: 최초 실행의 원본 캡처·제품 스냅샷·실행 관찰 기록.
after/: Q05·Q06 새 실행 캡처·제품 스냅샷·전체 표·실행 기록과 소스 해시.
Q10_scroll_supplement/: 저장된 동일 응답의 후속 내부 스크롤 전후 캡처·검사 기록.
reference_only/: 2026-10-27 동결 정답 참고 문서·관측값. 제품 출력과 구별하세요.
evaluation_design/: 원래 질문 10개와 정성 루브릭.
provenance/: 최초 실행 코드·파일 해시, 사용량, 기준 승인 원본과 출처.
change/: 단위 검토 흐름 최소 수정 diff·회귀 테스트 및 수행한 검증 범위.
reassessment_request/: Q05·Q06·Q10 재평가에 사용한 프롬프트와 증거 목록.

Claude 산출물은 원본 바이트를 보존했습니다. 원래 파일의 경로나 문구는 수정하지 않았습니다.
공유 폴더에 맞춘 결과 위치는 이 안내와 archive-manifest.json의 출처 매핑을 사용하세요.
judge_criteria의 run_binding_v14_20261027_archive.jsonl은 과거 실행 보관 양식입니다.
이번 최초 실행은 루트 run_binding_new_20261102.jsonl, 수정 후 실행은 after/run_binding_Q05_Q06.jsonl입니다.

코드 재현 예시 (압축을 푼 최상위 폴더에서 실행, 새 OUT 폴더 사용)
python accuracy_initial/verify_accuracy.py . reproduced_initial
python accuracy_patched/verify_accuracy_v2.py . reproduced_patched --binding after/run_binding_Q05_Q06.jsonl --prefix after/actual_outputs --cases ME14-23,ME14-29
검증 스크립트는 저장된 JSON을 비교하는 것으로 제품·유료 API 재실행이 필요하지 않습니다.
이 예시는 검증 결과를 새로 기록하며 제공된 원본 결과 파일을 덮어쓰지 않습니다.

제외한 자료: 실제 API 키, .env, 계정 DB, 인증 쿠키, 원자료 CSV 폴더, 벡터 DB, 비공개 평가·holdout 정답.
압축 무결성, 원본 해시, 결과 25건의 v3 스키마, 이미지 경로와 실행 구분을 패키징 시 점검했습니다.
