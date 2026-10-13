# 의존성 및 새 설치 검증

ai-assisted. 팀원 PC의 CMD 첫 설치 오류 후 local1의 npm·pnpm 및 Python 운영 의존성 전체를 새 환경에서 확인했다. 기존 PR #27의 후속 검증이다.

## 원인과 보완

1. 누락된 npm ECharts 의존성은 이전 후속 커밋에서 package-lock.json에 반영했다.
2. 기존 CMD는 Python 모듈과 일부 프런트엔드 모듈이 존재하면 설치를 생략했다. 따라서 패키지가 설치돼 있어도 요구 버전 또는 새 잠금 파일과 맞지 않는 환경을 놓칠 수 있었다.
3. Python 요구 버전과 marker를 importlib.metadata로 확인하고 pip check로 전이 의존성 충돌을 확인한다. 필요할 때 requirements를 설치하고 같은 검사 및 운영 모듈 import를 다시 확인한다. 실패하면 다음 단계로 진행하지 않는다.
4. 프런트엔드는 package.json과 npm 잠금 파일 해시를 설치 확인 기록과 비교한다. 직접 의존성의 실제 설치 버전도 잠금 파일과 비교한다. 최초 도입 또는 의존성 변경 시 npm ci를 다시 실행하며 성공한 설치만 기록한다. pnpm 설치를 사용했던 환경도 CMD가 사용하는 npm 잠금 파일 기준으로 확인한다.
5. npm audit에서 source-map-js 1.2.1의 고위험 경고 GHSA-68fv-2mgg-jv7q를 발견했다. npm 잠금 파일을 1.2.2로 갱신했고 pnpm 잠금 파일도 이미 1.2.2임을 확인했다. 최종 npm audit 전체 결과는 취약점 0건이다.

## 실제 설치 검증

- Windows x64, Python 3.11, Node 24.21.0, npm 11.19.0, pnpm 12.4.2 환경에서 검증했다.
- 기존 프로젝트 node_modules를 사용하지 않는 별도 캐시 폴더에서 npm ci → TypeScript/Vite 전체 빌드 성공.
- 별도 캐시 폴더에서 pnpm install --frozen-lockfile → TypeScript/Vite 전체 빌드 성공.
- 보안 패치 이후 두 경로 모두 재설치와 전체 빌드를 다시 실행해 성공했다.
- Python 3.11의 빈 가상환경에 src/backend/requirements.txt 전체 설치 성공. pip check 결과 No broken requirements found.
- 새 환경에서 모든 CMD 운영 모듈과 bridge_api import 성공. 운영 Python 코드의 외부 import 목록도 확인했다.
- 기존 설치 검사에서 기록 없음·manifest 변경·잘못된 설치 버전·누락된 Python 패키지·지원하지 않는 버전을 거절하는 테스트를 포함한다.

검증 캐시와 원본 로그는 .venv/cache/dependency-* 및 npm-clean-validation/pnpm-clean-validation에만 저장하고 Git에서 제외한다. 기존 사용 환경의 node_modules와 서버를 설치 검증으로 변경하지 않았다.

## 한계

팀원 PC 자체와 Python 3.12–3.14, 다른 OS·CPU·Node 지원 버전을 모두 실행한 결과는 아니다. npm audit는 검사 시점의 npm 공개 권고를 확인한 것이며 Python 취약점 전수 감사를 뜻하지 않는다. 인터넷 없이 첫 설치할 수 있다고 주장하지 않는다. 기존 큰 프런트엔드 번들 경고는 남아 있다. 새 Python 환경 전체 테스트 최종 결과는 아래에 실제 완료 후 기록한다.

## 최종 결과

- 새 Python 3.11 환경 전체 회귀: **749 passed, 355 subtests passed**, 464.27초. 실행 시작 시점에 수집한 테스트 기준이다.
- 실행 중 추가한 프런트엔드 설치 기록 검사를 포함한 최종 집중 검사: **4 passed** (새 환경, 구조 검사 2개와 의존성 검사 2개). 추가 검사까지 포함한 전체 테스트를 다시 실행한 수치로 주장하지 않는다.
- 격리 npm 설치의 프런트엔드 검사: **9 passed**, 실패 0개.
- 공개 v4.1 validator: VALIDATION OK.
- npm 개발 서버 시작 및 실제 HTTP 200 확인 후 임시 서버 종료.
- 최종 npm 전체 audit: 취약점 0건. npm/pnpm 최종 설치·전체 빌드 모두 성공.
- Windows npm ci와 설치 기록 검사·Node 검사·빌드를 실행하는 CI 작업을 추가했다. 기존 Python CI에도 의존성 검사와 Node 준비를 추가했다. YAML 파싱 통과. GitHub 새 CI 실행은 별도 상태로 확인한다.
