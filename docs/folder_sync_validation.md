# StatBridge 폴더 동기화 검증

최신 StatBridge-local1의 소스와 문서, 공개 평가 데이터, 실행 스크립트를 StatBridge1/StatBridge-official에 반영했습니다.

## 실행

- local1: 루트 START_STATBRIDGE.cmd → UI http://127.0.0.1:5173/ · API 8000
- StatBridge1: 루트 START_STATBRIDGE.cmd → UI http://127.0.0.1:5174/ · API 8001
- 각 STOP_STATBRIDGE.cmd는 해당 폴더에서 시작한 프로세스만 종료합니다.
- 기능과 공통 실행 스크립트는 동일합니다. 두 프로그램을 동시에 실행할 수 있도록 포트와 로그인 쿠키 이름을 분리했습니다.

## 보존과 환경

각 프로젝트의 API 키, 회원 정보, 저장 그래프는 별도로 유지했습니다. local1의 비밀 설정을 StatBridge1에 복사하지 않았습니다. StatBridge1은 자신의 기존 Python 환경과 벡터 인덱스를 연결하고 필요한 의존성을 설치했습니다.

덮어쓴 기존 파일 백업: StatBridge1/runtime_scripts/sync_backup/20261012-163445

## 검증 결과

- 두 루트 CMD 모두 정상 종료 코드 0, 기본 UI와 API 준비 완료
- 두 API에서 로그인 정상, 카탈로그 349개, 디자인 6종, 보고서 화살표 2종 일치
- 동일한 실제 KOSIS DT_181Y011 2021–2025년 조회: 관측값 20개와 데이터 SHA-256 일치
- SHA-256: 2ee377569031208667773f618993aaa65fa6702a9d8b8d8eb136ccf6084e7147
- StatBridge1 전체 회귀 검사: 최초 747개 및 하위 검사 355개 통과, 루트 CMD 금지 검사 1개 실패. 새 바로가기 허용 및 실제 스크립트 위임 검증으로 수정한 뒤 구조 검사 2개 모두 통과. 전체 기능 검사와 수정한 검사 합계 748개 통과. 수정 후 전체 검사를 다시 실행한 결과는 아닙니다.
- 최초 전체 검사에서 임시 SQLite 파일 정리 관련 Windows 파일 점유 경고 1건 발생
- v4.1 공개 평가 데이터 검증 VALIDATION OK
- 프런트엔드 의존성 설치와 production build 성공
- 실제 브라우저 StatBridge1 로그인 및 최신 홈 화면 확인

상세 실행 로그와 해시 목록은 local1/evaluation_runs/folder_sync에 저장했습니다. 별도 임시 검증 서버는 종료하고 두 기본 서버를 유지합니다.
