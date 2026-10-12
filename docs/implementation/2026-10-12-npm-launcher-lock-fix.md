# Windows CMD npm 설치 오류 수정

팀원의 새 설치에서 START_STATBRIDGE.cmd 5단계가 `npm ci`의 EUSAGE로 중단됐다. package.json과 pnpm-lock.yaml에는 ECharts가 반영됐지만 package-lock.json에는 ECharts, zrender, tslib가 누락돼 있었다. 기존 node_modules가 있는 개발 환경과 pnpm 빌드만으로는 이 오류가 드러나지 않았다.

현재 package.json을 기준으로 npm 잠금 파일을 다시 생성했다. 실패를 숨기는 npm install 자동 재시도는 추가하지 않고 기존 npm ci의 일관된 설치를 유지한다.

## 실제 검증

- `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` 성공
- 기존 node_modules를 사용하지 않는 별도 빈 캐시 폴더에 package.json과 package-lock.json만 복사
- 그 폴더에서 `npm ci --no-audit --no-fund` 성공
- 설치된 vite, echarts, zrender, tslib, plotly.js-dist-min의 모듈 경로 확인
- TypeScript `--noEmit` 검사 성공. 이 검사는 프로젝트의 기존 타입 의존성 경로도 사용하므로 깨끗한 전체 앱 빌드와 구분한다.

로그와 설치 검증 폴더는 .venv/cache에 남기고 Git에서 제외한다. 팀원 PC 자체의 CMD 재실행은 아직 확인하지 않았다. 최신 브랜치의 package-lock.json을 함께 받은 뒤 START_STATBRIDGE.cmd를 다시 실행하면 된다.

ai-assisted 변경. 기존 PR #27의 후속 수정이다.
