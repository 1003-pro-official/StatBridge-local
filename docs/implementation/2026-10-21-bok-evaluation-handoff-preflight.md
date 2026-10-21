# BOK v1.2 평가 패키지 사전 점검

ai-assisted · 2026-10-21. 제품 E2E 평가 또는 공식 성능 결과가 아니다.

## 확인 결과

- 사용자 지정 위치에서 실제 발견한 파일명은 `bok-evaluation-reviewer-handoff-v1.2.zip`이다.
- 원본 ZIP은 변경하지 않고 공개 검수용 파일을 `eval/bok-reproduction/v1/`에 추출했다.
- manifest에 기재된 포함 파일의 SHA-256은 모두 일치한다. 누락 파일은 `profiles.json`, `scripts/build.py`이다.
- HANDOFF에 명시된 대로 독립 실행용 고정 원자료와 수치 오라클은 ZIP에 포함되지 않았다. 확인한 프로젝트 내 실행 캐시에서도 발견되지 않았다.
- 파일럿 22건, 보완 24건, 사람 승인 0건이다. 자동 수치 정합성과 공식 승인 통과를 구분해야 한다.

## 실제 실행

저장소 루트에서 Windows 가상환경으로 실행했다.

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider eval/bok-reproduction/v1/tests
.venv/Scripts/python.exe eval/bok-reproduction/v1/scripts/evaluate.py validate
```

평가 도구 테스트: **37 passed, 1 failed**. 실패는 `scripts/build.py` 누락으로 `pilot_query`를 가져오지 못한 것이다. 패키지 검증은 `profiles.json` 부재로 실패했다. 이것은 앱의 46건 E2E 통과율이 아니다. 제품 코드·기대 계약·manifest·승인 상태는 수정하지 않았다. 유료 모델/API 호출은 하지 않았다.

## 재개에 필요한 자료

1. manifest와 해시가 일치하는 `profiles.json`, `scripts/build.py`.
2. 고정 평가 공급자 `provider.json` 및 독립 수치 정답 `oracles.json`. 해당 버전 manifest의 SHA와 일치해야 한다.
3. 보완 사례가 참조하는 이미지/PDF 및 초기 자료와 해시.
4. 보완 24건의 실제 모델/앱 경로를 실행하는 런타임 어댑터. 기본 오프라인 경로와 컴포넌트 두 건만으로 전체 모델 E2E 성공을 주장하지 않는다.
5. 공식 승인 결과를 원하면 담당자의 실제 골든 검수 및 응답 검수. 자동 승인이나 승인값 변경으로 대체하지 않는다.

원본 제작 환경에서 위 실행 자료를 포함한 별도 전체 패키지를 받아 격리 계정·세션으로 기준 실행을 만든 뒤, 재현된 제품 결함을 수정하고 동일 조건으로 재평가한다. 평가 누락 파일이나 숫자 정답을 제품 결과에서 역으로 만들어 채우지 않는다. 앱 계정·저장 분석·환경 설정은 변경하지 않았다.

## 채점용 ZIP 후속 점검

`bok-evaluation-scoring-handoff-v1.2.zip` SHA-256: `a15bdc6704fdc6381cda7ce4309876a3fa5828f0967630ba9d469444aadd0324`.

30개 정량 사례의 정답 파일이 추가됐다. 그러나 `profiles.json`, `scripts/build.py`, 고정 `provider.json`, 참조 자료 및 실제 행동 실행 어댑터는 추가되지 않았다. 포함 파일은 manifest 해시와 일치한다. 정답은 제품·모델 실행 입력이나 공급자로 사용하지 않았으며 소스 저장소에 추출하지 않았다.

제품 `DynamicExpressionExecutor.execute`로 공개 입력의 합성 계산 경계 `SUP-derived-04`를 별도로 실행했다. 관측 파일을 먼저 저장하고 SHA를 고정한 다음 별도 정답을 읽어 비교했다. 수치·단위·주기·달력 시점 직접 비교는 **5/5셀 일치**했다. 정식 `score_case`는 고정 provider SHA 증거가 없으므로 `source_vintage_mismatch`로 차단했다. 해당 검사를 우회하거나 정답의 provider 해시를 실제 관측처럼 채우지 않았다.

따라서 제품 계산기 1건의 수치 검사일 뿐 전체 E2E 통과 또는 공식 통과가 아니다. 이 실행에서 수정할 계산 결함은 발견되지 않았다. 제품 코드와 채점 기준은 변경하지 않았다. 실행·직접 수치 비교·정식 채점 결과는 `.venv/cache/kosis-bok-reproduction/scoring-handoff-20261021/`에 별도로 남겼다. 유료 호출 및 실제 API 호출은 0회다.
