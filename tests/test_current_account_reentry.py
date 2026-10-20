import copy
from types import SimpleNamespace
import pytest
from agent_runtime import StatBridgeAgent


@pytest.fixture(scope='module')
def agent():
    return StatBridgeAgent(object(), ncp_client=SimpleNamespace(configured=False))


@pytest.mark.parametrize('query,table_id',[
    ('경상수지','DT_301Y017'),
    ('경상수지 원계열','DT_301Y013'),
    ('국제수지 경상수지 원계열 월별','DT_301Y013'),
    ('DT_301Y013 경상수지','DT_301Y013'),
    ('경상수지(계절조정)','DT_301Y017'),
])
def test_period_picker_same_question_keeps_a_revalidated_plan(agent,query,table_id):
    first=agent.resolve(query)
    assert first['status']=='resolved'
    before=copy.deepcopy(first['state'])
    again=agent.resolve(query,state=first['state'])
    assert again['status']=='resolved'
    assert again['api_plans']==[first['api_plan']]
    assert again['api_plan']['table_id']==table_id
    assert again['request_validation']['valid']
    assert first['state']==before


def test_reentry_does_not_accept_a_forged_classification(agent):
    first=agent.resolve('경상수지')
    state=copy.deepcopy(first['state'])
    state['_validated_api_plans'][0]['classifications']['objL1']='not-in-catalog'
    state['_validated_api_plans'][0]['exact_params']['objL1']='not-in-catalog'
    result=agent.resolve('경상수지',state=state)
    assert 'not-in-catalog' not in str(result.get('api_plan'))
