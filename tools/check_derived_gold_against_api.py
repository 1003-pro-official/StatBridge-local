"""Review sealed questions against retained DIRECT API responses, never LLM answers."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/backend'),str(ROOT/'src/agent'),str(ROOT/'tools')]
from live_derived_catalog import LiveDerivedCatalog
from statbridge_mcp.metadata_store import MetadataStore
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import validate_plan
from run_derived_eval import dump

class ApiSnapshot:
    api_key='not_used'
    def _get(self,url,params):
        r=json.loads((ROOT/'eval/derived_api_metadata_349_records'/(params['tblId']+'.json')).read_text(encoding='utf8'))
        kind=r['types'][params['type']]
        if kind['status']!='PASS':raise ValueError('Actual API request failed')
        return kind['rows']

def main():
    report=json.loads((ROOT/'eval/derived_api_metadata_349.json').read_text(encoding='utf8'))
    assert report['summary']['executed']==349
    catalog=LiveDerivedCatalog(MetadataStore(),ApiSnapshot());cases=[json.loads(x) for x in (ROOT/'eval/derived_goldset_v5_300.jsonl').read_text(encoding='utf8').splitlines()]
    records=[]
    for c in cases:
        row={'id':c['id'],'status':'PASS','basis':'actual TBL/ITM/PRD API response','positive_plan':bool(c.get('expected_plan'))}
        try:
            if c.get('expected_plan'):
                p=ExpressionPlan.model_validate(c['expected_plan']);validate_plan(p,catalog)
                for s in p.sources:
                    m=catalog.validate_source_selection(s)
                    if not any(r['frequency']==s.frequency and r['start_period']<=p.start_period<=p.end_period<=r['end_period'] for r in m['periods']):
                        raise ValueError('Actual API publication interval does not cover the question')
            else:row['scope']='negative/clarification contract; no positive API series claimed'
        except Exception as exc:row.update(status='FAIL',error_type=type(exc).__name__,error=str(exc))
        records.append(row)
    result={'origin':'actual_KOSIS_metadata_API_responses','registry_size':349,'direct_API_summary':report['summary'],
            'question_set':'derived_goldset_v5_300.jsonl','questions_changed':False,'summary':{'executed':300,'passed':sum(r['status']=='PASS' for r in records),'failed':sum(r['status']=='FAIL' for r in records)},'records':records}
    dump(ROOT/'eval/derived_v6_api_question_review.json',result);print(json.dumps(result['summary']))
    return int(result['summary']['failed']>0)

if __name__=='__main__':raise SystemExit(main())
