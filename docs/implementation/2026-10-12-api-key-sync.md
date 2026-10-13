# OpenAI·Jev 키 입력 및 두 폴더 동기화

최신 local1의 역질문 복구, GPT-5.4 출력·수정, 참고 이미지/PDF 업로드와 의존성 검사 변경을 StatBridge1/StatBridge-official에 반영한다. 각 폴더의 비밀 설정·회원 DB·저장 그래프는 그대로 유지하고 복사하지 않는다.

## 키 입력 위치

- local1: 프로젝트 루트 `.env`
- StatBridge1: `StatBridge-official/.env` (현재 정본 실행 경로)

두 프로젝트의 `scripts/windows/EDIT_API_KEYS.cmd`를 실행하면 해당 프로젝트의 .env가 메모장으로 열린다. 실제 키를 입력하고 저장한 뒤 해당 루트 START_STATBRIDGE.cmd로 재시작한다.

```dotenv
OPENAI_API_KEY=발급받은_OpenAI_API_키
OPENAI_CHART_MODEL=gpt-5.4
STATBRIDGE_OUTPUT_PROVIDER=openai
JEV_API_KEY=발급받은_Jev_API_키
TYPESAFE_ENDPOINT=https://api.typesafe.ai
STATBRIDGE_JEV_ENABLED=1
```

Jev는 JEV_API_KEY를 먼저 사용하고, 비어 있으면 기존 TYPESAFE_API_KEY를 사용한다. 기존 키를 지우거나 다른 폴더에서 복사하지 않는다. Jev는 복수 지표 수 판별 보조 역할이며 키가 없거나 실패하면 기존 분류 경로로 돌아간다. OpenAI는 출력·수정에 사용하고 NCP 분류·임베딩 키는 유지한다. 실제 모델 사용 권한과 응답 품질은 키 입력 후 별도 확인해야 한다.

동시 실행 프로필은 local1 UI 5173/API 8000, StatBridge1 UI 5174/API 8001이며 로그인 쿠키 이름도 분리한다. 포트별 루트 래퍼는 의도적으로 다르고 공통 소스·설치 스크립트는 같은 내용으로 맞춘다. ai-assisted 작업이다.

## 이번 실행 검증

공통 공개 파일 775개가 같은 내용임을 확인했다. local1 Jev·경로 검사 17개, StatBridge1의 Jev·이미지·복구·경로 검사 9개 통과. StatBridge1 Python 의존성 충돌 검사와 기존 인덱스 검사, npm 설치·전체 빌드도 통과했다. 연결 경로가 유효하지 않던 StatBridge1 Python 환경을 자체 환경으로 준비했다. 두 루트 CMD 모두 기본 API/UI 준비 완료로 종료했다. 기존 큰 번들 경고는 유지된다. 실제 OpenAI/Jev 외부 모델 응답은 키 설정 후 별도 검증한다.
