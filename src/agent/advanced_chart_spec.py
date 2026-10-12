"""Versioned report metadata layered on the existing, observation-owned ChartSpec."""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

ReportKind = Literal['forecast', 'dual_axis', 'contribution', 'panels', 'events', 'fan',
    'waterfall', 'regression', 'heatmap', 'violin', 'dotplot', 'yield_curve',
    'stacked_area', 'scenario', 'bubble', 'network']


class StrictReport(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Interval(StrictReport):
    label: str = Field(min_length=1, max_length=300)
    level: float = Field(gt=0, lt=1)
    periods: list[str] = Field(min_length=1, max_length=10000)
    lower: list[float] = Field(min_length=1, max_length=10000)
    upper: list[float] = Field(min_length=1, max_length=10000)
    method: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=300)

    @model_validator(mode='after')
    def bounds(self):
        if len(self.periods) != len(self.lower) or len(self.lower) != len(self.upper):
            raise ValueError('신뢰구간의 시점·하한·상한 길이가 다릅니다.')
        if len(set(self.periods)) != len(self.periods) or self.periods != sorted(self.periods):
            raise ValueError('신뢰구간 시점은 중복 없이 정렬해 주세요.')
        if any(a>b for a,b in zip(self.lower,self.upper)):
            raise ValueError('신뢰구간 하한이 상한보다 큽니다.')
        return self


class Event(StrictReport):
    period: str = Field(min_length=1, max_length=30)
    text: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=300)


class ReportOptions(StrictReport):
    chart_id: str = Field(default_factory=lambda:uuid4().hex,min_length=1,max_length=80)
    template: str = 'economic_outlook'
    kind: ReportKind = 'forecast'
    forecast_start: str | None = Field(default=None, max_length=30)
    forecast_description: str = Field(default='사용자 지정 전망 구간', max_length=100)
    intervals: list[Interval] = Field(default_factory=list, max_length=12)
    events: list[Event] = Field(default_factory=list, max_length=20)
    contribution_confirmed: bool = False
    right_axis: list[str] = Field(default_factory=list, max_length=20)
    columns: int = Field(default=2, ge=1, le=4)
    source_note: str = Field(default='', max_length=500)
    footnotes: list[str] = Field(default_factory=list, max_length=8)
    regression: Literal['ols'] = 'ols'
    date_format: Literal['period','year'] = 'period'
    width: int = Field(default=1200, ge=600, le=2400)
    height: int = Field(default=720, ge=400, le=2000)
    dpi: int = Field(default=200, ge=96, le=400)
    svg_text_mode: Literal['path','text'] = 'path'

    @model_validator(mode='after')
    def known_template(self):
        if self.template not in TEMPLATES:
            raise ValueError('등록되지 않은 보고서 템플릿입니다.')
        if any(len(text)>300 for text in self.footnotes):
            raise ValueError('각주는 항목당 300자 이하여야 합니다.')
        return self


PALETTE = ['#2255a4','#e88438','#299a86','#c64949','#7854a6','#7388a6']
# Original sample PDF page indexes, not claims of official BOK authorship.
TEMPLATES = {
    'economic_outlook': {'name':'경제전망 시계열','kind':'forecast','sample':'경제전망 2026.8, PDF 26쪽 그림 1.9'},
    'forecast_band': {'name':'추정·신뢰구간','kind':'fan','sample':'경제전망 2026.8, PDF 57쪽 그림 16·17'},
    'payments_combo': {'name':'지급결제 복합축','kind':'dual_axis','sample':'지급결제 2025, PDF 23쪽 그림 I-4'},
    'growth_contribution': {'name':'성장·임금 기여도','kind':'contribution','sample':'경제전망 2026.8, PDF 26쪽 그림 1.11'},
    'financial_panels': {'name':'금융안정 비교 패널','kind':'panels','sample':'금융안정 2026.6, PDF 22쪽 그림 I-1-6'},
    'policy_events': {'name':'정책·참조선','kind':'events','sample':'통화신용정책 2026.9, PDF 22쪽 그림 I-11'},
    'change_waterfall': {'name':'변화분 워터폴','kind':'waterfall','sample':'StatBridge 확장; 업로드 샘플에서 동일 유형은 확인하지 않음'},
    'relationship': {'name':'지표 관계·회귀','kind':'regression','sample':'StatBridge 확장; 경제전망 PDF 57쪽 관계 분석의 표현 원칙 참고'},
    'risk_heatmap': {'name':'비교 지표 히트맵','kind':'heatmap','sample':'StatBridge 확장; 금융안정 PDF 22쪽 비교 원칙 참고'},
    'distribution': {'name':'분포·바이올린','kind':'violin','sample':'경제전망 PDF 26쪽 그림 1.12의 분포 비교를 확장'},
    'scenario_compare': {'name':'시나리오·기관 전망','kind':'scenario','sample':'지역경제 2026.7, PDF 125쪽 그림 6'},
    'composition_area': {'name':'누적 영역 구성','kind':'stacked_area','sample':'지급결제 PDF 23쪽 구성 비교를 확장'},
}


