# StatBridge 골든셋 설계 (v0.1)

- 작성일: 2026-10-06
- 상태: 정의 확정(구현 전). 기존 `eval/table-discovery/v1~v4.1`·`eval/end-to-end/v1~v2`의 사례·라벨은 이 정의에 사용하지 않는다.
- 목적: StatBridge의 자연어 질의 → 통계표 탐색·실행·**그래프 해석**을 자동 평가하기 위한 새 골든셋의 정의와 생성 절차를 고정한다.

## 0. 정의

**골든셋 = 자연어 질의를 고정 입력으로 넣었을 때의 계층별 기대 출력(9층)을 정답으로 기록해 둔, 3분할(dev/test/holdout)·버전 고정 시험지.** 최상위 제품 KPI(pass/fail)와 단계별 진단을 **한 레코드**에서 함께 제공한다.

골든셋은 코드가 아니라 **데이터(JSONL)** 이며, 채점기는 별도 프로그램이다. 채점기는 `input`만 시스템에 넣고 `gold`는 시스템에 노출하지 않는다(누수 방지).

## 1. 답의 우주(범위) — 최우선 제약

- StatBridge가 답할 수 있는 것은 **KOSIS Open API의 한국은행 349표**(`data/kosis/hankook_tables.json`)뿐이다. 이 집합이 곧 **정답의 우주(answer universe)** 다.
- `research/` 발간물은 **질문 소재(씨앗)** 로만 사용한다. **정답은 항상 로컬 349표 카탈로그에서 확정**하고, `research/`를 정답 근거로 쓰지 않는다.
- 씨앗 출처 필터 (`research/그림표-분석/그림표_마스터.csv`의 `사용 데이터·출처` 기준, 총 4,027행):

| 출처 분류 | 건수 | 처리 |
|---|---:|---|
| `bok_only` (한국은행 단독) | 1,242 | 긍정 케이스 후보. 주제를 349표에 매핑되면 채택 |
| `mixed` (한은 + 외부) | 637 | 검수자가 한은 성분이 표에 있는지 확인 후 채택/제외 |
| `external_only` (외부 단독) | 1,714 | 현실적인 사용자 질문만 골라 `no_match` 부정 케이스로 채택, 나머지 제외 |
| `unknown` | 434 | PDF로 출처 확인 후 결정, 확인 불가 시 제외 |

- 발간물의 **전망치를 관측값 정답으로 쓰지 않는다.**
- 복수 출처 표기의 `mixed`는 자동 판정하지 않고 검수자가 결정한다.

## 2. 레코드 스키마 (단일 평면 레코드)

질의 1건 = 레코드 1개. 입력 단위는 `prior_turns` 옵션으로 단일 턴과 멀티턴을 한 형식으로 담는다.

```jsonc
{
  "id": "GS2-0001",
  "split": "dev",                       // dev | test | holdout
  "source": {
    "publisher": "한국은행",
    "publication": "경제전망보고서",
    "doc_id": "2026-08-27_경제전망보고서(2026년 8월)",
    "locator": "p.12 그림 3",
    "url": "..."
  },
  "input": {
    "prior_turns": [],                  // 비우면 단일 턴, 채우면 멀티턴(마지막 발화를 채점)
    "query": "최근 5년 경제심리지수 추이 알려줘"
  },
  "gold": {
    "e2e_kpi":       { "status": "labeled", "pass": true, "final_output": "..." },
    "slots":         { "status": "labeled", "metric": "경제심리지수", "period": { } },
    "concepts":      { "status": "labeled", "acceptable_concepts": [ ] },
    "clarification": { "status": "labeled", "need_clarification": false, "acceptable_options": [ ] },
    "plan":          { "status": "labeled", "acceptable_tool_sequences": [ ] },
    "discovery":     { "status": "labeled", "expected_status": "select",
                       "acceptable_table_ids": [ ], "required_set": [ ],
                       "forbidden_table_ids": [ ] },
    "numeric":       { "status": "not_labeled" },
    "graph":         { "status": "not_labeled" },
    "interpretation":{ "status": "not_labeled" }
  },
  "provenance": { "annotation_method": "...", "labeler": "...", "notes": "..." },
  "review": { "machine_reviewed": true, "human_approved": false }
}
```

