import pytest
from chart_reference_policy import generic_reference_style,validate_reference_style
from edit_request_coverage import normalize_parameter_names
from output_schema import ChartEditCommand

def test_observed_mixed_geometry_binds_real_series_and_right_axis():
 from chart_reference_policy import bind_reference_structure
 proposal={'reference_style':{'chart_type':'bar','panel_count':1,'columns':1,'series_types':['line','line','bar'],'secondary_axis_indices':[2]},'commands':[{'operation':'set_presentation','params':{'design_template':'snapshot'}}]}
 result=bind_reference_structure(proposal,{'instruction':'이렇게 그려줘','seriesLabels':['지표 A','지표 B','지표 C'],'chartState':{'chart_type':'line'}})
 commands=result['commands']
 assert any(c['operation']=='set_series_chart_type' and c['label']=='지표 C' and c['value']=='bar' for c in commands)
 assert any(c['operation']=='set_secondary_axis' and c['value']=='지표 C' for c in commands)
 assert not any(c.get('operation')=='set_transform' for c in commands)
 result=bind_reference_structure(proposal,{'instruction':'이렇게 그려줘','seriesLabels':['지표 A','지표 B','지표 C'],'chartState':{'chart_type':'line','report':{'kind':'forecast'}}})
 assert any(c['operation']=='set_report' and c['params']['patch']['right_axis']==['지표 C'] for c in result['commands'])

def test_reference_patches_compact_and_base_type_precedes_mixed_series():
 from chart_reference_policy import bind_reference_structure
 proposal={'reference_style':{'chart_type':'line','panel_count':1,'columns':1},'commands':[
  {'operation':'set_presentation','params':{'design_template':'snapshot'}},
  {'operation':'set_presentation','params':{'latest_values':True}},
  {'operation':'set_series_chart_type','label':'세 번째','value':'bar','params':{}}]}
 result=bind_reference_structure(proposal,{'instruction':'이렇게 그려줘','seriesLabels':['첫 번째','두 번째','세 번째'],'chartState':{'chart_type':'bar'}})
 assert result['commands'][0]['operation']=='set_chart_type'
 assert len([c for c in result['commands'] if c['operation']=='set_presentation'])==1
 assert result['commands'][1]['params']['latest_values'] is True
 assert result['commands'][2]['value']=='bar'

def test_null_optional_params_normalize_without_accepting_wrong_types():
 assert normalize_parameter_names({'operation':'set_chart_type','value':'bar','params':None})['params']=={}
 assert normalize_parameter_names({'operation':'set_chart_type','params':'wrong'})['params']=='wrong'
@pytest.mark.parametrize('op,value,params',[('set_transform','growth_rate',{}),('set_title','국제유가',{}),('rename_series','두바이유',{}),('add_guide',None,{'value':100}),('set_axis_style',None,{'minimum':0,'maximum':180})])
def test_reference_style_cannot_replace_statistical_identity(op,value,params):
 c=ChartEditCommand(operation=op,kind='DATA_EDIT' if op=='set_transform' else 'STYLE_EDIT',label='현재 지표',value=value,params=params)
 with pytest.raises(ValueError):validate_reference_style([c],'이렇게 그려줘',{'chartState':{'title':'실제 대출금리'}})
def test_explicit_title_request_and_safe_style_are_preserved():
 c=ChartEditCommand(operation='set_title',kind='STYLE_EDIT',value='내 제목')
 validate_reference_style([c],'제목을 내 제목으로 바꿔줘',{'chartState':{'title':'기존'}})
 c=ChartEditCommand(operation='set_series_style',kind='STYLE_EDIT',params={'markers':False,'width':2})
 validate_reference_style([c],'이렇게 그려줘',{'chartState':{}})
 assert generic_reference_style('첨부한 그래프처럼 그려줘')
def test_empty_unused_value_and_nested_settings_are_unambiguous():
 item=normalize_parameter_names({'operation':'set_presentation','value':'','params':{'font_size':18}})
 assert item['value'] is None and item['params']['font_size']==18
 item=normalize_parameter_names({'operation':'set_axis_style','value':{'show_grid':False},'params':None})
 assert item['value'] is None and item['params']=={'show_grid':False}
 assert normalize_parameter_names({'operation':'set_title','value':''})['value']==''
 from edit_request_coverage import CoverageContractError
 with pytest.raises(CoverageContractError):normalize_parameter_names({'operation':'set_presentation','value':{'font_size':18},'params':{'font_size':20}})
def test_annual_rate_spellings_share_axis_but_not_other_units():
 from chart_availability import combined_layout_reason
 from research_plotly_styles import cartesian_traces
 from output_schema import ChartSpec
 series=[{'label':'대출','unit':'연%','frequency':'M','color':'#123456','points':[{'date':'202401','value':3},{'date':'202402','value':4}]},{'label':'수신','unit':'연리%','frequency':'M','color':'#456789','points':[{'date':'202401','value':2},{'date':'202402','value':3}]}]
 assert not combined_layout_reason(series)
 assert combined_layout_reason([{**series[0],'unit':'%'},series[1]])
 assert combined_layout_reason([{**series[0],'unit':'%p'},series[1]])
 spec=ChartSpec(series_styles={'대출':{'markers':False}})
 trace=cartesian_traces(series[0],spec,'line')[0]
 assert trace.mode=='lines'
 assert [s['unit'] for s in series]==['연%','연리%']
def test_reference_structure_uses_observed_panel_count_not_case_id():
 from chart_reference_policy import bind_reference_structure
 context={'instruction':'이렇게 그려줘','seriesLabels':['a','b','c'],'chartState':{'chart_type':'line'},'candidateProposal':{}}
 proposal={'reference_style':{'chart_type':'line','panel_count':3,'columns':3},'commands':[{'operation':'set_presentation','params':{'design_template':'report'}}]}
 result=bind_reference_structure(proposal,context)
 assert result['commands'][-1]=={'operation':'set_layout','value':'horizontal','params':{}}
 assert result['coverage'][0]['command_indices']==[0,1]
 from edit_request_coverage import validate_coverage,request_sources
 assert validate_coverage(result,request_sources(context['instruction'],{}))
 with pytest.raises(ValueError,match='그룹'):bind_reference_structure(proposal,{**context,'seriesLabels':['a','b']})
 with pytest.raises(ValueError,match='판독'):bind_reference_structure({'commands':[]},context)
 assert bind_reference_structure({'clarification':'그룹을 확인해 주세요'},context)['clarification']
def test_reference_layout_can_return_from_panels_to_one_chart():
 from output_agent import OutputAgent
 from output_schema import ChartSpec
 from advanced_chart_spec import ReportOptions
 spec=ChartSpec(layout='horizontal',report=ReportOptions(kind='panels',columns=3))
 changed=OutputAgent._apply_edit_spec(spec,ChartEditCommand(operation='set_layout',kind='STYLE_EDIT',value='combined'),['a','b','c'])
 assert changed.layout=='combined' and changed.report.kind=='forecast'
