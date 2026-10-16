"""Finite supported-operation matrix using synthetic observations, never frozen gold."""
import copy,itertools
import pytest
from chart_availability import CHART_TYPES,inspect_charts,combined_layout_reason,data_requirements
from output_agent import OutputAgent
from output_schema import ChartSpec
from report_table import build_table,TableOptions,render_table_file
from plotly_renderer import render_plotly
from research_chart_editing import validate_research_spec
from recovery import recovery_question


def series(profile='two',frequency='M'):
 n=1 if profile=='one' else 3 if profile=='three' else 2
 periods={'M':['202401','202402','202403'],'Q':['202401','202402','202403'],'A':['2022','2023','2024']}
 result=[]
 for i in range(n):
  freq='Q' if profile=='mixed_frequency' and i else frequency
  dates=periods[freq]
  if profile=='disjoint' and i:dates=['202101','202102','202103']
  result.append({'label':f'계열{i}','color':['#005e93','#e28b49','#0a9d85'][i],'unit':'억원' if profile=='mixed_units' and i else '%','frequency':freq,'sourceId':f'fixture{i}', 'points':[{'date':d,'value':(-j-1 if profile=='negative' and i else j+i+1)} for j,d in enumerate(dates)]})
 return result


@pytest.mark.parametrize('profile',['one','two','three','negative','mixed_units','mixed_frequency','disjoint'])
@pytest.mark.parametrize('kind',CHART_TYPES)
@pytest.mark.parametrize('layout',['combined','separate'])
def test_chart_capability_and_requested_layout_have_a_render_or_explicit_reason(profile,kind,layout):
 data=series(profile);before=copy.deepcopy(data);allowed,unavailable=inspect_charts(data)
 spec=ChartSpec(chart_type=kind,layout=layout)
 if kind not in allowed:
  assert unavailable[kind]
 else:
  try:
   blockers=data_requirements(data,kind)
   if blockers:raise ValueError(' / '.join(blockers))
   validate_research_spec(data,spec);figure=render_plotly(data,spec)
   assert figure['data']
  except ValueError as error:
   # A combined mixed-unit/frequency layout may require separate panels.
   assert (layout=='combined' and combined_layout_reason(data)) or (layout=='separate' and kind in {'pie','donut','treemap','waterfall','scatter','bubble','heatmap'} and '지원하지 않습니다' in str(error) and '사용해 주세요' in str(error)),str(error)
 assert data==before


@pytest.mark.parametrize('template',['default',*[f'BOK-T0{i}' for i in range(1,7)]])
@pytest.mark.parametrize('orientation',['indicators','periods'])
@pytest.mark.parametrize('frequency',['M','Q','A'])
@pytest.mark.parametrize('comparison',['none','previous_change'])
@pytest.mark.parametrize('decimals',[0,3])
def test_table_settings_and_csv_excel_combinations(template,orientation,frequency,comparison,decimals):
 original=series(frequency=frequency);before=copy.deepcopy(original)
 doc=build_table(original,TableOptions(template=template,orientation=orientation,comparison=comparison if orientation=='indicators' else 'none',decimals=decimals))
 assert doc['sections'] and original==before
 assert render_table_file(doc,'csv').decode('utf-8-sig')
 assert render_table_file(doc,'xlsx').startswith(b'PK')


@pytest.mark.parametrize('template',['default',*[f'BOK-T0{i}' for i in range(1,7)]])
@pytest.mark.parametrize('orientation',['indicators','periods'])
@pytest.mark.parametrize('format',['png','pdf'])
def test_table_visual_export_combinations(template,orientation,format):
 doc=build_table(series(),TableOptions(template=template,orientation=orientation))
 assert render_table_file(doc,format).startswith(b'%PDF' if format=='pdf' else b'\x89PNG')


def test_provider_rate_limit_is_recoverable_not_a_request_to_change_statistics():
 recovery=recovery_question('KOSIS 호출 제한으로 대기 중입니다. 약 31초 후 다시 시도해 주세요.')
 assert recovery['issue']=='rate_limit' and recovery['preserveState']
 assert any(c['id']=='retry' for c in recovery['choices'])
