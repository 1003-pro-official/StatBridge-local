# 기자 질의 통계표 탐색 골든셋 v2.1 (목표 200문항)

v2의 30문항과 단계별 정답 형식을 그대로 유지하고, 한국은행 보고서의 그림·표 주제를 출처로 새 문항을 증강한 공개 개발용 골든셋입니다.

- 기준일: 2026-10-13
- 스키마: `reporter200-discovery-2.1` (v2에서 그대로 옮긴 30문항은 `reporter30-discovery-2` 유지)
- 문항: 200개 = v2 원본 30 + 증강 170 (`resolved` 140, `no_match` 53, `need_clarification` 7)
- 증강 170의 구성: 단일 계열 28 / 한 표 복수 계열 80 / 여러 표 복수 계열 11, 표 96개
- 정답 근거: 한국은행 KOSIS 카탈로그(`org_id=301`) 349개 표 메타데이터
- 검수 상태: `ai-assisted`, 사람 승인 대기 (`human_approved=false`)
- 모든 문항은 공개 `dev`이며 블라인드 holdout이 아닙니다.

## 증강 기준

- v2 원본 30문항은 바이트 수준이 아니라 **JSON 내용 그대로** 옮깁니다. `schema_version`만 v2 값이 남습니다. 검증기가 v2 파일과 대조해 본문 변경을 거부합니다.
- 신규 문항은 `research/그림표-분석/`의 보고서 그림·표 주제에서 착안합니다. 출처는 `research_references`에 경로·행·제목·결과물 ID·SHA256으로 기록하고, **research 본문은 정답 근거가 아닙니다**. 표 ID·항목·분류 코드는 카탈로그에서만 가져옵니다.
- 연구 문서의 `추정`·`불명` 필드는 질문 소재로도 정답 근거로도 쓰지 않습니다.
- 기간 정책과 판정 규칙은 v2와 동일합니다. 명시 기간은 포괄적 KOSIS 기간으로 변환하고, 기간 미지정 문항은 런타임 계획을 기록한 뒤 API `need_period` 후속을 기대합니다.
- 표 ID 집합과 계열 코드 조합은 순서 없이 정확히 일치해야 하며, 누락·추가 계열은 실패입니다.

## 파일

| 파일 | 내용 |
|---|---|
| `statbridge-reporter200.jsonl` | 200문항, 질의·해석 슬롯·단계별 정답·출처 |
| `statbridge-reporter200.md` | 문항별 질문·상태·정답 표 요약 |
| `dataset_manifest.json` | 버전, 상태·스키마별 집계, dataset·catalog·research SHA256 |
| `scripts/build.py` | 문항 스펙에서 정답 JSONL·요약·manifest를 생성. 런타임 예측을 읽지 않음 |
| `scripts/specs/batch*.json` | 작성 배치별 문항 스펙(질문·상태·표·분류값 이름·출처). 생성기의 입력 |
| `scripts/validate.py` | 카탈로그 코드·기간·API 파라미터·v2 원본 보존·research 출처를 확인하는 검증기 |
| `tests/test_reporter200_validate.py` | 분류 코드 오류, 계열 누락, v2 본문 변조, 출처 해시·행 불일치를 거부하는 회귀 테스트 |
| `scripts/evaluate_runtime.py` | 실제 `/api/query` 실행기. 채점 정책·합격 판정·진단 산출물 |
| `scripts/evaluate_offline.py` | 규칙 계층 오프라인 평가: 리졸버 후보 대비 recall@k·MRR·주기·역질문 일치. LLM·키 불필요 |
| `scripts/self_audit.py` | 골드 자기 감사: 카탈로그 역질문 계약(하드)과 질의↔표·부재 근거(경고). 골드를 고치지 않음 |
| `scripts/verify_kosis.py` | 골드의 KOSIS 파라미터를 **실서버에 그대로 보내** 응답·기간·분류 이름을 확인(키 필요, 표본 기본 20건/`--all`) |
| `scripts/evaluate_execution.py` | 조회 계층 실행기: `execute=true`로 실제 조회를 요청하고 계약(표·기간·행 수·조회 금지)을 채점. 차트 생성은 금지 |
| `scripts/build_kosis_snapshot.py` | 값 정본 생성: 골드 계열의 KOSIS 값을 기준일로 고정해 `kosis_snapshot.json`에 저장(키는 저장하지 않음) |
| `scripts/score_execution_values.py` | 값 채점: 저장된 조회 rows와 스냅샷을 비교(소수 자릿수 허용오차, 결측은 결측으로) |
| `kosis_snapshot.json` | 값 정본(기준일·골드 해시·계열별 점) |
| `tests/test_runtime_save_gate.py` | 채점 계약, 반복 표본, 중복 계열, 실패 분류, 저장 게이트 회귀 테스트 |
| `tests/test_gold_mutation_coverage.py` | 200문항 각각에 필드 변조를 넣어 검증기가 전부 거부하는지 확인 |
| `tests/test_self_audit.py` | 자기 감사의 하드·경고 판정 회귀 테스트 |
| `tests/test_offline_metrics.py` | 오프라인 지표 산식(순위·분모) 회귀 테스트 |

