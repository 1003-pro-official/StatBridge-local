"""Answer prose omits annotations while calculation evidence keeps its keys."""
import copy

import pytest

from narrative_labels import narrative_name
from report_summary import explain
from statistical_question import answer_question


LOAN = '예금은행 대출금리(신규취급액 기준) · 신규취급액 · DT_121Y006 · 신규취급액 · DT_121Y002 · 대출평균 1)'
DEPOSIT = '예금은행 수신금리(신규취급액 기준) · 신규취급액 · DT_121Y006 · 신규취급액 · DT_121Y002 · 저축성수신(금융채 제외) 1)'


@pytest.mark.parametrize('label,expected', [
    (LOAN, '예금은행 대출금리'), (DEPOSIT, '예금은행 수신금리'),
    ('생산자물가지수（기본분류） · 총지수 1)', '생산자물가지수'),
    ('중소기업 이자보상배율(제조업(전체)) 2)', '중소기업 이자보상배율'),
    ('DT_121Y006 · 가계대출 1)', '가계대출'),
])
def test_short_name_omits_codes_parentheses_footnotes_and_trailing_items(label, expected):
    assert narrative_name(label) == expected


def data():
    return [dict(label=label, sourceId=source, unit='연%', frequency='M', points=[
        dict(date='202601', value='4.2'), dict(date='202602', value='4.1')])
        for label, source in [(LOAN, 'DT_121Y006'), (DEPOSIT, 'DT_121Y002')]]


def assert_short(text):
    assert '예금은행 대출금리' in text and '예금은행 수신금리' in text
    assert all(value not in text for value in ['신규취급액', 'DT_', '대출평균', '저축성수신', '1)'])


def test_summary_and_question_only_shorten_the_prose():
    series = data()
    before = copy.deepcopy(series)
    summary = explain(series)
    answer = answer_question('대출금리와 수신금리의 하락 속도가 같은가?', series)
    assert answer['status'] == 'answered'
    for text in [summary['text'], ' '.join(answer['paragraphs'])]:
        assert_short(text)
    assert series == before
    assert summary['facts'][0]['label'] == LOAN
    assert answer['facts'][0]['observations'][0]['label'] == LOAN
    assert answer['scope']['series'][0]['sourceId'] == 'DT_121Y006'
    assert answer['facts'][0]['result'] == '-0.1'


def test_short_item_label_uses_its_table_name_for_prose():
    assert narrative_name('신규취급액 · 대출평균 1)', table_name='예금은행 대출금리(신규취급액 기준)') == '예금은행 대출금리'
