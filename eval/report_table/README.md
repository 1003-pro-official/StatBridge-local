# 첨부 표 편집 평가

`reference_cases.json`은 업로드한 PDF의 물리적 5·13·18쪽에서 발췌한 88개 관측값입니다. 파일 SHA256과 쪽 번호를 각 사례에 기록했습니다. 5쪽은 조사 시계 3개와 응답 구간 4개, 13쪽은 가계신용·가계대출의 연간/분기, 18쪽은 금액/건수의 10개 항목을 사용합니다.

정답은 조회값 직접 참조와 Python Decimal 차이·증가율 검산입니다. 모델 응답이나 그림 속 계산값을 그대로 정답으로 복사하지 않습니다. 입력 관측값과 독립 수식으로 22개 계산 셀을 검증합니다. `tests/test_table_layout.py`에 각 실패 조건과 정답 검증을 명시했습니다.

```powershell
.venv/Scripts/python.exe tools/run_table_edit_eval.py
```

외부 HTTP를 전송 전에 차단합니다. 모델 키는 평가 자식 프로세스에서만 공란으로 설정하며 프로젝트 .env를 수정하지 않습니다. 평가 로그·JUnit·개별 판정은 `.venv/cache/table-editor-20261019/evaluation/`에 저장합니다. 실제 UI는 별도 계정 DB의 `tools/serve_table_edit_preview.py`로 확인합니다. 이 서버와 원본 참조 관측값은 운영용 KOSIS 데이터 경로가 아닙니다.

이 평가의 PASS는 표 편집·계산·파일·복원 회귀에 한정합니다. 실시간 KOSIS 조회, GPT 자연어 계획 품질, 첨부 ZIP의 모든 표 완전 재현, 전문가의 통계 의미 승인으로 해석하지 않습니다. 원본 PDF·계정 DB·생성 파일·평가 로그는 공개 커밋 대상이 아닙니다.
