# 내부 첨부 자료 테스트

ai-assisted. UI 업로드 기능을 의미하지 않습니다.

cases.jsonl은 공개 개정 전 SBV2-0055~0072 18건을 보존한 내부 OutputAgent 테스트입니다.
fixture와 claims, attachment_registry는 이 디렉터리의 별도 정답·근거입니다.
공개 72건과 같은 ID를 사용하므로 반드시 별도 실행·채점하고 점수를 합치지 않습니다.

저장소 루트에서 실행합니다.

```powershell
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/run.py eval/statbridge-golden/v2/internal/components/cases.jsonl --output results/internal-components.jsonl
.venv/Scripts/python.exe eval/statbridge-golden/v2/scripts/score.py eval/statbridge-golden/v2/internal/components/cases.jsonl eval/statbridge-golden/v2/results/internal-components.jsonl --output eval/statbridge-golden/v2/results/internal-components-score.json
```

이 경로는 fixture를 직접 OutputAgent에 전달하며 파일 업로드나 조회 API 흐름을 검증하지
않습니다. 오프라인 편집은 명령 재생으로 자연어 분류 성능을 평가하지 않습니다.
사람 승인·해석 검수는 별도로 필요하며 과거 공개 관측을 재사용하지 않습니다.