### status 3값
- `labeled`: 정답을 실제로 기록함 → 채점 대상.
- `not_labeled`: 아직 정답 없음 → **점수 분모에서 제외**.
- `not_applicable`: 이 질의에 해당 계층이 없음 → 분모 제외.

**정답 없는 계층을 0점으로 세지 않는다.** `labeled`가 아닌 계층은 어떤 지표에도 포함하지 않는다.

### 정답은 "허용 집합" 중심
- 단일 정답이 아니라 `acceptable_table_ids`(허용 표 집합)로 기록한다.
- 복수표 질의는 `required_set`(필수 표)과 허용 집합을 함께 기록한다.
- 모호 질의(`clarification.need_clarification=true`)는 정답 표 대신 **필요한 선택지**가 정답이다.

## 3. 계층 (9층, 전부 gold 채점 대상)

| # | 계층 키 | 채점 내용 |
|---|---|---|
| 8 | `e2e_kpi` | 최종 산출물 도달 pass/fail |
| 1 | `slots` | 지표·기간·대상·비교 조건 추출 정확도 |
| 2 | `concepts` | 정답 개념 Recall@k / 순위 |
| 3 | `clarification` | 질문 필요 판정 + 선택지 적절성 |
| 4 | `plan` | 도구 시퀀스 유효성·필수 누락·무효 계획 차단 |
| 5 | `discovery` | 상태(select/clarify/no_match/catalog_only) + 후보 순위 + 최종 선택 |
| 6 | `numeric` | 시점·값·단위 |
| 7 | `graph` | 차트 종류·계열 (상세 §3.1) |
| 9 | `interpretation` | 그래프·데이터의 의미 해석 (상세 §3.2) |

`e2e_kpi`는 전체 결과, 나머지는 중간 과정으로 본다. `e2e_kpi`의 최종 산출물은 **그래프 + 해석**이며, 두 요소가 모두 성립해야 pass로 본다.

### 3.1 그래프(`graph`) 계층 상세

**목적**: 자연어로 요청한 그래프가 **올바른 계열·시점·값·단위·차트 종류**로 만들어졌는지 채점한다. "그래프를 그렸는가"가 아니라 **"무엇을 그렸는가"**를 본다.

#### gold 스키마 (`gold.graph`)

```jsonc
"graph": {
  "status": "labeled",                 // labeled | not_labeled | not_applicable
  "chart_type": "line",                // line | bar | ... (요청/기대 차트 종류)
  "layout": "separate",                // separate(계열별 분리) | combined(한 축에 결합)
  "fixture": "fixtures/esi.json",      // 수치 스냅샷 파일 (아래 스키마)
  "fixture_sha256": "...",             // fixture 파일 지문 (변조/갱신 감지)
  "snapshot_id": "statbridge-local-csv-frozen-2026-09-28",
  "series": [                          // 기대하는 통계계열 (순서 무관, 집합 비교)
    {
      "table_id": "DT_513Y001",
      "item_id": "13103134673999",     // 표가 단일 item으로 검증될 때만 기록
      "label": "경제심리지수 순환변동치",
      "unit": "",
      "classifications": { "objL1": "...", "objL2": "..." }   // 검증된 경우만
    }
  ],
  "visual_checks": [                   // 사람이 보는 항목 (자동 채점 아님)
    "축 단위가 계열 단위와 일치",
    "범례가 각 통계계열을 구분",
    "누락/중복 기간이 임의 보간되지 않음"
  ]
}
```

#### fixture 스키마 (수치 스냅샷, `fixture`가 가리키는 파일)

```jsonc
{
  "snapshot_id": "statbridge-local-csv-frozen-2026-09-28",
  "series": [
    {
      "table_id": "DT_513Y013",
      "item_id": "13103134673999",
      "label": "전산업 업황실적BSI",
      "frequency": "M",
      "unit": "",
      "classifications": { "objL1": "...", "objL2": "..." },
      "source_file": "data/tables/DT_512Y013__기업경기조사(실적).csv",
      "source_file_sha256": "47ae4b0d...",
      "source_last_changed_dates": ["2026-09-13"],
      "points": [ { "period": "202501", "value": 64.0 }, { "period": "202502", "value": 63.0 } ]
    }
  ]
}
```

