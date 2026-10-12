# StatBridge3 UI 이식

2026-10-12, ai-assisted. 사용자의 요청에 따라 StatBridge3의 화면을 StatBridge-local1에 이식했다.

## 변경 범위

- 원본: `statbridge3/StatBridge-local/src/agent/frontend/src/`.
- 대상: local1의 `App.tsx`, `main.tsx`, 새 `professional.css`.
- 상단 내비게이션, 남색 메인 영역과 경제 시각화 SVG, 기능 안내, 이용 안내, 카탈로그 테마, 모바일 메뉴와 포커스 이동을 가져왔다.
- local1의 API 클라이언트·백엔드·환경 설정·패키지·스티커·수정이·보고서 컴포넌트는 이번 이식에서 교체하지 않았다. 이전 작업의 미커밋 변경도 유지했다.
- 원본 App과 다른 local1의 동적 그래프 높이, 계열별 데이터 예시 5개, 수정 실패 예외 전달은 유지했다. 원본의 이전 동작으로 되돌리지 않았다.
- 원본 UI 세 파일의 SHA-256을 전후 비교해 변경되지 않았음을 확인했다.

## 확인

- TypeScript / Vite production build 성공. 기존 큰 번들 경고는 남아 있다.
- 스티커·독립 출력 요청 프론트 테스트 6개 통과.
- 공개 v4.1 validator: VALIDATION OK.
- 실제 브라우저에서 상단 메뉴와 메인 배치를 확인했다. 카탈로그는 실제 `/api/catalog`로 349개 표를 표시했다.
- 합성 QA 조회 자료를 실제 편집 API에 연결해 수정이 열기와 보고서 설정 적용을 확인했다. 분기 라벨과 계열별 5개 예시도 유지됐다. 이 검증에서 외부 Jev/NCP/KOSIS 연결 성공을 주장하지 않는다.
- 390×844 viewport에서 모바일 메뉴 열기·홈 복귀, 메인 레이아웃과 가로 넘침 없음(본문 폭 375px, 스크롤 폭 375px)을 확인했다. 임시 viewport와 테스트 서버는 검증 후 정리한다.
- 전체 Python 회귀: `tests`, `eval/table-discovery/v4.1/tests`에서 728 passed, 355 subtests passed (273.74초).

키나 데이터 파일은 이식하지 않았고, GitHub 게시·PR은 수행하지 않았다.