## 단계별 골드

v2와 동일하게 `query_interpretation`, `table_discovery`, `item_selection`, `classification_and_plan`, `resolution`, `post_discovery`를 기록하고, 증강 문항에는 `research_references`를 추가합니다. 값은 런타임 예측 로그가 아니라 카탈로그 메타데이터로 작성한 규범적 기대 정답입니다.

## 채점 기준 (동결)

실행: `python3 eval/reporter-table-discovery-30/v2.1/scripts/evaluate_runtime.py`
기준은 실행 전에 `POLICY` 상수와 이 표에 고정하며, 해시(`policy_sha256`)가 manifest·`run_manifest.json`에 기록됩니다. 정책을 바꾸면 기존 실행은 무효입니다.

| 채점 항목 | 판정 |
|---|---|
| `http_success` | HTTP 200 |
| `agent_status` | 골드 `resolution.agent_status` 일치 |
| `api_boundary_status` | `need_period`·`no_match`·`need_clarification` 일치 |
| `table_set` | 표 ID **집합** 정확 일치 |
| `series_identity_set` | `(표 ID, 항목 ID, 분류코드)` **중복 포함** 일치 |
| `exact_api_params` | 계열별 KOSIS 파라미터(기간·주기·`objL*`) 완전 일치 |
| `clarification_group` / `clarification_options` | 역질문 그룹 ID 일치 / 런타임 선택지가 골드(카탈로그) 선택지의 **부분집합**(카탈로그에 없는 선택지는 요구하지 않음) |
| `period_followup` | `need_period` + 기간 텍스트 선택 여부가 골드와 일치 |
| `numeric_not_executed` / `chart_not_generated` | 수치 조회 0회 / 차트 없음 |

| 합격 조건 | 기준 |
|---|---|
| 경계·HTTP·미분류·골드 의심 | 각 0건 |
| v2 원본 30문항 | 30/30 |
| 증강 `resolved` 119건 | 114건 이상 (≥95%) |
| 증강 `no_match` 45건 | 41건 이상 (≥90%) |
| 증강 역질문 6건 | 5건 이상 |

- 진단 점수(`scores.json`, `diagnostic.md`)는 항상 저장하고, `REPORT.md`는 위 조건을 모두 충족할 때만 저장합니다.
- 실행기는 리포 `tests/authenticated_client.py`의 로그인 클라이언트를 씁니다. 인증 미들웨어가 `/api/query`를 보호하므로 로그인 없이 호출하면 401이 나고, 실행기는 첫 401에서 중단합니다.
- 부분 실행은 `--limit`(배선 확인용, 점수가 아님), 중단 후 재개는 `--resume`을 씁니다. 재개는 기존 실행과 정책·데이터셋·소스 해시가 다르면 섞지 않고 중단합니다.
- 실행은 200문항 + 반복 표본 20건 = 220회입니다. 반복은 상태·구성 층화로 결정적으로 고르고 통과 판정 분모에서 제외하며, 일치율로만 보고합니다. 주기(M/Q/A) 층화는 보장하지 않습니다.
- 문항당 타임아웃 120초, 초과 시 `http_error`로 기록하고 진행합니다. 재시도는 금지합니다.
- 모든 실패는 `http_error`·`status_misjudged`·`table_set`·`series_identity`·`params`·`clarification_group`·`clarification_options`·`period_followup`·`boundary_violation` 중 하나로 분류됩니다. 분류되지 않은 실패는 합격을 막습니다.
- 귀책이 불분명한 문항은 `--gold-suspect-file`로 넘기고, 목록이 비어 있지 않으면 `REPORT.md`를 저장하지 않습니다.