- 수치 배열(`points`)은 레코드에 직접 넣지 않고 **fixture 파일로 분리**한다(중복 방지). 레코드는 `fixture` 경로·`fixture_sha256`·`snapshot_id`로 참조한다.
- `source_file_sha256`·`source_last_changed_dates`는 **어느 로컬 CSV 스냅샷에서 뽑았는지**를 고정한다. 스냅샷이 바뀌면 validator가 stale로 표시한다.

#### 기계 채점 항목 (자동)

1. `status == resolved`인가 (그래프 생성 성공).
2. **차트 종류** `chartType`이 `chart_type`과 일치.
3. **layout** 일치 (`separate`/`combined`).
4. **계열 집합**: 기대 `series`의 식별자 집합(`table_id` + `item_id`/`classifications`)과 실제 계열 집합의 **완전일치**, 아니면 P/R/F1.
5. **계열 개수** 일치.
6. **각 계열의 시점 집합**: 기대 `points`의 `period` 집합과 실제가 일치 (누락·추가 없음).
7. **각 계열의 값**: 허용 오차 내 일치. 반올림·단위 스케일 차이는 명시 규칙으로만 허용.
8. **단위·주기**: `unit`·`frequency` 일치.
9. **보간 금지**: 기대에 없는 기간을 임의로 채우지 않았는가.

#### 사람 검수 항목 (비자동)

`visual_checks`는 자동 채점하지 않는다. 축 단위 표기, 범례 구분, 색/가독성, 보간 여부의 최종 확인은 사람이 `review`에 기록한다. **시각 미학(색·폰트·레이아웃 세부)은 채점 범위 밖**이다.

#### 두 평가 모드를 분리한다 (중요)

| 모드 | 입력 | 측정하는 것 |
|---|---|---|
| `graph_data_exact` | 정답 계열 ID를 **직접 지정** | 데이터 경로만 정확한가 (기존 v1의 30/30) |
| `graph_e2e` | 자연어 질의만 | 자연어 → 계열 선택 → 그래프까지 전 과정 |

두 점수를 **합치지 않고 따로 보고**한다. "정답 계열을 지정한 그래프 데이터 검사 n/N"과 "자연어 전체 흐름 그래프 n/N"은 다른 주장이므로 분리한다.

#### 데이터 제약

- 그래프 gold는 **로컬 CSV(`data/tables/`)가 있는 표**에만 만들 수 있다. 없으면 `graph.status = not_labeled`.
- fixture는 반드시 로컬 CSV 스냅샷에서 추출하고 `snapshot_id`·`source_file_sha256`를 기록한다. 출처 없는 수치는 쓰지 않는다.
- 그래프가 요구되지 않는 질의는 `graph.status = not_applicable`.
- KOSIS 실시간 값과 로컬 fixture의 불일치 검사는 초기 범위 밖(§9).

### 3.2 해석(`interpretation`) 계층 상세

**목적**: 프로젝트의 최종 목표는 **그래프 출력 + 그 의미 해석**이다. 해석은 **실제 한국은행 보고서에 넣어도 될 만큼(report-grade)** 구체적이어야 한다.

**핵심 원칙**: 해석은 자유 텍스트가 아니라 **데이터로 검증 가능한 주장(claim)의 묶음**으로 정답을 만든다. 보고서는 **목적(purpose)의 씨앗**이며, 사실은 **fixture 데이터에서 도출**한다. **모든 사실 문장은 최소 1개 claim에 매핑**되어야 하며, 매핑 없는 사실 문장은 환각으로 집계한다.

> 근거: `research/그림표-분석/그림표_마스터.csv`의 `분석 목적`은 3,589/4,027행에 있으나 대부분 정형 문구 + `(추정)`이고, `설명`은 추출이 깨진 조각이 많아 그대로 정답으로 쓸 수 없다.

#### 해석 품질 기준 (report-grade: 6요소)

보고서급 해석은 아래 6요소를 담는다. 각 요소는 claim으로 뒷받침된다.

