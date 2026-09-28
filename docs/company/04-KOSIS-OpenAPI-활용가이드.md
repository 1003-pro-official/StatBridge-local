# KOSIS Open API 활용 가이드 — 호출 예시·파라미터 정리

- 출처: https://psychedelic-uncle-650.notion.site/3d631c089bcd806a93dcf46c4dc94c4b?p=3d631c089bcd802eb898e01e0a3bc177
- 소속: "한국은행통계 탐색시각화에이전트 프로젝트" 하위 페이지 (참고자료)
- 수집일: 2026-09-14
- 성격: KOSIS Open API 3종 호출 예시와 파라미터·응답 필드 정리 (원문 보존)

> 참고: 원문의 코드는 그대로 옮겼으며, `apiKey`는 빈 값으로 표기되어 있습니다. 실행 시 본인 인증키를 넣어야 합니다.

> **정정 안내 (2026-09-14, KOSIS-001·KOSIS-006)** — 실검증 결과 원문과 다른 부분이 있어 아래 2건을 정정 표기합니다. 원문은 보존하되, **정정 표기가 있는 쪽을 따르세요.**
>
> | # | 정정 내용 | 근거 |
> |---|---|---|
> | 1 | 통계목록 조회의 트리 파라미터는 `parentId`가 아니라 **`parentListId`** 다. `parentId`는 API가 **무시**하며, 최상위(기관 목록) 조회 시에는 parent 파라미터를 **생략**해야 한다(`parentListId="A"`는 예외). | `docs/운영/이슈-및-오류-정리.md` KOSIS-001 |
> | 2 | **오류 응답도 HTTP 200으로 온다.** 본문이 `{"err":"21","errMsg":"..."}` 형태의 JSON 객체이므로, `status_code`만 확인하면 오류를 정상으로 오인한다. 응답이 `dict`이고 `err` 키가 있으면 오류로 처리한다. | `docs/운영/이슈-및-오류-정리.md` KOSIS-006 |

---

## 1. 통계자료 조회 — `statisticsParameterData.do`

통계표를 직접 선택해서 수치 데이터를 조회할 때 사용하는 엔드포인트.

```python
import requests

url = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
params = {
    "method": "getList",
    "apiKey": "",
    "orgId": "101",
    "tblId": "DT_1B8000G",
    "itmId": "T1+",
    "objL1": "ALL",
    "objL2": "ALL",
    "objL3": "",
    "objL4": "",
    "objL5": "",
    "objL6": "",
    "objL7": "",
    "objL8": "",
    "prdSe": "M",
    "newEstPrdCnt": "1",
    "prdInterval": "2024",
    "format": "json",
}
r = requests.get(url, params=params)
r.raise_for_status()
print("요청 URL:\n", r.url)
data = r.json()
print("\n레코드 수:", len(data))
print("첫 행:", data[0])
```

**결과**

```
요청 URL:{실제 URL 정보} 레코드 수:181
첫 행:{'C1_OBJ_NM': '행정구역별', 'C2_NM': '출생아수(명)', 'DT': '26916', 'C2': '10', 'C1': '00',
'PRD_SE': 'M', 'UNIT_NM_ENG': 'Case Person', 'ITM_ID': 'T1', 'TBL_ID': 'DT_1B8000G',
'ITM_NM': '출생사망혼인이혼', 'TBL_NM': '월.분기.연간 인구동향(출생사망혼인이혼)', 'PRD_DE': '202601',
'LST_CHN_DE': '2026-03-23', 'C1_NM_ENG': 'Whole country', 'C1_NM': '전국', 'UNIT_NM': '명 건',
'ITM_NM_ENG': 'Vital Statistics by Month', 'C2_OBJ_NM_ENG': 'By the kind',
'C2_NM_ENG': 'Live births(persons)', 'ORG_ID': '101',
'C1_OBJ_NM_ENG': 'By administrative divisions', 'C2_OBJ_NM': '종류별'}
```

