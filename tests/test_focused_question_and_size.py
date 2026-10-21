import io
import copy
import pytest
from decimal import Decimal
from focused_question_answer import focused_answer
from statistical_question import answer_question
from test_statistical_question import item,Planner
from report_table import build_table,TableOptions,render_table_file
from test_table_layout import CASES


def test_speed_answer_focuses_on_changes_and_preserves_audit():
    raw=answer_question('어느 금리가 더 빠르게 하락했나?', [item(),item('수신금리',('3.50','3.30'))],Planner('speed',(0,1)))
    before=copy.deepcopy(raw);result=focused_answer(raw);text=' '.join(result['paragraphs'])
    assert '수신금리의 변화 속도가 가장 빨라' in text
    assert '0.20' in text and '3.30' not in text and '5.00' not in text
    assert '기록하' not in text and '습니다' not in text
    assert raw==before and result['facts']==raw['facts']


def test_levels_are_never_echoed_and_missing_answers_are_casual():
    raw=answer_question('금리 값은?', [item(values=('9.8765',))],Planner())
    result=focused_answer(raw)
    assert '9.8765' not in ' '.join(result['paragraphs'])
    assert '표에서 확인해 줘' in result['paragraphs'][0]
    result=focused_answer({'status':'insufficient_data','paragraphs':['자료가 없습니다. 추가 자료가 필요합니다.'],'limitations':[]})
    assert result['paragraphs']==['자료가 없어. 추가 자료가 필요해.']


@pytest.mark.parametrize('kind',['png','pdf'])
@pytest.mark.parametrize('grid',[True,False])
def test_table_export_dimensions_preserve_original_content(kind,grid):
    c=copy.deepcopy(CASES[0]);c['options'].update(export_width=1400,export_height=750)
    if not grid:c['options']['layout']={'enabled':False}
    doc=build_table(c['series'],TableOptions.model_validate(c['options']),title=c['title']);before=copy.deepcopy(doc)
    content=render_table_file(doc,kind)
    if kind=='png':
        from PIL import Image
        im=Image.open(io.BytesIO(content));assert im.width==1400 and im.height%750==0
    else:
        from pypdf import PdfReader
        pages=PdfReader(io.BytesIO(content)).pages
        assert pages and all(float(p.mediabox.width)==pytest.approx(1400*.72) and float(p.mediabox.height)==pytest.approx(750*.72) for p in pages)
    assert doc==before


@pytest.mark.parametrize('patch',[{'export_width':0},{'export_height':0},{'export_width':True}])
def test_invalid_export_size_is_rejected(patch):
    with pytest.raises(ValueError):TableOptions.model_validate(patch)


@pytest.mark.parametrize('kind',['png','pdf'])
def test_graph_vector_exports_share_explicit_pixel_size(kind):
    from output_schema import ChartSpec
    from report_export import render_file
    series=[item(values=('4.53','4.36'))]
    spec=ChartSpec.model_validate({'title':'금리 비교','chart_type':'line','presentation':{'width':1400,'height':750}})
    content=render_file(series,spec,{},kind)
    if kind=='png':
        from PIL import Image
        assert Image.open(io.BytesIO(content)).size==(1400,750)
    else:
        from pypdf import PdfReader
        page=PdfReader(io.BytesIO(content)).pages[0]
        assert float(page.mediabox.width)==pytest.approx(1400*.72)
        assert float(page.mediabox.height)==pytest.approx(750*.72)
