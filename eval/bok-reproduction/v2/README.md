# 한국은행 E2E 평가 v2

ai-assisted · 공개 원자료 기반 후보셋 · 사람 승인 대기 · 점수 미산출

## 범위

질의 명세는 논리 질의 36건, 각 4개 표현·출력 조합으로 후보 144건입니다. 감사 원본 46건은 별도 `source_register.jsonl`에 보존하며, 사례의 `source_id`는 감사 원본 ID가 아니라 해당 공표물 ID입니다. 따라서 하나의 공표물에 여러 질의·도표가 연결될 수 있습니다.

각 사례는 PDF 당시 빈티지의 전체 도표를 재현한다고 주장하지 않습니다. 숫자 정답은 빌드 시 고정한 로컬 KOSIS CSV에서 독립 추출합니다. 요구 계열·기간·단위 또는 참조 PDF SHA-256을 확인하지 못한 후보는 `blocked`로 남으며, 기간을 줄이거나 수치를 추정하지 않습니다. 연구 질의의 `human_reviewed:false` 상태도 그대로 반영합니다. 골든셋의 사람 승인은 별도 절차입니다.

PDF는 출처와 사람 검토를 위한 `reference_attachments`로 보관합니다. 제품 질의 입력에는 포함하지 않으며, 현재 제품 실행 어댑터도 PDF를 업로드하지 않습니다.

## 빌드와 검증

저장소 루트에서 실행합니다. 숫자 자료와 ZIP은 `.venv/cache/` 아래 로컬 평가 캐시에 생성되며 저장소에 커밋하지 않습니다.

```bash
python eval/bok-reproduction/v2/scripts/build.py
python eval/bok-reproduction/v2/scripts/validate_package.py .venv/cache/kosis-bok-reproduction/evaluation-v2/bok-e2e-v2.zip
python -m pytest -q eval/bok-reproduction/v2/tests
```

기본 산출 위치는 `.venv/cache/kosis-bok-reproduction/evaluation-v2/bok-e2e-v2.zip`입니다. `build_inputs/`에는 질의·감사목록·메타데이터·원자료 CSV 스냅샷·확보된 PDF가 들어갑니다. ZIP 내부 `scripts/validate_package.py`로 검증하고 `scripts/build.py --input-root build_inputs --output ...`로 동일한 입력에서 다시 생성할 수 있습니다. manifest는 `manifest.json` 자체를 제외한 모든 ZIP 파일의 SHA-256을 기록합니다.

`ready:false`는 실행 불가를 뜻하며, 오류와 runnable/blocked 수를 먼저 해결해야 합니다. runnable도 사람 승인 전에는 공식 골드나 성능 점수로 부르지 않습니다.

## 제품 E2E 어댑터

ZIP을 별도 폴더에 푼 뒤 먼저 패키지 검증기를 실행하고, 패키지 Python 의존성과 Chromium을 설치합니다. 어댑터는 제품 checkout의 백엔드와 프런트엔드를 로컬 포트에서 시작하고, ZIP에 고정된 메타데이터·CSV를 fixture로 연결해 브라우저에서 테스트 계정으로 로그인한 뒤 후보 질의를 제출합니다. baseline 모델을 실행 환경에 적용하며, 제품 출력 생성기는 `OPENAI_CHART_MODEL`을 사용합니다. `STATBRIDGE_EVAL_USERNAME`과 `STATBRIDGE_EVAL_PASSWORD`로 로그인 정보를 지정할 수 있습니다.

```bash
python -m zipfile -e /path/to/bok-e2e-v2.zip /path/to/extracted-zip
python /path/to/extracted-zip/scripts/validate_package.py /path/to/bok-e2e-v2.zip
cd /path/to/extracted-zip
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/adapter.py --bundle-root /path/to/extracted-zip \
  --product-root /path/to/StatBridge-local --case-id INF-01__업무형__graph \
  --run-dir /path/to/private-run
```

실행 기록·스크린샷·로그·예측은 비공개 평가 디렉터리에 둡니다. 제품 revision, adapter 코드 해시, baseline profile 및 적용된 chart 모델을 함께 기록합니다. 모델 API 자격 증명은 ZIP에 넣지 않으며 제품 실행 환경에서만 읽습니다. 실제 모델 호출·144건 전체 채점은 빌드 명령에서 수행하지 않습니다.

```bash
python scripts/evaluate.py oracles.json /path/to/private-run/observed.json \
  --case-id INF-01__업무형__graph --output /path/to/private-run/score.json
```

`oracles.json`은 평가 ZIP 안의 케이스 ID별 정답 맵입니다. blocked 사례에는 정답이 없고 실행할 수 없습니다. XLSX 검증은 각 기간 헤더에 연결된 셀의 값까지 비교하므로, 숫자만 같고 기간에 잘못 배치된 표는 통과하지 않습니다.

계산기 경계 검사·장애 주입은 별도 진단 트랙이며 이 E2E 점수에 합치지 않습니다.
