import copy
import pytest
from output_agent import OutputAgent
from output_schema import ChartSpec,PositionedNote
from test_research_chart_edit import source,edit


def test_individual_marker_and_auto_label_follow_actual_value_on_rebuild():
    agent=OutputAgent();data=source();before=copy.deepcopy(data);initial=agent.prepare(data,{'chart_type':'line'})
    result=edit(agent,data,initial,'set_point_style',label='계열0',start='202403',params={'markers':True,'marker_size':8,'marker_symbol':'circle-open','color':'#246294'})
    result=edit(agent,data,result,'add_note',params={'label':'계열0','period':'202403','text':'시점·관측값','observation_label':True,'y_shift':22})
    markers=[t for t in result['plotlyFigure']['data'] if t.get('mode')=='markers']
    assert markers[0]['marker']['size']==[0,0,8,0,0]
    note=next(a for a in result['plotlyFigure']['layout']['annotations'] if a.get('name')==result['chartState']['notes'][-1]['id'])
    assert note['x']==2 and note['y']==15 and note['yshift']==22 and note['text'].endswith('<br>15')
    assert data==before and result['table']==initial['table']
    for row in data['execution']['rows']:
        if row['PRD_DE']=='202403':row['DT']='16'
    updated=agent._build(data,ChartSpec.model_validate(result['chartState']),generate_explanation=False)
    assert next(a for a in updated['plotlyFigure']['layout']['annotations'] if a.get('name')==result['chartState']['notes'][-1]['id'])['text'].endswith('<br>16')


def test_free_text_escaped_and_position_change_and_remove():
    agent=OutputAgent();data=source();initial=agent.prepare(data,{'chart_type':'line'})
    result=edit(agent,data,initial,'add_note',params={'text':'<script>bad</script>\n사용자 문구','x':.3,'y':.8})
    n=result['chartState']['notes'][-1]
    annotation=next(a for a in result['plotlyFigure']['layout']['annotations'] if a.get('name')==result['chartState']['notes'][-1]['id'])
    assert annotation['xref']=='paper' and annotation['x']==.3 and annotation['y']==.8
    assert '<script>' not in annotation['text'] and '<br>' in annotation['text']
    moved=edit(agent,data,result,'update_note',value=n['id'],params={'x':.6,'y':.5})
    assert next(a for a in moved['plotlyFigure']['layout']['annotations'] if a.get('name')==n['id'])['x']==.6
    removed=edit(agent,data,moved,'remove_note',value=n['id'])
    assert not removed['chartState']['notes']


def test_unknown_points_invalid_auto_anchor_and_shift_are_blocked():
    agent=OutputAgent();data=source();initial=agent.prepare(data,{'chart_type':'line'})
    with pytest.raises(ValueError):edit(agent,data,initial,'set_point_style',label='계열0',start='209901',params={'markers':True})
    with pytest.raises(ValueError):edit(agent,data,initial,'add_note',params={'text':'거짓 값','observation_label':True})
    with pytest.raises(ValueError):PositionedNote(text='이동',x_shift=401)