**파라미터**

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| url | 호출할 API 주소 | - | `statisticsParameterData.do` — 통계표를 직접 선택해 데이터 조회 |
| method | API 동작 방식 | 필수 | `"getList"` : 목록 형태의 통계 데이터 조회 |
| apiKey | KOSIS에서 발급받은 인증키 | 필수 | 발급받은 API Key 입력 |

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| orgId | 기관 ID | 필수 | 어떤 기관이 제공하는 통계인지 지정 |
| tblId | 통계표 ID | 필수 | 어떤 표를 조회할지 지정하는 핵심 값 |

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| itmId | 항목 ID | 필수 | 남녀, 전체, 비율, 건수 등 "무엇을 볼지" 지정 |
| objL1 | 분류1(첫 번째 분류코드) | 필수 | 예: 지역, 성별, 연령, 산업분류 |
| objL2 ~ objL8 | 분류2 ~ 분류8 | 선택 | 표가 여러 차원으로 구성돼 있으면 추가 분류값 입력 |
| ALL | 해당 분류의 전체값(전체 범주) | - | 예: `objL1="ALL"` 이면 해당 분류 전체 기준 조회 |

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| prdSe | 수록주기 | 필수 | D=일, M=월, Q=분기, H=반기, Y=연, F=다년 주기, IR=부정기 |
| newEstPrdCnt | 최신자료 기준 최근 수록시점 개수 | 선택 | `"1"` 이면 가장 최근 시점 1개 조회 |
| prdInterval | 수록시점 간격 | 선택 | 예: 2개 시점 간격으로 조회할 때 사용 |
| prdInterval 주의사항 | 특정 연도를 넣는 칸이 아니라 간격값을 넣는 용도 | - | `prdInterval="2024"` 는 의미상 어색할 수 있음 |
| 시점 지정 방식 | 특정 연도/기간 조회 시 보통 `startPrdDe`, `endPrdDe` 사용 | - | 월 주기(M)는 보통 `YYYYMM` 형식 |

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| format | 결과 형식 | 필수 | `"json"` 이면 JSON으로 응답 |

---

## 2. 통계목록 조회 — `statisticsList.do`

> **정정 (KOSIS-001)** — 원문은 `parentId`를 사용하지만 **실제로는 무시된다.** 올바른 이름은 `parentListId`이며, **최상위(기관 목록) 조회 시에는 parent 파라미터를 생략**한다(`parentListId="A"`는 예외 발생). 하위 탐색은 직전 응답의 `LIST_ID`를 `parentListId`로 넘긴다.

```python
import requests

url = "https://kosis.kr/openapi/statisticsList.do"
params = {
    "method": "getList",
    "apiKey": "",
    "vwCd": "MT_OTITLE",      # 국내통계 기관별
    # 정정(KOSIS-001): 원문 "parentId": "A" → 실제 파라미터는 parentListId.
    #   최상위(기관 목록)는 parent 파라미터를 생략한다 → 182건
    #   하위 탐색: 직전 응답의 LIST_ID를 parentListId로 전달 (예: "301" = 한국은행)
    "format": "json",
    "jsonVD": "Y",            # KOSIS JSON 표준화 (안전)
}
r = requests.get(url, params=params)
r.raise_for_status()
print("요청 URL:", r.url)
data = r.json()
print("항목 수:", len(data))
print(data[0])
```

**결과**

```
요청 URL:{실제 URL 정보} 항목 수:182
{'LIST_NM': '근로복지공단', 'LIST_ID': '439', 'VW_NM': '국내통계 기관별', 'VW_CD': 'MT_OTITLE'}
```

