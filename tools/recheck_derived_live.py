"""Recheck recorded real KOSIS observations as raw Decimal, no new API calls."""
import json,sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from derived_eval_reference import evaluate,compare
ROOT=Path(__file__).resolve().parents[1]

def main():
    path=ROOT/'eval/derived_after_kosis_all.json';report=json.loads(path.read_text(encoding='utf8'))
    for row in report['records']:
        if not row.get('receipt'):continue
        identifier=row['receipt']['calculationId']
        assert len(identifier)==32 and all(c in '0123456789abcdef' for c in identifier)
        original=ROOT/'.venv/cache/derived-independent-20261019/live-evidence'/f'{identifier}.json'
        target=ROOT/'eval/derived_live_records'/original.name
        target.parent.mkdir(exist_ok=True)
        if original.exists():target.write_bytes(original.read_bytes())
        record=json.loads(target.read_text(encoding='utf8'))['evidence'];p=record['plan'];raw={}
        for s in p['sources']:
            rows=row['raw_sources'][s['alias']]['rows']
            raw[s['alias']]={'values':{str(r['PRD_DE']):None if r.get('DT') is None or str(r['DT']).strip() in {'','-','..','...','NA','N/A'} else Decimal(str(r['DT']).replace(',','')) for r in rows},
                'unit':str(rows[0]['UNIT_NM']).strip(),'frequency':s['frequency'],'source_ids':[s['alias']]}
        check=compare(evaluate(p,raw),{'series':{k:SimpleNamespace(**v) for k,v in record['node_results'].items()}})
        row['numerical_check']=check;row['numerical_check']['oracle_input']='raw KOSIS DT strings -> Decimal, independent parser/calendar/arithmetic'
        row['record_file']=str(target.relative_to(ROOT)).replace('\\','/')
        if not check['passed']:row.update(status='FAIL',failure_type='independent_raw_decimal_mismatch')
    report['summary']['passed']=sum(r['status']=='PASS' for r in report['records'])
    report['summary']['failed']=sum(r['status']=='FAIL' for r in report['records'])
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps([{'id':r['id'],'status':r['status'],'check':r.get('numerical_check')} for r in report['records']],ensure_ascii=False))
    return int(any(r['status']=='FAIL' for r in report['records']))

if __name__=='__main__':raise SystemExit(main())
