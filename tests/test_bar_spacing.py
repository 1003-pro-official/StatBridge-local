"""Bar spacing remains equivalent in Plotly and vector exports."""
import copy
import pytest
from matplotlib.axes import Axes
from output_agent import OutputAgent
from output_schema import ChartEditCommand, ChartSpec
from report_export import render_file
from test_research_chart_edit import source

@pytest.mark.parametrize('mode,layout,expected',[('group','combined',.35*.75/2),('relative','combined',.35*.75),('group','separate',.35*.75)])
def test_bar_spacing_roundtrip_and_export(monkeypatch,mode,layout,expected):
    agent=OutputAgent();data=source(2);before=copy.deepcopy(data)
    initial=agent.prepare(data,{'chart_type':'bar'})
    edited=agent.apply_edits(data,initial,[ChartEditCommand(operation='set_layout',kind='STYLE_EDIT',value=layout),ChartEditCommand(operation='set_presentation',kind='STYLE_EDIT',params={'bar_gap':.65,'bar_group_gap':.25,'bar_mode':mode})],generate_explanation=False)
    assert edited['plotlyFigure']['layout']['bargap']==.65
    assert edited['plotlyFigure']['layout']['bargroupgap']==.25
    spec=ChartSpec.model_validate(edited['chartState'])
    assert spec.presentation.bar_group_gap==.25
    widths=[];original=Axes.bar
    def capture(self,*args,**kwargs):
        widths.append(kwargs.get('width'));return original(self,*args,**kwargs)
    monkeypatch.setattr(Axes,'bar',capture)
    svg=render_file(agent._series(data['execution']['rows']),spec,data,'svg')
    assert svg and len(widths)==2
    assert all(w==pytest.approx(expected) for w in widths)
    assert data==before
    restored=agent.apply_edits(data,edited,[ChartEditCommand(operation='set_presentation',kind='STYLE_EDIT',params={'bar_gap':.2,'bar_group_gap':0})],generate_explanation=False)
    assert restored['plotlyFigure']['layout']['bargap']==.2
    assert restored['plotlyFigure']['layout']['bargroupgap']==0

def test_invalid_gap_rejected():
    with pytest.raises(ValueError):ChartSpec.model_validate({'presentation':{'bar_group_gap':.95}})
