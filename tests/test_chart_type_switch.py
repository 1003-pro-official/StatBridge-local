"""All 13 chart transitions, using synthetic rows and no provider calls."""
import copy
import pytest
from test_research_chart_edit import source
from chart_availability import CHART_TYPES, data_requirements
from chart_edit_agent import ChartEditAgent, explicit_chart_change
from output_agent import OutputAgent
from output_schema import ChartEditCommand


NAMES = dict(zip(CHART_TYPES, ['선 그래프','막대 그래프','누적 막대 그래프','영역 그래프','산점도','버블 그래프','원 그래프','도넛 그래프','히스토그램','상자 그림','히트맵','트리맵','워터폴 그래프']))


class NoModel:
    model_name='not-called'
    supports_images=False
    def interpret(self, *args):
        raise AssertionError('Explicit graph switching must not call a provider')


@pytest.mark.parametrize('before_kind', CHART_TYPES)
@pytest.mark.parametrize('after_kind', CHART_TYPES)
def test_every_chart_transition_or_precise_blocker(before_kind, after_kind):
    data=source(1 if before_kind=='waterfall' else 3 if before_kind=='bubble' else 2)
    agent=OutputAgent()
    current=agent.prepare(data, {'chart_type':before_kind})
    saved=copy.deepcopy(current); original=copy.deepcopy(data)
    editor=ChartEditAgent(NoModel(),agent)
    blockers=data_requirements(agent._series(data['execution']['rows']),after_kind)
    if blockers:
        with pytest.raises(ValueError,match='변경할 수 없습니다') as error:
            editor.edit(data,current,f'{NAMES[after_kind]}로 변경해줘',{'selected_target':'계열0'})
        assert all(reason in str(error.value) for reason in blockers)
    elif before_kind==after_kind:
        with pytest.raises(ValueError,match='변경된 내용이 없습니다'):
            editor.edit(data,current,f'{NAMES[after_kind]}로 변경해줘')
    else:
        edited=editor.edit(data,current,f'{NAMES[after_kind]}로 변경해줘',{'selected_target':'계열0'})
        assert edited['chartState']['chart_type']==after_kind
        assert edited['table']==current['table']
        if after_kind=='bar':
            assert all(trace['type']=='bar' for trace in edited['plotlyFigure']['data'])
            assert all(len(trace['x'])==5 for trace in edited['plotlyFigure']['data'])
    assert data==original and current==saved


@pytest.mark.parametrize('target',['chart','title','legend','x_axis','y_axis','계열0'])
def test_stale_selected_element_cannot_block_global_switch(target):
    agent=OutputAgent();data=source(2);current=agent.prepare(data,{'chart_type':'donut'})
    edited=ChartEditAgent(NoModel(),agent).edit(data,current,'막대 그래프로 변경',{'selected_target':target})
    assert edited['chartState']['chart_type']=='bar'


def test_global_switch_clears_mixed_chart_overrides():
    agent=OutputAgent();data=source(2)
    current=agent.prepare(data,{'chart_type':'line','series_chart_types':{'계열0':'area'}})
    edited=agent.apply_edits(data,current,[ChartEditCommand(operation='set_chart_type',value='bar',kind='STYLE_EDIT')])
    assert edited['chartState']['series_chart_types']=={}
    assert all(t['type']=='bar' for t in edited['plotlyFigure']['data'])


@pytest.mark.parametrize('instruction',['계열0만 막대 그래프로 변경','막대 그래프로 변경하고 제목도 바꿔줘','여기만 막대 그래프로 변경','막대 그래프로 변경하지 마'])
def test_partial_compound_and_negative_commands_do_not_bypass_model(instruction):
    assert explicit_chart_change(instruction) is None


@pytest.mark.parametrize('kind',[k for k in CHART_TYPES if k!='line'])
def test_switch_from_partially_styled_line_does_not_keep_incompatible_style(kind):
    data=source(1 if kind=='waterfall' else 3 if kind=='bubble' else 2)
    agent=OutputAgent();current=agent.prepare(data,{'chart_type':'line'})
    current=agent.apply_edits(data,current,[ChartEditCommand(operation='set_segment_style',kind='STYLE_EDIT',label='계열0',start='202401',end='202402',params={'color':'#ff0000','dash':'dash'})])
    edited=ChartEditAgent(NoModel(),agent).edit(data,current,f'{NAMES[kind]}로 변경해줘')
    assert edited['chartState']['chart_type']==kind and not edited['chartState']['range_styles']
    assert edited['table']==current['table']
    assert any('원자료' in change for change in edited['editChanges'])


def test_http_donut_to_bar_blocked_bubble_and_undo(monkeypatch):
    from fastapi.testclient import TestClient
    import bridge_api as api
    data=source(2);agent=OutputAgent();current=agent.prepare(data,{'chart_type':'donut'})
    record={'result':data,'output':current,'sessions':[{'query':'모의 비교','table_name':'모의 표','frequency':'M','period':{'start':'202401','end':'202405'}}]}
    monkeypatch.setitem(api.EDIT_SESSIONS,'chart-switch-test',record)
    monkeypatch.setattr(api,'edit_agent',ChartEditAgent(NoModel(),agent))
    monkeypatch.setattr(api.agent,'output_agent',agent)
    monkeypatch.setattr(api,'_table_card',lambda table_id:{'id':table_id,'name':'모의 표'})
    client=TestClient(api.app)
    response=client.post('/api/output/edit',json={'edit_session_id':'chart-switch-test','instruction':'막대 그래프로 변경','visual':{'selected_target':'계열0'}})
    assert response.status_code==200,response.text
    assert response.json()['chartType']=='bar'
    assert response.json()['outputSpec']['table']==current['table']
    saved=copy.deepcopy(record)
    response=client.post('/api/output/edit',json={'edit_session_id':'chart-switch-test','instruction':'버블 그래프로 변경'})
    assert response.status_code==422 and '현재 2개' in response.json()['detail']
    assert record==saved
    response=client.post('/api/output/edit',json={'edit_session_id':'chart-switch-test','action':'undo'})
    assert response.status_code==200,response.text
    assert response.json()['chartType']=='donut'
    assert response.json()['outputSpec']['table']==current['table']