| 요소 | 내용 | 뒷받침 claim |
|---|---|---|
| A. 요약(lead) | 기간 + 방향 + 수준을 한 문장으로 | `direction` + `level` |
| B. 추세 | 시작→끝 방향, 연중 변동폭 | `direction` + `change` |
| C. 국면 | 저점·고점 시점, 전환점 | `extreme` + `turning_point` |
| D. 구간별 속도 | 상·하반기 등 구간별 상승/하락 속도 | `subperiod` + `pace` |
| E. 수준 맥락 | 기준선·전기 대비 등 (근거 있는 경우만) | `context` (출처 필수) |
| F. 시사점 | 근거 범위 내 해석("~을 시사한다") | 데이터 기반, 단정 금지 |

- 인과 단정·미래 확정("~때문이다", "~할 것이다")은 정답으로 쓰지 않는다(§9).
- E(수준 맥락)는 데이터만으로 검증이 안 될 수 있다(예: 지수 기준선 100). 이 경우 `context` claim으로 두되 **`source_basis`에 출처(카탈로그 메타·도메인 노트)를 명시**해야 한다. 출처 없는 맥락 단정은 금지한다.

#### gold 스키마 (`gold.interpretation`)

```jsonc
"interpretation": {
  "status": "labeled",                 // labeled | not_labeled | not_applicable
  "report_grade": true,                // 6요소 충족 목표
  "purpose": "경제심리지수로 경기 심리 흐름을 점검",   // 보고서 분석목적(씨앗)
  "required_claims": [
    { "id": "c1", "type": "direction", "period": "2025-01~2025-12", "expected": "up" },
    { "id": "c2", "type": "change", "period": "2025-01~2025-12", "expected_delta": 5.0, "tolerance": 0.2 },
    { "id": "c3", "type": "extreme", "subtype": "min", "period": "202502", "value": 89.6 },
    { "id": "c4", "type": "extreme", "subtype": "max", "period": "202512", "value": 94.8 },
    { "id": "c5", "type": "subperiod", "period": "2025-01~2025-06", "metric": "pace", "expected": 0.26, "tolerance": 0.05 },
    { "id": "c6", "type": "subperiod", "period": "2025-07~2025-12", "metric": "pace", "expected": 0.58, "tolerance": 0.05 },
    { "id": "c7", "type": "turning_point", "period": "202502", "expected": "저점 후 상승 전환" }
  ],
  "acceptable_claims": [ ],            // 있어도 되고 없어도 되는 주장
  "context_claims": [                  // 도메인 맥락: source_basis 출처 필수
    { "id": "x1", "type": "context", "text": "지수가 기준선 100을 밑돌아 위축 국면",
      "source": "domain_note:ESI_기준=100" }
  ],
  "forbidden_claims": [                // 있으면 오답
    { "type": "hallucination", "text": "2025년에 하락", "reason": "데이터는 상승" },
    { "type": "forecast_as_fact", "text": "2026년에도 상승할 것", "reason": "전망은 정답 아님" }
  ],
  "rubric": [                          // 6요소별 0/1/2
    { "id": "A", "prompt": "요약: 기간·방향·수준을 한 문장으로 제시" },
    { "id": "B", "prompt": "추세: 시작→끝 방향과 변동폭을 수치로 제시" },
    { "id": "C", "prompt": "국면: 저점·고점·전환점을 시점과 함께 제시" },
    { "id": "D", "prompt": "구간별 속도: 구간을 나눠 변화 속도를 비교" },
    { "id": "E", "prompt": "수준 맥락: 기준선·전기 대비를 근거와 함께 제시" },
    { "id": "F", "prompt": "시사점: 인과·전망을 단정하지 않고 근거 범위에서 해석" }
  ],
  "reference_text": "보고서 문체의 참고 해석문 (사람이 데이터로 작성)",
  "source_basis": { "catalog_ids": [ ], "fixture": "fixtures/....json", "domain_notes": [ ] }
}
```

#### 주장 유형 (데이터로 검증 가능한 것)

| 유형 | 뜻 | 검증 |
|---|---|---|
| `direction` | 상승/하락/횡보 | fixture 기울기 |
| `level` | 특정 시점의 값 | fixture 값(오차 내) |
| `extreme` | 최고/최저 시점 | fixture min/max |
| `comparison` | 계열 간 우열 | 두 계열 값 비교 |
| `change` | 증감폭 | 값 차이 |
| `turning_point` | 국면 전환 시점 | 방향 변화 |
| `subperiod` | 구간별 추세 | 하위 구간 기울기 |
| `pace` | 변화 속도(구간당) | 값 차이/기간 수 |
| `volatility` | 변동성(범위·표준편차) | fixture 분포 |
| `context` | 도메인 맥락(데이터 외) | **출처 필요** (`source_basis`) |

