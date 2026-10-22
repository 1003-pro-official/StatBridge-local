"""Role separation and request compatibility, no provider calls."""
import json
import pytest
from openai_chart_client import OpenAIChartClient, text_model_client

@pytest.mark.parametrize('chart,text,expected',[(None,None,('gpt-6.1-sol','gpt-6.1-sol')),('gpt-5.4',None,('gpt-5.4','gpt-5.4')),('gpt-6.1-sol','gpt-6-luna',('gpt-6.1-sol','gpt-6-luna')),('','',('gpt-6.1-sol','gpt-6.1-sol'))])
def test_config_and_single_model_rollback(monkeypatch,chart,text,expected):
    for key,value in [('OPENAI_CHART_MODEL',chart),('OPENAI_TEXT_MODEL',text)]:
        if value is None:monkeypatch.delenv(key,raising=False)
        else:monkeypatch.setenv(key,value)
    strong=OpenAIChartClient(api_key='synthetic');cheap=text_model_client(strong)
    assert (strong.settings.main_model,cheap.settings.main_model)==expected
    assert OpenAIChartClient(model='pinned').settings.main_model=='pinned'

def test_pdf_detail_budget_and_privacy():
    class Transport:
        def post(self,url,**kw):
            body=kw['json'];self.body=body
            class Response:
                ok=True;status_code=200
                def json(self):return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"ok":true}'}]}]}
            return Response()
    transport=Transport();client=OpenAIChartClient(api_key='synthetic',session=transport)
    client.request('system','user',max_tokens=380,json_mode=True,references=[{'name':'sample.pdf','mime':'application/pdf','data_url':'data:application/pdf;base64,synthetic'}])
    body=transport.body
    assert body['store'] is False and body['max_output_tokens']==4096
    assert body['reasoning']=={'effort':'low'}
    assert body['input'][0]['content'][1]['detail']=='low'
    assert body['text']['format']['type']=='json_object'

def test_sensitive_roles_keep_strong_client():
    import bridge_api as api
    assert api.agent.workflow.derived_runtime.planner.client is api.strong_client
    if isinstance(api.edit_agent.model, __import__('openai_chart_client').OpenAIEditModel):
        assert api.edit_agent.model.client is api.strong_client
        assert api.report_client is api.strong_client
        assert api.agent.output_agent.ncp_client is not api.strong_client