산출물은 `evaluation_runs/reporter200_v2.1_<UTC시각>/`에 생성됩니다: `query_only_inputs.jsonl`, `environment.json`, `endpoint_logs.jsonl`, 문항별 `<id>.json`(`<id>.repeat.json`), `scores.json`, `diagnostic.md`, `run_manifest.json`, 합격 시 `REPORT.md`.

## 오프라인 검증 (런타임·키 불필요)

전체 실행 전에 초 단위로 돌려 골드와 규칙 계층의 문제를 먼저 걸러냅니다.

```bash
python3 eval/reporter-table-discovery-30/v2.1/scripts/self_audit.py       # 골드 자기 감사
python3 eval/reporter-table-discovery-30/v2.1/scripts/evaluate_offline.py  # 규칙 계층 recall
python3 eval/reporter-table-discovery-30/v2.1/scripts/verify_kosis.py --sample 20  # 실서버 파라미터 검증(키 필요)
python3 -m pytest -q eval/reporter-table-discovery-30/v2.1/tests           # 변조 커버리지 포함
```

- 자기 감사의 **하드 위반**은 골드가 카탈로그 역질문 계약을 어겼다는 뜻입니다(현재 1건: `REPORTER30-V2.1-153`). 경고는 한국어 어휘 기반 힌트이므로 실패로 처리하지 않습니다.
- 오프라인 recall은 **판정 기준이 아닙니다.** 규칙 계층만으로는 v2 원본 30문항(실제 런타임 30/30 통과)에서도 rank1 42.9%에 그쳤습니다. 역질문·기간·경계는 엔드포인트 실행으로만 검증됩니다.
- 변조 커버리지 테스트는 200문항 각각에 스키마·승인·표·항목·기간·파라미터·분류·주기·상태 변조를 넣고 검증기가 전부 거부하는지 확인합니다.
- `verify_kosis.py`는 **카탈로그를 벗어나는 유일한 검증**입니다. 전수 실행에서 응답 293/293이었지만, 분류 코드와 이름의 대응이 실서버와 다른 계열이 27/293(14문항) 있었습니다(카탈로그 결함, `docs/evaluation/2026-10-13-reporter-v2.1-offline-verification.md` §10). 골드와 런타임이 같은 카탈로그를 쓰므로 이 결함은 골드 대 골드 채점으로는 발견되지 않습니다.

## 조회(데이터 검색) 계층 평가 (2026-10-13 추가)

탐색 골드의 표·항목·분류·기간을 그대로 써서 **실제 조회까지** 평가한다.

```bash
python3 eval/reporter-table-discovery-30/v2.1/scripts/build_kosis_snapshot.py       # 값 정본(기준일 고정)
python3 eval/reporter-table-discovery-30/v2.1/scripts/evaluate_execution.py         # 조회 계약
python3 eval/reporter-table-discovery-30/v2.1/scripts/score_execution_values.py \
    --rows evaluation_runs/execution_full_<ts>/execution_rows.json                   # 값 채점
```

- 조회 흐름: `POST /api/query {query, execute:true}` → 앱이 조회를 마치면 `need_output_config`와 `outputSessionId`를 돌려준다. 행은 같은 프로세스의 세션(`OUTPUT_SESSIONS[id]['result']['execution']['rows']`)에서 읽고, **차트 생성 단계는 호출하지 않는다**(평가 경계).
- 기간이 없는 문항은 먼저 대기 상태(`need_period`)를 기록하고, 골드 계획 기간을 ISO로 주입해 조회까지 채점한다(주입한 기간은 우리가 고른 값이라는 점을 결과에 명시).
- `no_match`·역질문 문항은 **조회 금지가 정답**이다(조회가 일어나면 실패).
- 값 비교는 스냅샷 값의 소수 자릿수로 허용오차를 정하고(예: 2자리 → ±0.005), 결측은 결측으로 본다(0 대체 금지).

### 첫 측정 (2026-10-13, 스냅샷 기준일 동일)

| 지표 | 값 |
|---|---:|
| 조회 도달(탐색 통과 후 실행) | 71 / 140 |
| 조회 계약 통과(도달 분모) | 58 / 71 (81.7%) |
| 조회 금지 정답 준수 | 46 / 60 |
| 값이 일치한 계열 | 78 / 136 |
| 비교한 값(점) 일치율 | 4,832 / 4,832 (100%) |
| 차트 생성 호출 | 0 (경계 준수) |

