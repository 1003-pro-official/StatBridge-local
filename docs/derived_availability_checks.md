# 계산 전 원자료 확인 (ai-assisted)

`아직 계산하지 마` 등 명시적인 자료 확인 요청은 일반 계산 계획과 분리합니다. `DerivedIndicatorRuntime.plan` → `derived_availability.check_availability` 경로입니다. 계산 엔진과 OutputAgent를 호출하지 않습니다.

## 실제 API 근거

`tools/refresh_derived_api_inventory.py`는 로컬 등록 목록을 승인 ID 경계로만 사용합니다. 표명·항목·분류·주기·수록기간은 각각 승인된 한국은행 349개 표에 대한 실제 KOSIS TBL/ITM/PRD API에서 가져옵니다. 349개 전부 성공하고 승인 ID 집합이 일치해야 완성된 스냅샷을 사용합니다. 해시·완료 시각·출처를 보존합니다. 키·요청 URL·연락처는 모델과 결과 파일에 넣지 않습니다.

완성한 공개 메타데이터 캐시는 `runtime_data/derived_api_inventory/inventory.json`에 저장하고 24시간 동안 재사용합니다. 첫 요청에 캐시가 없으면 백그라운드에서 확인하며 UI에는 `verifying`와 진행 수를 반환합니다. API 실패는 `verification_failed`이며, 로컬 메타데이터로 성공을 대체하지 않습니다. 오래되거나 누락되거나 해시가 다른 캐시도 근거로 사용하지 않습니다. KOSIS 키가 없으면 실제 확인 실패를 안내합니다.

명시적으로 갱신하려면 프로젝트 루트에서 다음 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe tools/refresh_derived_api_inventory.py
```

공급자의 호출 제한을 지킵니다. 최초 전수 갱신은 1,047개 API 호출이므로 시간이 필요하며 매 사용자 요청마다 전수 조회하지 않습니다. 기존 API 키는 루트 `.env`에서만 읽습니다.

## 의미·항목·관측값 검증

GPT-5.4는 사용자 질문에서 필요한 시계열(각각 하나), 기간, 필요한 단위/호가 방향, 경제 개념 검색어와 미확정 조건을 구조화합니다. 숫자 관측값이나 수식을 생성하지 않습니다. 서버가 전체 실제 API 메타데이터의 표명·항목·분류를 검색합니다. 검색 결과와 사용자 미확정 조건은 별개 필드입니다.

후보가 있으면 실제 메타데이터로 항목·분류를 선택하고 서버가 ID를 검증합니다. 기간·주기가 실제 PRD에 포함되는 경우만 기존 KOSIS 서비스로 실제 원자료를 조회합니다. 로컬 CSV와 실패 시 대체 조회는 금지합니다. API 응답 출처·유효한 관측값·실제 단위를 검증한 경우만 `available`입니다. API 실패·수록기간 불일치·미확정 기간을 확보 완료로 표시하지 않습니다.

경제 개념 검색 결과가 없다는 `not_found`는 확인한 승인 349개 범위에서 해당 검색 개념이 확인되지 않았다는 뜻입니다. KOSIS 전체나 ECOS 전체에 자료가 없다는 주장은 아닙니다. 모델의 개념 해석 정확성에 대한 한계는 남으며, 원자료를 찾지 못했을 때 다른 경제지표로 대체하지 않습니다. 필요한 입력 단위는 실제 API 단위와 구분해서 표시합니다.

## 응답·UI 계약

계산 전 확인은 HTTP 응답 `status=need_details`, `availability` 객체, 정상적인 조건 질문입니다. `availability.status`는 `verifying`, `verification_failed`, `checked`이고 각 source는 `not_found`, `selection_required`, `api_error`, `available`로 구분합니다. 확인 결과에는 확인 표 수, 완료 시각, 해시, 필요한 자료별 기간·주기·단위·호가 방향·공식 입수처를 포함합니다. 원자료 확인과 관련한 실제 모델 사용량·시간은 소유자별 계산 근거 기록에 보존합니다.

조건 입력은 전용 폼에서 같은 질문에 추가 조건으로 전달합니다. 계산 요청이 아닌 재확인 단계입니다. 오류용 메시지와 빨간 경고 상자를 사용하지 않습니다. 자료 확인 단계에는 파일 선택창을 만들지 않습니다. 기존 파일 보완 UI는 실제 보완 입력 목록 또는 연결한 파일이 있는 경우에만 표시하며, 빈 작업공간/조건 확인만으로 노출하지 않습니다. CSV·JSON·TSV·XLSX 지원 안내와 실제 파일 선택창은 구분합니다.

## 외부 입수처 안내

외부 사이트는 사용자가 확인할 입수처 링크이며 계산용 외부 API 호출 권한이 아닙니다. 사용자 파일을 KOSIS 자료로 표시하지 않습니다.

- 정확한 DXY는 [ICE U.S. Dollar Index](https://www.ice.com/fixed-income-data-services/index-solutions/currency-indices)입니다. ICE 공식 페이지에서 심볼 DXY를 확인했습니다. 과거 파일의 무료 제공·이용권한은 확인이 필요하며 FRED 무역가중 지수나 달러 선물 가격으로 대체하지 않습니다.
- [연준 H.10 Country Data](https://www.federalreserve.gov/releases/h10/hist/)에서 통화별 과거 환율 페이지와 자료 정의를 확인했습니다. 뉴욕 정오 매입환율이므로 한국은행 관측시각과 동일하다고 가정하지 않습니다. 각 통화에 해당하는 공식 페이지를 직접 안내합니다.
- 인도네시아 루피아는 H.10 목록에 없어 [Bank Indonesia JISDOR](https://www.bi.go.id/en/statistik/informasi-kurs/jisdor/default.aspx)를 안내합니다. JISDOR는 USD/IDR 현물 기준입니다. 월평균 집계는 기준을 별도로 확인해야 합니다.
- [한국은행 ECOS](https://ecos.bok.or.kr/)는 해당 통화의 대미달러환율 검색 후보입니다. 승인된 KOSIS 349개와 같은 자료 집합이라고 주장하지 않습니다.

관측시각, 일별/월평균, 종가/평균값, 통화 방향이 다른 파일을 같은 원자료라고 간주하지 않습니다. 공식 지수나 관측값을 만들어서 빈 값을 채우지 않습니다.