**인과·전망은 데이터로 검증할 수 없다.** 정답으로 쓰지 않고, 근거 없는 단정은 `forbidden_claims`로 처리한다(§9 전망치 규칙과 동일).

#### 문장–주장 대응(grounding) 규칙

- 해석문의 **모든 사실 문장**은 ≥1개 claim에 매핑한다.
- 숫자를 말하는 문장은 반드시 해당 `period`의 fixture 값과 연결한다.
- 매핑 없는 사실 문장은 **환각**으로 집계한다. (허용 배수는 validator가 명시)

#### 채점 (혼합 방식)

기계 검증 가능한 주장과 서술 품질을 분리한다.

1. **claim recall** (자동): `required_claims` 중 포함된 비율.
2. **factual consistency** (자동): 포함된 주장의 수치·방향·시점이 fixture와 일치하는 비율.
3. **unsupported-claim rate = 환각률** (자동): fixture로 지지되지 않는 주장을 말한 비율. `forbidden_claims` 적중은 즉시 오답. **가장 중요한 지표.**
4. **coverage** (자동): report-grade 6요소 중 충족한 요소 수.
5. **rubric** (사람): 6요소별 0/1/2, `reference_text` 대조.

`reference_text`는 채점의 유일한 기준이 아니라 **사람 판정의 보조**다. 자동 판정만으로 "해석 정확"을 주장하지 않는다.

#### 데이터 제약

- 해석 gold는 §3.1의 fixture(로컬 CSV 스냅샷)가 있어야 만든다. 없으면 `not_labeled`.
- `context_claims`는 `source_basis`의 출처가 없으면 채택하지 않는다.
- 해석이 요구되지 않는 질의(예: `no_match`)는 `not_applicable`.

### 3.3 오답 함정·부정 케이스·실패 회귀

**원칙**: 골든셋은 **정답만 담지 않는다.** `gold`는 **정답 + 허용 + 금지(함정)** 를 함께 담고, 별도로 **부정 케이스**를 포함한다. 채점기는 (1) `gold`와 다르면 오답, (2) 금지 항목 적중은 **즉시 오답(원인까지 기록)** 으로 판정한다. 세상의 모든 오답을 미리 열거하지는 않는다 — 정답과 함정만 적으면 나머지는 자동 오답이 된다.

#### 3.3.1 hard negative (`discovery.forbidden_table_ids`)

- 비슷하지만 **틀린 표**를 명시한다. 냈다면 오답이며, "왜 헷갈렸는지"를 진단할 수 있다.
- 예: "수출물가지수" 질의에 `DT_404Y014`(생산자물가지수) 선택 금지. "경제심리지수"에 `DT_512Y013`(기업경기실사지수) 금지.
- sibling 통계군은 semantic family 기준으로 지정하고, catalog-neighbor를 보조로 둔다.

#### 3.3.2 부정 케이스 (negative cases)

`expected_status`가 `no_match` / `clarify` / `catalog_only`인 레코드는 **올바른 행동이 거부·질문**이다. 오답 정의를 명시한다.

| expected_status | 정답 행동 | 오답 처리 |
|---|---|---|
| `no_match` | 후보 없음/범위 밖 반환 | 임의의 표를 냈으면 오답. 헷갈리는 표는 `forbidden_table_ids`에 기록 |
| `clarify` | 역질문 + `acceptable_options` 제시 | 표를 확정했으면 오답. 불필요한 질문이면 `forbidden` |
| `catalog_only` | 카탈로그 검색 성공, 로컬 수치 없음 명시 | 로컬 수치를 지어냈으면 오답 (`forbidden_claims`) |

#### 3.3.3 실패 회귀셋 (`failures.jsonl`)

- 실제 평가 실행에서 틀린 출력을 `{ id, output, gold, failed_layer, reason }`로 기록한다.
- 목적: **버그 재발 방지**. 정답 파일(`dev/test.jsonl`)과 분리해 관리한다.
- holdout의 실패 기록은 **비공개 저장소**에만 둔다(§5).
- 개인정보·비공개 자료·비밀은 넣지 않는다.

