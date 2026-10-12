# 공통 명세와 JSON 저장

## 두 계층

- 기존 `ChartSpec`에 선택적 `report: ReportOptions | null`만 추가했다. 제목·축·스타일·메모·원자료 변환·이모티콘의 기존 필드는 유지한다.
- 저장용 `ChartDocument` 버전은 `statbridge.report/1`이다. API 출력에서는 `outputSpec.reportDocument`로 제공하며 JSON 파일로 저장할 수 있다.

주요 문서 필드는 `schema_version`, `chart_id`, `dataset_reference`, `dataset_version`, `data_transformations`, `series`, `axes`, `units`, `title`, `subtitle`, `legend`, `annotations`, `reference_lines`, `highlighted_regions`, `forecast_regions`, `confidence_intervals`, `panels`, `typography`, `theme`, `source`, `footnotes`, `export_settings`, `state`이다. `state`는 재렌더링할 정본 ChartSpec, 나머지는 같은 상태에서 계산한 관측·출처·변환 메타데이터다.

`dataset_version`은 원자료에서 만든 정본 계열의 SHA-256이다. 숨김·표시 기간·정렬·성장률 등은 원자료를 덮지 않는다. 문서에는 원자료 버전과 변환 후 표시 값이 함께 기록된다. 보고서 `chart_id`는 편집과 저장 동안 유지된다. 레거시 명세의 문서 ID는 원자료 버전에서 파생한다.

## 적용 예제

```json
{
  "edit_session_id": "현재 편집 세션",
  "revision": 0,
  "report": {
    "template": "economic_outlook",
    "kind": "forecast",
    "forecast_start": "202501",
    "forecast_description": "사용자 지정 전망 구간",
    "source_note": "추가 표기이며 실제 조회 출처를 대체하지 않음",
    "footnotes": ["주: 미래 수치는 자동으로 추정하지 않습니다."],
    "width": 1200,
    "height": 720,
    "dpi": 200,
    "svg_text_mode": "path"
  }
}
```

위 시점이 실제 제공된 데이터에 있어야 한다. Q의 `202501`은 2025년 1분기다. 사용자가 표시한 전망 구간은 `origin=user_marked_no_estimation`으로 기록하며 새로운 전망값을 만들지 않는다. 실제 관측 자료 전체를 예측 자료라고 자동 판단하지 않는다.

## 신뢰구간

`intervals` 항목은 `label`, `level`, `periods`, `lower`, `upper`, `method`, `source`를 모두 제공해야 한다. 길이·유한성·정렬·시점·계열·하한≤중심≤상한과 신뢰수준 간 포함 관계를 검증한다. 팬 차트는 구간이 없으면 실패한다. 임의 표준오차·분위수·미래값을 만들지 않는다. 실제 계산 모형의 타당성을 자동 검증하는 것은 아니다.

## 복원·마이그레이션

`POST /api/report/export`에 `format=json`으로 저장한다. `POST /api/output/edit`의 `document`로 복원한다. 모든 문서 필드와 버전, 데이터 버전·표 참조·출처·표시 수치·정본 상태를 현재 세션으로 재구성해 대조한다. 변조·다른 자료·미래 스키마는 거부하며 그래프는 유지된다. 오래된 ChartSpec은 `migrate_legacy()`로 v1 문서에 포장한다. JSON 복원은 원자료 업로드나 다른 데이터로 교체하는 기능이 아니다.

제한: 표시 자료 50,000점, JSON 8MB, 신뢰구간 12개, 이벤트 20개, 그래프 이미지 40개. API 설정 모델은 알 수 없는 보고서 필드를 금지한다. 템플릿 레지스트리에 새 템플릿을 추가할 수 있으며 20개 이상의 스타일로 확장해도 저장 형식의 기반은 유지된다.
