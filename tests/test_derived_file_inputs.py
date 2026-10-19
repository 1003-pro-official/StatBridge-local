"""Synthetic input files; no mock results labelled actual provider data."""
import base64,csv,hashlib,io,json,zipfile
from xml.sax.saxutils import escape
import pytest
from derived_file_inputs import decode_file,FIELDS
from derived_input_guidance import input_guidance
from test_derived_supplement import setup,csv_text

def workbook_bytes(formula=False,dimension='A1:E5',extra=None,malformed=False):
    # Minimal OOXML parser fixture, not a user workbook or computed artifact.
    rows=[FIELDS]+[[f'20200{i}',2,'지수','M','독립 시험 자료'] for i in range(1,5)]
    xml=[]
    for i,row in enumerate(rows,1):
        cells=[]
        for j,v in enumerate(row):
            coordinate=f'{chr(65+j)}{i}'
            if formula and i==2 and j==1:cells.append(f'<c r="{coordinate}"><f>1+1</f><v>2</v></c>')
            else:cells.append(f'<c r="{coordinate}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>')
        xml.append(f'<row r="{i}">'+''.join(cells)+'</row>')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="data" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml','<not-closed>' if malformed else f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="{dimension}"/><sheetData>'+''.join(xml)+'</sheetData></worksheet>')
        if extra:z.writestr(*extra)
    return stream.getvalue()

def payload(format):
    if format=='xlsx':return base64.b64encode(workbook_bytes()).decode(),'base64'
    if format=='json':return json.dumps(list(csv.DictReader(io.StringIO(csv_text()))),ensure_ascii=False),'utf8'
    if format=='tsv':return csv_text().replace(',','\t'),'utf8'
    return csv_text(),'utf8'

@pytest.mark.parametrize('format',['csv','json','tsv','xlsx'])
def test_all_formats_share_calculation_validation_and_raw_file_hash(setup,format):
    service,calls,_,_=setup
    wid=service.start(1,'2020년 1월부터 2020년 4월까지 경제심리지수와 사용자 비용지수 비율 계산')['supplement']['workspaceId']
    content,encoding=payload(format);service.upload(1,wid,'cost','source.'+format,content,encoding)
    state=service.load(1,wid);stored=state['files']['cost']
    raw=service.path(1,wid).parent/'files'/(stored['file_id']+'.'+format)
    assert hashlib.sha256(raw.read_bytes()).hexdigest()==stored['sha256']
    assert service.resume(1,wid)['result']['execution']['rows'][-1]['DT']==pytest.approx(66.55)
    assert len(calls)==1

@pytest.mark.parametrize('format',['csv','json','tsv'])
def test_blank_templates_never_become_observations(setup,format):
    service,_,_,_=setup;wid=service.start(1,'경제심리지수와 비용 파일의 비율 계산')['supplement']['workspaceId']
    template=service.template(1,wid,'cost',format)
    with pytest.raises(ValueError):service.upload(1,wid,'cost','blank.'+format,template)
    assert service.load(1,wid)['files']=={}

@pytest.mark.parametrize('filename,content,encoding',[
    ('a.json','{}','utf8'),('a.json','[{"period":1,"period":2}]','utf8'),('a.json','[NaN]','utf8'),
    ('a.json','[{"period":"202001"}]','utf8'),('a.xls','data','utf8'),('a.pdf','data','utf8'),
    ('a.xlsx','not base64','base64'),('../a.csv',csv_text(),'utf8'),('a.csv','x'*2_000_001,'utf8'),
],ids=['object_not_array','duplicate_key','nonfinite_json','missing_fields','legacy_xls','pdf','invalid_base64','path_traversal','oversized'])
def test_invalid_or_unsupported_files_are_rejected(filename,content,encoding):
    with pytest.raises(ValueError):decode_file(filename,content,encoding)

@pytest.mark.parametrize('raw',[
    workbook_bytes(formula=True),workbook_bytes(dimension='A1:XFD1048576'),
    workbook_bytes(extra=('xl/externalLinks/externalLink1.xml','<link/>')),
    workbook_bytes(extra=('xl/comments1.xml','<!DOCTYPE foo [<!ENTITY x "boom">]><x/>')),
    workbook_bytes(extra=('xl/large.xml','a'*8_000_001)),
],ids=['formula','oversized_dimensions','external_link','entity','zip_expansion'])
def test_xlsx_formulas_external_entities_and_zip_expansion_are_blocked(raw):
    with pytest.raises(ValueError):decode_file('a.xlsx',base64.b64encode(raw).decode(),'base64')

