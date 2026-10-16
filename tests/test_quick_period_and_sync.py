import copy
import pytest
from output_agent import OutputAgent
from output_schema import ChartEditCommand,ChartSpec
from report_export import render_file
from test_research_chart_edit import source

def cmd(op,**kw):return ChartEditCommand(operation=op,kind='DATA_EDIT' if op=='filter_period' else 'STYLE_EDIT',**kw)
def history():
 d=source(2);d['execution']['rows']=[{'PRD_DE':f'{y}{m:02d}','DT':str((y-2010)*10+m+i),'ITM_NM':f'계열{i}','UNIT_NM':'조원','_SOURCE_SERIES_ID':'DT_TEST','_FREQUENCY':'M'} for i in range(2) for y in range(2010,2026) for m in range(1,13)]
 return d

def test_periods_restore_from_full_source_and_sync_export(monkeypatch):
 agent=OutputAgent();data=history();before=copy.deepcopy(data);initial=agent.prepare(data,{'chart_type':'line'})
 result=agent.apply_edits(data,initial,[cmd('set_secondary_axis',value='계열1'),cmd('set_series_chart_type',label='계열1',value='bar'),cmd('set_presentation',params={'sync_y_axes':True})],generate_explanation=False)
 for years,points in [(1,12),(5,60),(10,120),(1,12),(None,192)]:
  result=agent.apply_edits(data,result,[cmd('filter_period',params={'years':years})],generate_explanation=False)
  assert len(result['plotlyFigure']['data'][0]['x'])==points
  assert result['chartState']['period_window_years']==years
  layout=result['plotlyFigure']['layout']
  assert layout['yaxis']['range']==layout['yaxis2']['range']
  assert layout['yaxis']['dtick']==layout['yaxis2']['dtick']
 assert data==before
 import matplotlib.pyplot as plt
 closed=[];original=plt.close
 def close(fig=None):
  if hasattr(fig,'axes') and len(fig.axes)==2:
   assert fig.axes[0].get_ylim()==fig.axes[1].get_ylim()
   assert list(fig.axes[0].get_yticks())==list(fig.axes[1].get_yticks());closed.append(True)
  return original(fig)
 monkeypatch.setattr(plt,'close',close)
 assert render_file(agent._series(data['execution']['rows']),ChartSpec.model_validate(result['chartState']),data,'svg')
 assert closed

@pytest.mark.parametrize('freq,periods,expected',[('Q',[f'{y}{q:02d}' for y in range(2020,2026) for q in range(1,5)],4),('A',[str(y) for y in range(2020,2026)],1)])
def test_quarter_and_year_windows(freq,periods,expected):
 data=source(1);data['execution']['rows']=[{**data['execution']['rows'][0],'PRD_DE':p,'_FREQUENCY':freq} for p in periods]
 agent=OutputAgent();first=agent.prepare(data,{'chart_type':'line'})
 result=agent.apply_edits(data,first,[cmd('filter_period',params={'years':1})],generate_explanation=False)
 assert len(result['plotlyFigure']['data'][0]['x'])==expected

def test_different_units_reject_sync_and_keep_source():
 agent=OutputAgent();data=history()
 for row in data['execution']['rows']:
  if row['ITM_NM']=='계열1':row['UNIT_NM']='%'
 initial=agent.prepare(data,{'chart_type':'line','layout':'separate'})
 dual=agent.apply_edits(data,initial,[cmd('set_secondary_axis',value='계열1')],generate_explanation=False)
 before=copy.deepcopy(dual)
 with pytest.raises(ValueError,match='단위가 같은'):
  agent.apply_edits(data,dual,[cmd('set_presentation',params={'sync_y_axes':True})],generate_explanation=False)
 assert dual==before