통계목록 API의 요청 URL은 `https://kosis.kr/openapi/statisticsList.do?method=getList` 형태로 안내 ([KOSIS 개발가이드](https://kosis.kr/openapi/devGuide/devGuide_0101List.do)).

**파라미터**

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| url | 호출할 API 주소 | - | `statisticsList.do` — 통계목록 조회 API |
| method | API 동작 방식 | 필수 | `"getList"` : 목록 조회 |
| apiKey | KOSIS에서 발급받은 인증키 | 필수 | Open API 신청 후 발급받은 key 입력 |

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| vwCd | 서비스뷰 코드 | 필수 | 어떤 기준으로 통계목록을 탐색할지 지정 |
| parentListId | 시작목록 ID | **조건부**(최상위는 생략) | **정정(KOSIS-001)**: 원문 `parentId`는 API가 무시한다. 트리 구조에서 어느 노드부터 조회할지 지정 |

**vwCd 값**

| 값 | 의미 |
|---|---|
| MT_ZTITLE | 국내통계 주제별 |
| MT_OTITLE | 국내통계 기관별 |
| MT_GTITLE01 | e-지방지표(주제별) |
| MT_GTITLE02 | e-지방지표(지역별) |
| MT_CHOSUN_TITLE | 광복이전통계(1908~1943) |
| MT_HANKUK_TITLE | 대한민국통계연감 |
| MT_STOP_TITLE | 작성중지통계 |
| MT_RTITLE | 국제통계 |
| MT_BUKHAN | 북한통계 |
| MT_TM1_TITLE | 대상별통계 |
| MT_TM2_TITLE | 이슈별통계 |
| MT_ETITLE | 영문 KOSIS |

| 파라미터 | 의미 | 예시 / 비고 |
|---|---|---|
| parentListId | 시작 노드(시작 목록 ID) | **정정(KOSIS-001)**: 원문 `parentId` → `parentListId`. 최상위는 파라미터 생략 |
| 활용 방식 | 트리 구조 탐색용 | 상위 노드를 조회하고, 반환된 `LIST_ID`를 다음 `parentListId`로 넣어 하위 목록 탐색 |

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| format | 결과 유형 | 필수 | 공식 가이드에는 `json` 으로 안내 |

**응답 필드**

| 응답 필드 | 의미 |
|---|---|
| VW_CD | 서비스뷰 ID |
| VW_NM | 서비스뷰명 |
| LIST_ID | 목록 ID |
| LIST_NM | 목록명 |
| ORG_ID | 기관코드 |
| TBL_ID | 통계표 ID |
| TBL_NM | 통계표명 |
| STAT_ID | 통계조사 ID |
| SEND_DE | 최종갱신일 |
| REC_TBL_SE | 추천 통계표 여부 |

| 파라미터 | 의미 | 공식 가이드 기준 | 비고 |
|---|---|---|---|
| content | 헤더 유형 | 선택 | `html`, `json` 가능 |
| jsonVD | JSON 표준화 관련 옵션 | . | "KOSIS JSON 표준화(안전)" 주석으로 사용 |

---

## 3. 대용량 통계자료 조회 — `statisticsBigData.do`

```python
import requests

API_URL = "https://kosis.kr/openapi/statisticsBigData.do"
params = {
    "method": "getList",
    "apiKey": "",
    "userStatsId": "DT_1B8000G",
    "type": "DSD",       # 문서에 나온 SDMX 유형
    "format": "sdmx",    # 결과 유형
    # "version": "new"   # 필요 시만 추가
}
response = requests.get(API_URL, params=params, timeout=30)
print("요청 URL:", response.url)
print("상태 코드:", response.status_code)
print(response.text[:2000])
```

**결과**: 공식 사이트에서 확인 필요.

공식 가이드의 요청 URL은 `https://kosis.kr/openapi/statisticsBigData.do?method=getList` 형태로 안내 ([KOSIS 개발가이드](https://kosis.kr/openapi/devGuide/devGuide_030101List.do)).

**파라미터**

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| API_URL | 호출할 API 주소 | - | `statisticsBigData.do` — 대용량 통계자료 조회 API |
| method | API 동작 방식 | 필수 | `"getList"` : 대용량 통계자료 목록/구조 조회 |
| apiKey | KOSIS에서 발급받은 인증키 | 필수 | Open API 신청 후 발급받은 key 입력 |

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| userStatsId | 사용자 등록 통계표 ID | 필수 | 예: `DT_1B8000G` |

| 파라미터 | 의미 | 필수 여부 | 예시 / 비고 |
|---|---|---|---|
| type | SDMX 유형 | 필수 | 가이드에는 `DSD` 로 안내 |
| format | 결과 유형 | 필수 | `sdmx` |
| version | 결과값 구분 | 선택 | 생략 시 구버전으로 출력 |

| 항목 | 내용 |
|---|---|
| SDMX 제공 제한 | 데이터 출력건수가 40,000개 이상이면 SDMX 제공 불가 |
| XLS 제공 제한 | 데이터 출력건수가 200,000개 이상이면 XLS도 제공 불가 |
| 사용 권장 방식 | 조회 건수를 줄여서 사용 |

특히 `type="DSD"` 일 때는 실제 수치 데이터 자체보다 **통계표 구조(코드리스트, 컨셉, 디멘전 구조)** 를 보는 데 가까운 응답이 나오게 됨.

**응답 항목 예**

| 응답 항목 예 | 의미 |
|---|---|
| Header | 기관코드_통계표ID, 전송시간, 전송기관 정보 등 |
| Codelist | 코드리스트 ID, 코드명, 설명 |
| Concepts | 컨셉 스키마, 컨셉 ID/명 |
| DataStructures | 통계표 구조, 디멘전 정보 |

---

## 참고 링크

- KOSIS Open API 개발가이드: https://kosis.kr/openapi/devGuide/devGuide_0101List.do
- 통계자료 조회(statisticsParameterData): https://kosis.kr/openapi/Param/statisticsParameterData.do
- 통계목록 조회(statisticsList): https://kosis.kr/openapi/statisticsList.do
- 대용량 조회(statisticsBigData): https://kosis.kr/openapi/statisticsBigData.do
