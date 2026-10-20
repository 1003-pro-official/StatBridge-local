"""Research guardrails: omission/wrong measure must not become a passing example."""
import importlib.util
from pathlib import Path


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_plan_check_rejects_missing_and_wrong_series():
    check = module('build').check_plans
    expected = [{'table_id': 'T', 'values': ['원계열']}, {'table_id': 'T', 'values': ['순환변동치']}]
    labels = {('T', 'a'): '원계열', ('T', 'b'): '순환변동치'}
    one = {'table_id': 'T', 'classifications': {'objL1': 'a'}}
    two = {'table_id': 'T', 'classifications': {'objL1': 'b'}}
    assert not check([one], expected, labels)
    assert not check([one, one], expected, labels)
    assert not check([one, two | {'table_id': 'OTHER'}], expected, labels)
    assert check([two, one], expected, labels)


def test_listing_and_attachment_parsing_preserve_official_location():
    m = module('collect')
    page = '''<li class="bbsRowCls"><span class="date">2025.10.29</span>
    <a href="/portal/bbs/P0000599/view.do?nttId=12&amp;menuNo=200455" class="title">
    <!-- 공지사항 --> 기업경영분석</a></li>'''
    row = m.parse_listing(page)[0]
    assert row['title'] == '기업경영분석'
    assert row['url'].endswith('nttId=12&menuNo=200455')
    links = m.attachment_links('<a href="/fileSrc/portal/a/1/a.pdf" title="본문.pdf">PDF</a>')
    assert links == {'https://www.bok.or.kr/fileSrc/portal/a/1/a.pdf': '본문.pdf'}


def test_caption_candidates_are_review_only_and_skip_contact_prose():
    candidates = module('build').caption_candidates('''예금은행 가중평균금리\n(연 %, %p)
    □ 금리가 전월 대비 상승하였다.\n문의: 금리 추이팀\nhttp://example.com/추이
    가계신용 잔액 추이\n(십억원)''')
    assert candidates == ['예금은행 가중평균금리', '가계신용 잔액 추이']


def test_value_comparison_rejects_missing_duplicate_and_non_numeric_rows():
    same = module('audit_values').same_rows
    row = {'PRD_DE': '202512', 'ITM_ID': 'x', 'C1': 'a', 'DT': '1.00'}
    assert same([row], [row | {'DT': '1.0'}])
    assert not same([row], [])
    assert not same([row, row], [row])
    assert not same([row | {'DT': '-'}], [row | {'DT': '-'}])


def test_non_numeric_observations_do_not_pass_as_a_complete_period():
    check = module('build').numeric_rows
    assert check([{'DT': '1,200.5'}, {'DT': 0}])
    for value in ['-', 'nan', 'inf', '', None, 'estimated']:
        assert not check([{'DT': value}])


def test_original_pilot_requires_all_periods_once_and_finite_values():
    import pytest
    check = module('pilots').complete
    assert len(check([{'PRD_DE':'202501','DT':'1'}], ['202501'])) == 1
    for rows in [[], [{'PRD_DE':'202501','DT':'1'}]*2, [{'PRD_DE':'202501','DT':'nan'}]]:
        with pytest.raises(ValueError):check(rows, ['202501'])


def test_original_pdf_decimal_parser_handles_merged_cells_and_signs():
    from decimal import Decimal
    assert module('pilots').numbers('1,234.5 -0.02 +0.13') == [Decimal('1234.5'),Decimal('-0.02'),Decimal('0.13')]
