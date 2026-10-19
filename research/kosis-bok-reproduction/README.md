# KOSIS 한국은행 통계로 만드는 보고서 표·그래프

2026-10-19 조사·검증 자료. ai-assisted, 사람 검수 미완료. 초기 조사 후 수치 차이 해결 작업에서 앱의 실행 근거 표시와 안전한 CSV 갱신 도구를 추가했다. [해결 결과 및 전체 범위 원본 표](해결결과.md)를 먼저 확인한다.

**먼저 [실행 확인 질의집](질의집.md#실행-확인-질의-바로-사용하기)을 사용한다.** 조사 확장 범위·한계·개선 순서·skill 추천은 [조사보고서](조사보고서.md), 명령과 검증 범위는 [검증기록](검증기록.md)에 있다.

| 확인한 범위 | 결과 |
|---|---:|
| 공식 게시물 목록 | 1,021건 |
| 선정 대표판·통계 개편 자료 | 70건 |
| 수집 첨부 | PDF 75개 + XLSX 21개 |
| PDF 텍스트 선별 | 3,384페이지, 캡션 후보 917건 |
| 기존 추출물 전체 선별 | 4,027건 중 제목 일치 후보 770건 |
| 원본에 연결한 제작 대상 | 36개 유형 |
| 실제 API 질의 검증 | 144개 변형 중 96개 통과 |
| 그래프·표·XLSX 출력을 확인한 유형 | 33개 |
| KOSIS–로컬 CSV 지정 시점 대조 | 갱신 후 45개 중 45개 일치 |
| 공식 PDF 금리 표본 대조 | 10개 중 10개 일치 |
| 원본 표 전체 수치 셀 대조 | 금리 78/78, 가계신용 260/260 |
| 디자인·빈티지 포함 원본 전체 동일성 검증 | 0건 |

144개는 36개 유형의 업무형·ID 포함형 × 그래프·표 변형이다. 표본을 보고 수정한 질의가 포함된 기능 점검이며, 블라인드 자연어 정확도나 기존 평가셋의 공식 성능이 아니다. 캡션 후보와 제목 일치 후보도 검증된 재현 수에 합산하지 않는다.

전체 계열·기간·가공·수치·디자인을 재현했다는 뜻으로 사용하지 않는다. 현재 질의집은 원본의 일부 계열·기간을 활용한 응용형이다. PG·선불전자지급수단은 원천 최종변경일이 다른 로컬 자료를 전체 범위 대조 후 백업·갱신해 차이를 해소했다. 대외금융부채·순대외금융자산·제조업 산업별대출금의 세 후보는 현재 작성한 질의로 기대 계열의 출력을 확인하지 못했다.

## 산출물

| 파일 | 읽는 방법 |
|---|---|
| [조사목록.csv](조사목록.csv) | 목록 단위 선정·제외 사유와 공식 URL |
| [원본목록.csv](원본목록.csv) | 첨부파일명·공식 첨부 URL·SHA-256 |
| [확장그림표_후보.csv](확장그림표_후보.csv) | 전체 선정 PDF의 텍스트 규칙 후보; 본문·목차 오탐과 무번호 그림 누락 가능 |
| [기존추출물_선별.csv](기존추출물_선별.csv) | 기존 결과물ID 보존, 제목 기반 후보 표만 제안 |
| [재현매핑.csv](재현매핑.csv) | 36개 유형의 원본 PDF 페이지·표/항목/분류 코드·제약·실행 판정 |
| [질의집.md](질의집.md) | 실행 확인 입력을 먼저 제시하고 실패 변형을 상세히 구분 |
| [질의집.jsonl](질의집.jsonl) | 같은 질의의 기계 판독용 조사 명세와 기대 조건; 런타임 예측 결과 미포함 |

기존 결과물ID는 [`../그림표-분석/그림표_마스터.csv`](../그림표-분석/그림표_마스터.csv)에 연결한다. 새 후보의 `CAP-…` ID는 게시물·첨부 해시·물리 페이지·캡션을 바탕으로 만들었다. PDF 표기 페이지와 뷰어의 물리 페이지는 다를 수 있다.

## 실행 환경과 재현

수집·원자료·실행 로그·그래프·표 파일은 Git에서 제외되는 프로젝트 `.venv/cache/kosis-bok-reproduction/`에 있다. 공개 조사 명세에 키·원자료 수치·예측 계획을 포함하지 않는다.

```bash
# PDF·XLSX·requests가 준비된 Python을 사용한다.
python research/kosis-bok-reproduction/collect.py --fetch
python research/kosis-bok-reproduction/build.py --extract-inventory
python research/kosis-bok-reproduction/build.py --verify
python research/kosis-bok-reproduction/audit_values.py --live
python research/kosis-bok-reproduction/pilots.py
python -m pytest -q research/kosis-bok-reproduction/test_reproduction.py
```

- `collect.py --fetch`: 한국은행 공개 목록·대표판을 로컬 캐시에 수집한다. 기존 캐시는 재사용한다. 동일 첨부 URL의 정정본까지 확인하려면 별도 캐시를 보존한 뒤 새로 수집해 해시를 비교해야 한다.
- `build.py --extract-inventory`: 캐시만 읽어 캡션 후보와 조사 산출물을 작성한다. 그림·표의 시각 검수나 재현 가능성을 자동 승인하지 않는다.
- `build.py --verify`: 모델·벡터 검색·KOSIS 키를 사용하지 않고 현재 API와 CSV로 모든 질의를 새로 실행한다. 기존 성공·실패 결과를 재사용하지 않는다. 로그인 계정·세션은 검증 전용 저장소에 둔다.
- `build.py`만 실행하면 마지막 실행 스냅샷으로 문서를 다시 만든다. 이 명령은 새로운 실행 검증이 아니다.
- `audit_values.py --live`: 설정된 키로 각 기대 계열의 지정 시점 한 개를 실제 KOSIS에서 조회한다. 로컬 출처가 `local_csv`인지 확인한 뒤 대조하며, 키·응답 수치를 출력하거나 공개 파일에 기록하지 않는다. 전체 기간 일치를 뜻하지 않는다.

필요 패키지: 기존 프로젝트 실행 의존성 외 `openpyxl`, `pdfplumber`, `pypdfium2`. 이 작업에서는 Windows 가상환경을 유지하고 `/tmp/statbridge-research-venv`에서 검증했다. `/tmp` 환경은 영구 설치가 아니며 프로젝트 잠금 파일·의존성은 수정하지 않았다.

## 바로 볼 수 있는 로컬 예시

다음은 실제 API 출력으로 만든 응용형 그래프다. 원본 공식 그림을 복제한 파일이 아니다. HTML에는 Plotly를 포함해 인터넷 없이 열 수 있으며, `.venv/cache`의 생성물이므로 Git에 포함하지 않는다.

| 예시 | 그래프 | 표 |
|---|---|---|
| 경제심리지수 원계열 | [HTML](../../.venv/cache/kosis-bok-reproduction/previews/ESI-01.html) | [XLSX](../../.venv/cache/kosis-bok-reproduction/previews/ESI-01.xlsx) |
| 대기업·중소기업 신규 대출금리 | [HTML](../../.venv/cache/kosis-bok-reproduction/previews/RATE-03.html) | [XLSX](../../.venv/cache/kosis-bok-reproduction/previews/RATE-03.xlsx) |
| 원화 수출·수입물가지수 | [HTML](../../.venv/cache/kosis-bok-reproduction/previews/PRICE-02.html) | [XLSX](../../.venv/cache/kosis-bok-reproduction/previews/PRICE-02.xlsx) |
| 가계대출·판매신용 | [HTML](../../.venv/cache/kosis-bok-reproduction/previews/CREDIT-02.html) | [XLSX](../../.venv/cache/kosis-bok-reproduction/previews/CREDIT-02.xlsx) |
| 계좌이체 금액 | [HTML](../../.venv/cache/kosis-bok-reproduction/previews/PAY-03.html) | [XLSX](../../.venv/cache/kosis-bok-reproduction/previews/PAY-03.xlsx) |
