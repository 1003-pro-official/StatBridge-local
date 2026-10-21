import base64
import io
import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader
from report_draft_export import render_draft_pdf


def image(width=1200,height=600):
    out=io.BytesIO();canvas=Image.new('RGB',(width,height),'white');ImageDraw.Draw(canvas).ellipse((10,10,80,80),fill='navy');canvas.save(out,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


def draft():
    return dict(title='경상수지 보고서 초안',paragraphs=['검증 지표의 최신 값은 12개입니다.'],
                plotlyFigure={'layout':{'width':1200,'height':600}},sources=[{'organizationId':'301','tableId':'DT_TEST'}],
                scope={'series':[{'label':'검증 지표','start':'202601','end':'202607','unit':'개'}]})


def test_real_pdf_contains_chart_and_korean_caption_with_a4_page():
    content=render_draft_pdf(draft(),image())
    assert content.startswith(b'%PDF-')
    pdf=PdfReader(io.BytesIO(content));assert len(pdf.pages)==1
    page=pdf.pages[0];text=page.extract_text()
    assert '경상수지 보고서 초안' in text and '12개입니다.' in text and 'DT_TEST' in text
    assert float(page.mediabox.width)==pytest.approx(8.27*72)
    assert len(page.images)==1
    assert page.images[0].image.width/page.images[0].image.height==pytest.approx(2)


def test_rejects_wrong_image_type_size_or_changed_ratio():
    for value in ['https://example.org/image.png','data:image/png;base64,wrong!',image(600,1200)]:
        with pytest.raises(ValueError):render_draft_pdf(draft(),value)


@pytest.mark.parametrize('width,height', [(650,520),(1300,1040),(1000,700),(400,1200)])
def test_pdf_preserves_explicit_report_image_dimensions(width,height):
    pdf=PdfReader(io.BytesIO(render_draft_pdf(draft(),image(width,height),image_width=width,image_height=height)))
    embedded=pdf.pages[0].images[0].image
    assert embedded.size==(width,height)


@pytest.mark.parametrize('width,height', [(None,520),(650,None),(399,520),(2401,520),(650,10001),(650.5,520),(True,520)])
def test_rejects_incomplete_or_invalid_pixel_dimensions(width,height):
    with pytest.raises(ValueError):
        render_draft_pdf(draft(),image(650,520),image_width=width,image_height=height)


def test_rejects_png_that_does_not_match_requested_pixels():
    with pytest.raises(ValueError,match='픽셀'):
        render_draft_pdf(draft(),image(650,520),image_width=1300,image_height=1040)


def test_pdf_download_endpoint_requires_owned_current_draft(monkeypatch,tmp_path):
    import account_auth as auth
    import bridge_api as api
    from fastapi.testclient import TestClient
    from test_account_auth import login,fixture_graph
    store=auth.AccountStore(tmp_path/'accounts.sqlite3');monkeypatch.setattr(auth,'STORE',store)
    client,user=login('test1');session=fixture_graph(monkeypatch,store,user,'draft-pdf')
    revision=session['output'].get('editVersion',0)
    session['report_drafts']={'draft1':{**draft(),'revision':revision}}
    body=dict(edit_session_id='draft-pdf',revision=revision,draft_id='draft1',image_data_url=image())
    assert TestClient(api.app).post('/api/report/draft/export',json=body).status_code==401
    response=client.post('/api/report/draft/export',json=body)
    assert response.status_code==200,response.text
    assert response.headers['content-type']=='application/pdf'
    assert 'attachment' in response.headers['content-disposition'] and response.content.startswith(b'%PDF-')
    assert client.post('/api/report/draft/export',json={**body,'revision':revision+1}).status_code==409
    assert client.post('/api/report/draft/export',json={**body,'draft_id':'unknown'}).status_code==409
    assert client.post('/api/report/draft/export',json={**body,'image_data_url':image(600,1200)}).status_code==422
    sized={**body,'image_data_url':image(650,520),'image_width':650,'image_height':520}
    assert client.post('/api/report/draft/export',json=sized).status_code==200
    for invalid in [{'image_width':None},{'image_width':399},{'image_width':650.5},{'image_width':1300},{'image_height':None}]:
        assert client.post('/api/report/draft/export',json={**sized,**invalid}).status_code==422
    other,_=login('test2')
    assert other.post('/api/report/draft/export',json=body).status_code==404