## 4. 질의 생성 절차

1. **씨앗 선정**: `그림표_마스터.csv`에서 5개 발간물(통화신용정책·금융안정·경제전망·지급결제·연차)에 골고루 퍼지게 뽑고, §1 출처 필터를 적용한다.
2. **문장 생성 (LLM 보조 + 사람 검수)**: 씨앗을 LLM에 넣어 유형별 문장 후보를 생성한다. 문체 변주:
   - 공식 용어 / 일상 표현·별칭 / 조건 명시(기간·주기) / 복수 비교 / 모호 → 역질문 / 범위 밖 → no_match / 후속 → 멀티턴.
3. **정답 부여**:
   - 표 ID: 주제를 로컬 349표 카탈로그에서 매핑. 없으면 자연히 `no_match`/`catalog_only`가 된다.
   - 수치·그래프: 해당 `그림 원본 데이터.xlsx`의 시점·값·단위·계열.
   - 출처: 씨앗 보고서·그림 번호를 `source`에 기록.
4. **사람 검수**: 원문·카탈로그와 대조. `검수대장.csv`의 `확정값/검수상태` 워크플로를 따른다. 통과 시 `human_approved=true`.
5. **누수 방지**: holdout 배정 질의는 개발 중 잠근다. 질의 문장은 보고서 원문을 복사하지 않는다.

## 5. 분할·거버넌스

- **dev / test / holdout 3분할.** 9계층 × 질의유형이 각 분할에 **층화**되도록 배치한다.
- holdout 정답과 평가기는 **비공개 저장소**(`StatBridge-evaluation-private`)에만 둔다. 공개 저장소·프롬프트·검색 인덱스에 넣지 않는다.
- holdout은 개발·프롬프트·인덱싱·라벨 튜닝에 사용하지 않는다. holdout 질의에 정답·개발 피드백을 기록하지 않는다.
- `human_approved`는 사람 검수 통과 시에만 true. 기본 false. "사람 승인 N건"을 과장하지 않는다.
- 버전을 고정한다. 서로 다른 계열/버전 간 점수를 직접 비교하지 않는다.

## 6. 채점

- 계층별 지표를 따로 보고한다(정확도, P/R/F1, Recall@k, MRR 등).
- **최상위 KPI는 pass/fail 두 값**이며, fail이면 **처음 무너진 계층을 귀속**한다.
- 하나의 종합점수로 요약하지 않는다. 보고 시 "100%" 대신 **"계층 X: n/N"** 형식을 쓴다. 미측정은 `not_labeled`로 표기한다.
- 복수표 = 집합 완전일치 + P/R/F1. 모호 질의 = 필요 질문 여부와 선택지 적절성을 분리 채점.
- 해석(`interpretation`) = claim recall, factual consistency, **환각률**, coverage, rubric을 따로 보고(§3.2).
- 오답은 `correct` / `forbidden_hit` / `mismatch` / `not_labeled`로 분류해 보고한다. `forbidden` 적중은 원인까지 기록한다(§3.3).

## 7. 규모·비율 (초기 90건)

초기 **총 90건**을 층화해 제작하고, 스키마·검증기가 안정되면 확장한다.

### 7.1 3분할

| 분할 | 건수 | 비율 | 용도 |
|---|---:|---:|---|
| dev | 30 | 33% | 개발·규칙 조정 |
| test | 42 | 47% | 회귀 검사 |
| holdout | 18 | 20% | 블라인드 1회 (비공개) |

### 7.2 질의 유형 × 분할 (층화)

| 유형 | dev | test | holdout | 합계 | 비율 |
|---|---:|---:|---:|---:|---:|
| single | 12 | 18 | 6 | 36 | 40% |
| followup | 6 | 8 | 4 | 18 | 20% |
| multi | 4 | 6 | 3 | 13 | 14% |
| clarify | 4 | 6 | 3 | 13 | 14% |
| no_match | 3 | 3 | 1 | 7 | 8% |
| catalog_only | 1 | 1 | 1 | 3 | 3% |
| **합계** | **30** | **42** | **18** | **90** | 100% |

### 7.3 긍정 / 부정

