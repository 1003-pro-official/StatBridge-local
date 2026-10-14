# 스냅샷 표현 품질 진단 v1

한국은행 스냅샷의 실제 선·막대·복합축 그림을 참고해 현재 KOSIS 데이터의 형식 재현을 검사하는 독립 진단입니다. 사이트 수치·같은 픽셀·표 탐색 골드셋의 점수가 아닙니다.

`cases.json`의 공개 URL에서 그림을 확인하고 이미지로 저장합니다. 실제 이미지 형식과 확장자를 일치시키세요. 원본 스냅샷 자료 대신 현재 카탈로그의 기업대출·대기업대출·중소기업대출 금리 72개 관측값을 사용합니다. 참고 그림의 없는 금리차나 증감액을 생성하지 않습니다.

1. 각 이미지를 `snapshot-line.jpg`, `snapshot-bar.jpg`, `snapshot-combo.jpg`로 준비하고 같은 폴더에 `cases.json`을 `samples.json`으로 복사합니다. PNG라면 manifest의 파일명도 `.png`로 바꿉니다. 실제 이미지가 JPEG인데 PNG MIME을 사용하면 검증이 거부됩니다.
2. 실제 호출이 가능한 프로젝트 환경에서 실행합니다. 키는 각 프로젝트 서버 설정에만 두고 출력·복사하지 않습니다.

```powershell
.venv/Scripts/python.exe scripts/evaluate_chart_references.py --samples .venv/cache/snapshot/samples.json --output-dir .venv/cache/snapshot/run1 --live --exports
```

`--live`는 실제 유료 모델 요청을 실행합니다. `--exports`는 기본 출력과 성공한 수정 후 PNG·SVG·PDF의 실제 HTTP 파일을 검증·저장합니다. `--case snapshot-combo`로 단일 사례를 실행할 수 있습니다. 각 실행은 새 출력 폴더를 사용하세요.

종류·실제 그리기 영역·보조축과 원자료 계약을 자동 판정합니다. 두 겹치는 축은 두 패널이 아닙니다. `visual_review=pending`은 외관 성공 점수가 아니며 이미지·PDF를 직접 비교해야 합니다. 관측값/원행 hash·호출별 시간/모델 usage·검증된 설정만 기록하고 모델 내부 추론은 수집하지 않습니다. 진단 결과·이미지·계정 DB를 Git에 포함하지 않습니다.

최초 실패, 반복 실패, 최종 재검증과 한계는 [작업 기록](../../../docs/implementation/2026-10-14-snapshot-report-quality.md)에 구분해 적었습니다.
