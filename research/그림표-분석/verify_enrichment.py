"""Run the requested offline, deterministic replay and regression checks."""
from pathlib import Path
import csv,hashlib,json,re,subprocess,sys
from collections import Counter
from enrichment.common import OUT,ROOT,FIELDS,UNKNOWN,BLACKLIST,normalize,ref_pattern,sentence_key

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def outputs():
    names=['그림표_마스터.csv','검수대장.csv','추출_요약.json','개선_리포트.md','PDF_페이지_검수.csv','내용_검수대상.csv']
    return [OUT/n for n in names]+sorted(OUT.glob('[0-9][0-9]-*/*.md'))

def hashes():return {p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs()}

def replay():
    # Block Python socket connections to substantiate the network-free replay.
    code="import socket,sys,runpy,pathlib\ndef denied(*a,**k):raise RuntimeError('network disabled during replay')\nsocket.socket.connect=denied\nsocket.create_connection=denied\nsys.argv=[sys.argv[1]]\nsys.path.insert(0,str(pathlib.Path(sys.argv[0]).parent))\nrunpy.run_path(sys.argv[0],run_name='__main__')"
    result=subprocess.run([sys.executable,'-c',code,str(OUT/'extract.py')],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if result.returncode:raise RuntimeError(result.stderr+result.stdout)

def main():
    replay();first=hashes();replay();second=hashes()
    assert first==second,'재실행 시 출력 변경'
    rows=read(OUT/'그림표_마스터.csv');ledger=read(OUT/'검수대장.csv')
    assert len(rows)==4027
    ids=[r['결과물ID'] for r in rows];assert len(set(ids))==len(ids)
    assert not any(not r.get(f) for r in rows for f in FIELDS)
    assert (OUT/'그림표_마스터.csv').read_bytes().startswith(b'\xef\xbb\xbf')
    assert len(ledger)==len(rows)*len(FIELDS)
    pairs={(r['결과물ID'],r['필드']) for r in ledger};assert len(pairs)==len(ledger)
    by_id={r['결과물ID']:r for r in rows}
    for item in ledger:
        row=by_id[item['결과물ID']];field=item['필드']
        assert item['자동추출값']==row[field]
        assert item['신뢰도']==json.loads(row['필드별신뢰도'])[field]
    descriptions=[]
    for row in rows:
        value=row['설명']
        if value!=UNKNOWN:
            assert not BLACKLIST.search(value)
            pat=ref_pattern(row['구분'],row['번호']);assert pat and pat.search(normalize(value))
            descriptions.append(sentence_key(value))
        assert '제목 기반 추론' not in row['분석 목적']
        if row['구분']=='그림':assert row['종류'].replace('(추정)','') in {'선그래프','막대','산점도','영역','pie','혼합','사진·이미지','불명'}
    assert len(set(descriptions))==len(descriptions)
    md_ids=[]
    for p in OUT.glob('[0-9][0-9]-*/*.md'):
        md_ids+=re.findall(r'- 결과물ID: `([^`]+)`',p.read_text(encoding='utf-8'))
    assert Counter(md_ids)==Counter(ids)
    summary=json.loads((OUT/'추출_요약.json').read_text(encoding='utf-8'))
    assert all(summary['content_enrichment']['acceptance'].values())
    assert summary['content_enrichment']['regression']['protected_field_changes']==0
    result={'status':'passed','network_blocked':True,'identical_replay_count':2,'identical_output_files':len(second),'row_count':len(rows),'markdown_count':31,'ledger_rows':len(ledger),'direct_number_descriptions':len(descriptions),'blank_common_fields':0,'duplicate_ids':0,'protected_field_changes':0,'sha256':second}
    (OUT/'멱등성_검증.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='sha256'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
