import copy
import pytest
from report_conversation import reply,refresh
from report_markdown import append_answer,markdown
from report_register import report_text
from test_report_conversation import data,NoModel


def test_report_register_keeps_figures_and_uses_declarative_ending():
    a,s=reply('그래프 변화율 설명해줘',data(),None,0,NoModel())
    text=' '.join(a['paragraphs'])
    assert '0.5%p 하락하였다' in text and not any(w in text for w in ['했어','이야','같아','이어갔어'])
    assert a['register']=='report'
    assert report_text('비교 기준은 2025년 1월이야.')=='비교 기준은 2025년 1월이다.'


def test_markdown_is_in_click_order_and_snapshots_not_rewritten_after_edit():
    _,s=reply('그래프 변화를 설명해줘',data(),None,0,NoModel())
    _,s=reply('그중 가장 많이 하락한 것은?',data(),s,0,NoModel())
    s['markdown_entries']=append_answer(s,2,0)
    s['markdown_entries']=append_answer(s,1,0)
    text=markdown(s['markdown_entries'])
    assert s['markdown_entries'][0]['turnId']==2 and s['markdown_entries'][1]['turnId']==1
    original=copy.deepcopy(s['markdown_entries'])
    updated=data();updated[1]['points'][-1]['value']='2.0'
    refreshed=refresh(s,updated,1)
    assert refreshed['markdown_entries']==original
    assert markdown(refreshed['markdown_entries'])==text
    assert len(append_answer(s,2,0))==2
    with pytest.raises(ValueError):append_answer(s,1,1)


def test_markdown_table_safe_pipe_and_no_raw_levels():
    _,s=reply('그래프 변화를 설명해줘',data(),None,0,NoModel())
    _,s=reply('표로 정리해줘',data(),s,0,NoModel())
    entries=append_answer(s,2,0);entries[0]['table']['rows'][0][0]='대출|금리'
    text=markdown(entries)
    assert '대출\\|금리' in text and '| --- |' in text
    assert '5.1' not in text and '2.6' not in text and '0.5' in text
    assert text.count('# 통계 분석 보고서')==1


def test_incomplete_answers_and_resource_limit_are_not_silently_saved():
    a,s=reply('전년대비로 보여줘',data(),None,0,NoModel())
    assert a['status']=='insufficient_data'
    with pytest.raises(ValueError):append_answer(s,1,0)
    _,s=reply('그래프 변화율 설명해줘',data(),None,0,NoModel())
    s['markdown_entries']=[{'turnId':100+i,'revision':0} for i in range(50)]
    with pytest.raises(ValueError,match='50'):append_answer(s,1,0)