def fingerprint(series):
    return hashlib.sha256(json.dumps(series,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def validate_report(series, options):
    by_label={s['label']:s for s in series}
    if not series or any(not s['points'] for s in series):
        raise ValueError('보고서에 사용할 관측값이 없습니다.')
    if sum(len(s['points']) for s in series)>50000:
        raise ValueError('보고서 렌더링은 최대 50,000개 관측값을 지원합니다. 기간을 줄여 주세요.')
    for s in series:
        dates=[p['date'] for p in s['points']]
        if dates!=sorted(dates) or len(set(dates))!=len(dates):
            raise ValueError('시점은 중복 없이 정렬되어야 합니다.')
    periods=sorted({p['date'] for s in series for p in s['points']})
    if options.forecast_start and options.forecast_start not in periods:
        raise ValueError('전망 시작은 실제 제공된 시점에서 선택해 주세요.')
    if options.kind in {'dotplot','yield_curve','network'}:
        raise ValueError(f'{options.kind}: 투표자·만기·연계 관계의 전용 메타데이터 어댑터가 아직 없습니다. 일반 선그래프로 대체하지 않습니다.')
    if options.kind=='contribution' and not options.contribution_confirmed:
        raise ValueError('기여도 자료인지 확인해 주세요. 일반 수치를 성장 기여도로 변환하지 않습니다.')
    if options.kind in {'contribution','stacked_area','heatmap','scenario'} and len({s['unit'] for s in series})!=1:
        raise ValueError('합산·공통 색상·시나리오 비교에는 같은 단위가 필요합니다.')
    if options.kind in {'contribution','stacked_area'} and any([p['date'] for p in s['points']]!=periods for s in series):
        raise ValueError('누적 그래프의 모든 계열에 같은 시점의 값이 필요합니다. 결측값을 0으로 만들지 않습니다.')
    if options.kind=='stacked_area' and any(p['value']<0 for s in series for p in s['points']):
        raise ValueError('누적 영역의 음수는 지원하지 않습니다. 음수 기여도는 누적 기여도 막대를 사용하세요.')
    if options.kind in {'regression','bubble'} and len(series)!=(3 if options.kind=='bubble' else 2):
        raise ValueError('회귀는 두 계열, 버블은 세 계열을 지정해 주세요.')
    if options.kind=='dual_axis' and (not options.right_axis or not set(options.right_axis)<set(by_label)):
        raise ValueError('왼쪽·오른쪽 축의 계열을 각각 명시해 주세요.')
    if options.kind=='dual_axis' and (len({s['unit'] for s in series if s['label'] in options.right_axis})>1 or len({s['unit'] for s in series if s['label'] not in options.right_axis})>1):
        raise ValueError('각 축에 연결한 계열은 같은 단위를 사용해야 합니다.')
    if options.kind=='fan' and not options.intervals:
        raise ValueError('팬 차트에는 실제 하한·상한·신뢰수준·계산법·출처가 필요합니다. 구간을 임의 추정하지 않습니다.')
    if options.intervals and options.kind not in {'fan','forecast','scenario'}:
        raise ValueError('신뢰구간은 단일 공통 시계열 축의 팬·전망·시나리오 그래프에서 지원합니다.')
    if options.forecast_start and options.kind in {'regression','bubble','violin','waterfall'}:
        raise ValueError('이 그래프의 축은 전망 시간 구간 표시를 지원하지 않습니다.')
    if options.events and options.kind in {'regression','bubble','violin'}:
        raise ValueError('정책 이벤트 시간 표시는 시계열 그래프에서 사용해 주세요.')
    for event in options.events:
        if event.period not in periods: raise ValueError('이벤트 시점이 제공된 관측 시점에 없습니다.')
    levels={}
    for band in options.intervals:
        if band.label not in by_label: raise ValueError('신뢰구간의 대상 계열이 없습니다.')
        values={p['date']:p['value'] for p in by_label[band.label]['points']}
        if any(d not in values or not lo<=values[d]<=hi for d,lo,hi in zip(band.periods,band.lower,band.upper)):
            raise ValueError('신뢰구간 시점 또는 중심값과 경계가 일치하지 않습니다.')
        key=(band.label,band.level)
        if key in levels: raise ValueError('같은 계열·신뢰수준 구간이 중복됐습니다.')
        levels[key]=band
    for band in options.intervals:
        for outer in options.intervals:
            if outer.label==band.label and outer.level>band.level:
                if outer.periods!=band.periods or any(a>b or c<d for a,b,c,d in zip(outer.lower,band.lower,outer.upper,band.upper)):
                    raise ValueError('높은 신뢰수준 구간은 낮은 수준 구간을 포함해야 합니다.')
    if options.kind not in {'panels','violin'} and len({s.get('frequency') for s in series if s.get('frequency')})>1:
        raise ValueError('공통 축에는 같은 관측 주기가 필요합니다.')
    if options.kind not in {'panels','regression','bubble','violin','dual_axis'} and len({s['unit'] for s in series})>1:
        raise ValueError('단위가 다른 계열은 명시적 복합축 또는 별도 패널을 선택하세요.')
    return periods


def recommend_report(series, plans):
    """Explain deterministic recommendations; unit differences do not imply dual axes."""
    units={s['unit'] for s in series};frequencies={s.get('frequency') for s in series}
    if len(units)>1 or len(frequencies)>1:
        return {'options':ReportOptions(template='financial_panels',kind='panels').model_dump(),
            'reasons':['단위 또는 주기가 달라 별도 패널을 권장합니다. 이중 축은 자동으로 설정하지 않습니다.']}
    if any('기여도' in p.get('table_name','') for p in plans) and len(series)>1:
        return {'options':ReportOptions(template='growth_contribution',kind='contribution',contribution_confirmed=True).model_dump(),
            'reasons':['정본 통계표 이름이 기여도이고 모든 계열의 단위·주기가 같습니다. 원값을 합산 표시하며 새 기여도를 계산하지 않습니다.']}
    if len(series)>4:
        return {'options':ReportOptions(template='financial_panels',kind='panels').model_dump(),'reasons':['5개 이상 계열의 중첩을 줄이기 위해 별도 패널을 권장합니다.']}
    return {'options':ReportOptions().model_dump(),'reasons':['제공된 시계열 관측값을 보고서형 선그래프로 표시합니다. 전망값·이벤트·신뢰구간을 생성하지 않습니다.']}
