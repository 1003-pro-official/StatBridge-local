from output_agent import edit_change_description
from output_schema import ChartEditCommand
import pytest
@pytest.mark.parametrize('operation,params,word',[('set_series_style',{'markers':False},'관측점 표시를 껐습니다'),('set_series_style',{'markers':True},'관측점 표시를 켰습니다'),('set_series_style',{'dash':'dash'},'파선'),('set_axis_style',{'show_grid':False},'격자 표시를 껐습니다'),('set_presentation',{'design_template':'report'},'경제보고서형')])
def test_readable_edit_changes(operation,params,word):
 text=edit_change_description(ChartEditCommand(operation=operation,kind='STYLE_EDIT',label='검증 지표',params=params))
 assert word in text
 assert not any(token in text for token in ['False','True','markers','show_grid','design_template','{'])
def test_nested_params_and_internal_ids_are_not_shown():
 text=edit_change_description(ChartEditCommand(operation='update_shape',kind='STYLE_EDIT',value='internal-id',params={'data_anchor':{'start':'202001'}}))
 assert 'internal-id' not in text and 'data_anchor' not in text and '{' not in text
