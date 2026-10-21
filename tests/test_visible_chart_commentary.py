import copy
import pytest
from visible_chart_commentary import refers_to_visible_chart,describe_visible_chart
from output_schema import PresentationStyle
from report_table import TableOptions
from test_statistical_question import item


@pytest.mark.parametrize('q',['해당 그래프의 변화율을 설명해줘','이 표의 추이를 설명해줘','현재 자료를 한국은행 보고서처럼 요약해줘','변화율을 설명해줘'])
def test_current_chart_references_are_deterministic(q):
    assert refers_to_visible_chart(q)


@pytest.mark.parametrize('q',['소비자물가의 전망을 알려줘','우리 회사 급여를 비교해줘','현재 그래프와 소비자물가를 비교해줘'])
def test_unrelated_subjects_are_not_silently_replaced(q):
    assert not refers_to_visible_chart(q)


def test_shares_use_percentage_points_not_relative_growth_and_no_raw_levels():
    data=[item('수입 달러 비중',('98.2','97.0','96.6'),unit='%',dates=('202501','202502','202503'))]
    before=copy.deepcopy(data);r=describe_visible_chart('해당 그래프의 변화율을 설명해줘',data);text=' '.join(r['paragraphs'])
    assert r['status']=='answered' and r['method']=='displayed_data_server_calculated'
    assert '1.6%p 하락' in text and '0.4%p 하락' in text and '하락폭은 직전보다 축소' in text
    assert '98.2' not in text and '96.6' not in text and data==before
    assert r['facts'][0]['result']=='-1.6'


def test_level_series_get_actual_relative_growth_and_turning_points():
    r=describe_visible_chart('해당 그래프의 변화율을 설명해줘',[item('물가지수',('100','120','110'),unit='2020=100',dates=('202501','202502','202503'))])
    assert '10% 상승' in ' '.join(r['paragraphs']) and '변화 방향이 바뀌었어' in ' '.join(r['paragraphs'])


def test_yearly_missing_input_names_exact_period_and_formula():
    r=describe_visible_chart('이 그래프의 전년동기 변화율을 설명해줘',[item('물가',('100','110'),unit='지수',dates=('202501','202503'))])
    assert r['status']=='insufficient_data' and '202403' in r['paragraphs'][0] and '÷' in r['paragraphs'][0]


def test_zero_denominator_and_category_do_not_become_fake_changes():
    r=describe_visible_chart('그래프 변화율 설명해줘',[item(values=('0','10'),unit='조원')]);assert r['status']=='insufficient_data' and '분모' in r['paragraphs'][0]
    r=describe_visible_chart('그래프 변화율 설명해줘',[item(frequency='category')]);assert r['status']=='insufficient_data' and '동일 항목' in r['paragraphs'][0]


def test_duplicate_timestamps_are_reported():
    r=describe_visible_chart('그래프 설명해줘',[item(dates=('202501','202501'))]);assert r['status']=='insufficient_data' and '중복' in r['paragraphs'][0]


def test_multiple_series_keep_full_period_baseline():
    r=describe_visible_chart('그래프 변화율 설명해줘',[item('수입',('80','90','100'),dates=('202501','202502','202503')),item('수출',('30','35','40'),dates=('202501','202502','202503'))])
    assert [f['result'] for f in r['facts']]==['20','10']


def test_explicit_previous_month_does_not_use_period_start_or_skip_missing_month():
    r=describe_visible_chart('그래프의 전월대비 변화율을 설명해줘',[item('지수',('100','120','132'),unit='지수',dates=('202501','202502','202503'))])
    assert r['facts'][0]['result']=='10.0'
    r=describe_visible_chart('그래프의 전월대비 변화율을 설명해줘',[item('지수',('100','132'),unit='지수',dates=('202501','202503'))])
    assert r['status']=='insufficient_data' and '202502' in r['paragraphs'][0]


@pytest.mark.parametrize('width,height',[(580,740),(379,614),(496,419),(3000,1200),(300,200)])
def test_no_old_axis_size_limits(width,height):
    assert PresentationStyle(width=width,height=height).width==width
    assert TableOptions(export_width=width,export_height=height).export_height==height


def test_total_pixel_allocation_limit_is_retained():
    with pytest.raises(ValueError):PresentationStyle(width=100000,height=100000)
    with pytest.raises(ValueError):TableOptions(export_width=100000,export_height=100000)


def test_endpoint_current_chart_needs_no_model_and_uses_displayed_period(monkeypatch,tmp_path):
    import account_auth as auth
    import bridge_api as api
    from test_account_auth import login,fixture_graph
    store=auth.AccountStore(tmp_path/'accounts.sqlite3');monkeypatch.setattr(auth,'STORE',store)
    client,user=login('test1');session=fixture_graph(monkeypatch,store,user,'visible-chart-test')
    class ForbiddenModel:
        configured=True
        def request(self,*a,**k):raise AssertionError('current-chart question must not call GPT')
    monkeypatch.setattr(api.agent.output_agent,'ncp_client',ForbiddenModel())
    session['output']['chartState'].update(period_start='202601',period_end='202602')
    response=client.post('/api/report/question',json={'edit_session_id':'visible-chart-test','revision':0,'question':'해당 그래프의 변화율을 설명해줘'})
    assert response.status_code==200,response.text
    answer=response.json();assert answer['method']=='displayed_data_server_calculated'
    assert answer['status']=='answered' and all(s['start']>='202601' and s['end']<='202602' for s in answer['scope']['series'])


def test_report_prose_names_dates_and_flat_change_without_redundant_zero():
    r=describe_visible_chart('해당 그래프의 변화율을 보여줘',[
        item('국가별 결제통화(수입) · 달러 (호주) · 비중(%)',('98.2','96.6'),dates=('202001','202512')),
        item('국가별 결제통화(수출) · 달러 (호주) · 비중(%)',('66.7','74.1'),dates=('202001','202512')),
        item('중국 비중',('88.5','90.3','90.3'),dates=('202001','202511','202512'))])
    text=' '.join(r['paragraphs'])
    assert '2020년 1월 대비 2025년 12월' in text
    assert '1.6%p 하락' in text and '7.4%p 상승' in text
    assert '비중(%)는' not in text and '0%p 변화가 없어' not in text
    assert '중국 비중은 2025년 11월 대비 변동이 없어' in text
    assert '등락을 반복' not in text
    assert r['facts'][-1]['recent']['change']=='0.0'


def test_explicit_year_comparison_does_not_claim_whole_period_direction():
    r=describe_visible_chart('그래프 전년대비 변화율 설명해줘',[item('지수',('100','130','90','110'),unit='지수',dates=('202301','202401','202501','202601'))])
    assert '중간에 등락을 반복' not in ' '.join(r['paragraphs'])