def test_guidance_distinguishes_synthetic_from_official_search_candidates():
    synthetic=input_guidance({'required_data':'가상비용지수 CSV','reason':'시험용 합성 자료'})
    assert synthetic['kind']=='self_provided' and synthetic['links']==[]
    official=input_guidance({'required_data':'소비자물가지수','reason':'승인 범위에서 미확인'})
    assert official['kind']=='search_candidates' and official['links'][0]['url']=='https://kosis.kr/'
    assert '확인한 것은 아닙니다' in official['description']

def test_json_template_and_binary_upload_http_contract(setup,monkeypatch):
    import bridge_api as api
    from authenticated_client import TestClient
    service,_,_,_=setup;monkeypatch.setattr(api,'derived_supplements',service);client=TestClient(api.app)
    r=client.post('/api/derived/supplement',json={'query':'경제심리지수와 사용자 비용지수 비율 계산'})
    wid=r.json()['supplement']['workspaceId']
    assert r.json()['supplement']['acceptedFormats']==['csv','json','tsv','xlsx']
    r=client.get(f'/api/derived/supplement/{wid}/template/cost?format=json')
    assert r.status_code==200 and r.json()[0]['value'] is None
    content,encoding=payload('xlsx')
    r=client.post(f'/api/derived/supplement/{wid}/upload',json={'alias':'cost','filename':'data.xlsx','content':content,'encoding':encoding})
    assert r.status_code==200,r.text
    r=client.post(f'/api/derived/supplement/{wid}/resume',json={});assert r.status_code==200,r.text
    assert r.json()['status']=='need_output_config'


def test_semantic_review_receives_validated_upload_stage_without_raw_values(setup):
    service,_,_,_=setup;model=service.base.planner.client;request=model.request;reviews=[]
    def capture(system,user,**kwargs):
        if system.startswith('경제학적 의미 검토자'):
            context=json.loads(user);reviews.append(context)
            assert context['authorized_file_inputs'][0]['table_id']=='USER_FILE:cost'
            assert len(context['authorized_file_inputs'][0]['sha256'])==64
            assert '완료' in context['workflow_stage']
            assert context['original_user_request'] and '현재 사용자 후속 요청' in context['query']
            assert 'rows' not in context['authorized_file_inputs'][0]
        return request(system,user,**kwargs)
    model.request=capture
    wid=service.start(1,'경제심리지수와 사용자 비용지수 비율 계산')['supplement']['workspaceId']
    service.upload(1,wid,'cost','cost.json',payload('json')[0])
    state=service.load(1,wid);state['question']='이전 확인 요청';service.save(state)
    assert service.resume(1,wid)['status']=='calculated' and len(reviews)==1
    assert 'question' not in service.load(1,wid)


def test_malformed_xml_is_a_validation_error_not_an_unhandled_parser_error():
    raw=workbook_bytes(malformed=True)
    with pytest.raises(ValueError):decode_file('a.xlsx',base64.b64encode(raw).decode(),'base64')


def test_binary_text_upload_preserves_original_utf8_bom_bytes():
    raw=b'\xef\xbb\xbf'+csv_text().encode()
    actual,rows,format=decode_file('a.csv',base64.b64encode(raw).decode(),'base64')
    assert actual==raw and format=='csv' and rows[0]['period']=='202001'


@pytest.mark.parametrize('xml',[
    b"<Relationship TargetMode='External' Target='https://example.invalid/'/>",
    '<!DOCTYPE x [<!ENTITY y "z">]><x/>'.encode('utf-16'),
],ids=['single_quoted_external_reference','utf16_entity'])
def test_encoded_xml_references_are_rejected_before_workbook_parser(xml):
    raw=workbook_bytes(extra=('xl/extra.xml',xml))
    with pytest.raises(ValueError):decode_file('a.xlsx',base64.b64encode(raw).decode(),'base64')