- 값이 일치한 계열에서는 값이 정확히 같다(같은 KOSIS 원천). 미조회 58계열은 **다른 표를 조회했거나 일부 계열만 조회**한 경우로, 조회 계약의 `tables_match`에서 별도로 잡는다.
- 값 채점은 **조회한 계열만** 검증한다. 대체 조회·누락은 계약 계층(`tables_match`, `not_executed`)이 담당한다.

## 범위와 한계

- 평가 범위는 통계표 탐색까지입니다. KOSIS 수치 호출, 로컬 CSV, 그래프 출력, 해석 문장은 `excluded_from_scoring`입니다.
- 자동 검증 통과는 골드의 사람 승인을 뜻하지 않으며 모델 성능 점수로 해석하지 않습니다.
- `v1`, `v2`, `v3`, `v3-four-tables`, `table-discovery/`, `end-to-end/`, `statbridge-golden/`과 버전·점수를 혼용하지 않습니다.
- 비공개 평가 저장소와 holdout 정답은 포함하지 않습니다.

## 검수 기록

- 170문항을 전수 육안 검수해 질의와 표·계열 대응을 확인했다. 발견한 결함 2건을 고쳤다: `REPORTER30-V2.1-142`는 질의에 없는 `국민총처분가능소득` 계열이 정답에 있어 질의를 정답과 맞췄고, `REPORTER30-V2.1-090`은 `REPORTER30-V2.1-040`과 표·계열·문구가 사실상 같은 중복이어서 CD·RP 금리 비교로 바꿨다.
- 검증기 통과는 골드의 사람 승인이 아니다. 자동 검사는 구조·코드·해시만 확인하고 질의의 의미와 계열 선택의 타당성은 검사하지 않는다.

## 카탈로그 이름 교정 (2026-10-13)

- `src/agent/stat_dictionary/stat_language_dictionary.json`의 분류값 이름 2,538건(41개 표)이 소스 메타데이터 `data/processed/bok_classifications.csv`와 어긋나 있었다. 코드는 실서버에서 다른 분류를 가리켰고(예: `내수` 코드 → `통계상 불일치`), 골드·런타임이 같은 카탈로그를 쓰므로 골드 대 골드 채점으로는 발견되지 않았다.
- `tools/repair_dictionary_values.py`로 코드는 두고 이름/파생 필드만 교정했다. 실서버 재검증에서 분류 이름 불일치가 **27계열 → 0건**이 되었다(294/294 응답).
- 이 교정으로 이름이 사라진 3문항(`065`·`066`·`136`)은 실제 존재하는 분류값으로 다시 썼고, v2 원본에서 복사한 2문항(`013`·`020`)의 잘못된 코드 4건은 이름(의도)을 두고 코드만 교정해 `legacy_value_repair`에 기록했다.
- v2·v3·v3-four-tables는 사용하지 않기로 해 데이터를 재생성하지 않았다. 해당 계보의 영향 테스트는 `xfail(strict=True)`로 표시했다.

## 한계

- `seasonal_adjustment` 역질문 그룹은 카탈로그의 `trigger_terms`가 M2 관련어로 되어 있어 실질 GDP 질문으로는 런타임이 이 역질문을 띄우지 않을 수 있다. 골드 그룹·선택지는 카탈로그와 일치한다.
- 증강 170문항은 research 결과물ID 166개를 참조한다(4개는 서로 다른 두 문항이 같은 그림·표를 출처로 씀).
- `no_match` 45건의 부재 판정은 공개 카탈로그 메타데이터 검색에 근거한다. KOSIS 실시간 호출로 재확인하지 않았고, 시산 지표가 정기 통계표로 편입되면 판정이 바뀔 수 있다.

## 검증

```bash
python3 eval/reporter-table-discovery-30/v2.1/scripts/build.py
python3 eval/reporter-table-discovery-30/v2.1/scripts/validate.py
python3 -m pytest -q eval/reporter-table-discovery-30/v2.1/tests
# 실제 API 실행(키와 런타임 의존성이 있는 환경)
python3 eval/reporter-table-discovery-30/v2.1/scripts/evaluate_runtime.py
```
