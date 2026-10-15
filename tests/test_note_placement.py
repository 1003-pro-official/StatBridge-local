"""Outside notes reserve caption lanes, preserve IDs and export text."""
import copy
import pytest
from output_agent import OutputAgent
from output_schema import ChartEditCommand, ChartSpec, PositionedNote
from report_export import render_file
from test_research_chart_edit import source

@pytest.mark.parametrize('count',[1,4,10])
def test_outside_note_lanes_and_export(count):
    agent=OutputAgent();data=source(count);before=copy.deepcopy(data)
    initial=agent.prepare(data,{'chart_type':'line'})
    edited=agent.apply_edits(data,initial,[ChartEditCommand(operation='add_note',kind='STYLE_EDIT',params={'text':'별도 설명 영역 검증 '*12,'placement':'below'}),ChartEditCommand(operation='add_note',kind='STYLE_EDIT',params={'text':'두 번째 설명','placement':'below'})],generate_explanation=False)
    spec=ChartSpec.model_validate(edited['chartState'])
    layout=edited['plotlyFigure']['layout']
    notes=[next(a for a in layout['annotations'] if a.get('name')==n.id) for n in spec.notes]
    assert all(a['y']==0 and a['yshift'] < -120 and a['yanchor']=='top' for a in notes)
    assert abs(notes[0]['yshift']-notes[1]['yshift'])>=34
    assert layout['margin']['b']>abs(notes[-1]['yshift'])
    assert layout['height']-layout['margin']['b']-layout['margin']['t']>=260
    assert data==before
    if count==1:
        svg=render_file(agent._series(data['execution']['rows']),spec,data,'svg').decode('utf8')
        assert '두 번째 설명' in svg
    moved=agent.apply_edits(data,edited,[ChartEditCommand(operation='update_note',kind='STYLE_EDIT',value=spec.notes[0].id,params={'placement':'inside','x':.2,'y':.8})],generate_explanation=False)
    n=next(a for a in moved['plotlyFigure']['layout']['annotations'] if a.get('name')==spec.notes[0].id)
    assert n['x']==.2 and n['y']==.8

def test_saved_legacy_note_stays_inside():
    assert PositionedNote(text='기존 설명').placement=='inside'
