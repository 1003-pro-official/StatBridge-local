import copy,json
import pytest
from output_agent import OutputAgent
from output_schema import ChartEditCommand,ChartSpec
from test_research_chart_edit import source
from chart_edit_agent import ChartEditAgent
from openai_chart_client import OpenAIChartClient,OpenAIEditModel
import base64,io
from PIL import Image

def reference():
    buf=io.BytesIO();Image.new('RGB',(20,20),'white').save(buf,format='PNG')
    return {'name':'reference.png','mime':'image/png','data_url':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()}

class Response:
    ok=True
    status_code=200
    def __init__(self,text):self.text=text
    def json(self):return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':self.text}]}]}


@pytest.mark.parametrize('axis',['y','y2'])
@pytest.mark.parametrize('placement',['side','top','bottom','custom'])
@pytest.mark.parametrize('orientation',['horizontal','vertical'])
def test_axis_title_direction_and_placement(axis,placement,orientation):
    agent=OutputAgent();data=source(2);first=agent.prepare(data,{'chart_type':'line'})
    params={'title':'축 제목','title_orientation':orientation,'title_placement':placement,'title_x':.2,'title_y':1.1}
    commands=[ChartEditCommand(operation='set_secondary_axis',kind='STYLE_EDIT',value='계열1'),ChartEditCommand(operation='set_axis_style',kind='STYLE_EDIT',label=axis,params=params)]
    out=agent.apply_edits(data,first,commands,generate_explanation=False)
    key='statbridge-axis-title:yaxis'+('2' if axis=='y2' else '')
    note=next(a for a in out['plotlyFigure']['layout']['annotations'] if a.get('name')==key)
    assert note['textangle']==(0 if orientation=='horizontal' else 90 if axis=='y2' else -90)
    if placement=='top':assert note['y']==1 and note['x']==(1 if axis=='y2' else 0)
    if placement=='bottom':assert note['y']==0
    if placement=='custom':assert note['x']==.2 and note['y']==1.1

def test_reference_uses_one_provider_call_without_duplicate_current_screenshots():
    class Transport:
        def __init__(self):self.calls=[]
        def post(self,url,**kw):
            self.calls.append(kw['json'])
            return Response(json.dumps({'commands':[],'reference_style':{'chart_type':'line','panel_count':1,'columns':1,'series_types':['line','bar'],'secondary_axis_indices':[1]}}))
    agent=OutputAgent();data=source(2);initial=agent.prepare(data,{'chart_type':'line'});before=copy.deepcopy(data)
    transport=Transport();model=OpenAIEditModel(OpenAIChartClient(api_key='fake',session=transport))
    out=ChartEditAgent(model,agent).edit(data,initial,'첨부 그림처럼 그려줘',{'reference_files':[reference()],'graph_image':reference()['data_url'],'marked_image':reference()['data_url']})
    assert len(transport.calls)==1
    assert len([c for c in transport.calls[0]['input'][0]['content'] if c['type']=='input_image'])==1
    assert out['chartState']['secondary_axis_series']==['계열1']
    assert data==before

def test_horizontal_top_axis_titles_export_as_svg():
    from report_export import render_file
    agent=OutputAgent();data=source(2);first=agent.prepare(data,{'chart_type':'line'})
    cmds=[ChartEditCommand(operation='set_secondary_axis',kind='STYLE_EDIT',value='계열1')]
    cmds += [ChartEditCommand(operation='set_axis_style',kind='STYLE_EDIT',label=axis,params={'title':title,'title_orientation':'horizontal','title_placement':'top'}) for axis,title in [('y','왼쪽 축 위 제목'),('y2','오른쪽 축 위 제목')]]
    out=agent.apply_edits(data,first,cmds,generate_explanation=False)
    svg=render_file(agent._series(data['execution']['rows']),ChartSpec.model_validate(out['chartState']),data,'svg').decode()
    assert '왼쪽 축 위 제목' in svg and '오른쪽 축 위 제목' in svg