| 성격 | 건수 | 비율 |
|---|---:|---:|
| 긍정(select: single+multi+followup+catalog_only) | 70 | 78% |
| clarify(역질문이 정답) | 13 | 14% |
| no_match(거부가 정답) | 7 | 8% |

### 7.4 계층별 라벨 비율 (90건 기준)

| 계층 | labeled | 비율 |
|---|---:|---:|
| `e2e_kpi` / `discovery` / `clarification` | 90 | 100% |
| `slots` | 81 | 90% |
| `concepts` | 72 | 80% |
| `plan` | 63 | 70% |
| `numeric` | 45 | 50% |
| `graph` | 30 | 33% |
| `interpretation` | 30 | 33% (graph 있는 건 전부) |

### 7.5 그래프·해석 내부 구성 (30건)

- single 그래프 20 (계열 1개), multi 그래프 10 (계열 2개, `comparison` claim 필수).
- `report_grade=true`(6요소) 12건, 나머지 18건은 요약~추세 3요소.
- fixture 계열 수 약 40 (single 20 + multi 10×2).
- 그래프 gold는 로컬 CSV가 있는 표에만 붙인다.

### 7.6 오답 함정·회귀·검수

- `forbidden_table_ids`(hard negative): 긍정 70건 중 약 14건(20%).
- `forbidden_claims`: 그래프·해석 30건 전부.
- 부정 케이스(clarify 13 + no_match 7) 오답 기준 100% 명시.
- dev+test(72건)·holdout(18건) 사람 검수 100%, 분할별 표본 재검수 30%.

## 8. 사후 검증 (구현 단계)

- `validator`: 구조·status 일관성·누수·층화·기간 검사 + `graph` fixture 존재·`fixture_sha256`·`snapshot_id`·`source_file_sha256` 일치 검사 + `forbidden_*` 필드 정합성 검사.
- `scorer`: dev/test prediction 채점 + 오답 분류(`forbidden_hit`/`mismatch`)와 `failures.jsonl` 생성.
- `tests`: validator 핵심 테스트.

구현은 별도 계획(writing-plans)으로 진행한다.

## 9. 범위 밖 (YAGNI)

- 가중 합성 종합점수.
- 자동 라벨 승격(사람 검수 대체).
- KOSIS 실시간 수치 일치 검사(초기에는 로컬 fixture 또는 `not_labeled`).
- 그래프 **시각 미학**(색·폰트·축 눈금 세부) 자동 채점. (`visual_checks`는 사람 검수)
- 해석의 **인과·전망 자동 채점**. 데이터로 검증할 수 없으므로 정답으로 쓰지 않고, 근거 없는 단정만 `forbidden_claims`로 처리한다.

## 부록 A. 결정 이력

| 축 | 결정 |
|---|---|
| 검증 대상(SUT) | 계층형 통합 (KPI + 단계 진단) |
| 구조 | 단일 평면 레코드 (한 질의에 모든 gold 필드) |
| 입력 단위 | `prior_turns` 옵션 (단일 턴 + 멀티턴 허용) |
| gold 계층 | 9층 전부 |
| 분할·승인 | dev/test/holdout 3분할 + 층화 + 블라인드 holdout + 사람 승인 |
| 채점 | 계층별 지표 + KPI pass/fail + 원인 귀속 |
| 질의 생성 | LLM 보조 생성 + 사람 검수 |
| 범위 밖 씨앗 | 일부를 no_match 부정 케이스로 활용 |
| 그래프 | `graph` 계층 + fixture 스냅샷, `graph_data_exact`/`graph_e2e` 두 모드 분리 |
| 해석 | `interpretation` 계층 추가, 구조화 claim + 사람 rubric 혼합 채점 |
| 오답 처리 | 정답 + 허용 + 금지(함정) + 부정 케이스; `forbidden_table_ids`(hard negative), `failures.jsonl` 회귀 |
| 규모·비율 | 초기 90건 (dev30/test42/holdout18), single40/followup20/multi14/clarify14/no_match8/catalog_only3, 긍정78% |

## 부록 B. 참고 근거

- `docs/evaluation/평가-설계.md`, `docs/evaluation/골든셋-현황과-개선안.md`, `docs/evaluation/질의-탐색-평가-기준.md`
- `eval/README.md`, `data/kosis/hankook_tables.json` (349표), `research/그림표-분석/그림표_마스터.csv` (4,027행)
