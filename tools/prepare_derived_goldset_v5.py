"""Final API-grounded question repair. Does NOT read evaluated GPT answers.

Positive requests use observed series where parent headings returned no data.
Real missing-unit responses become explicit safe-stop questions, never invented units.
"""
import copy,hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'src/agent'),str(ROOT/'src/backend')]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
from prepare_derived_eval_v2 import audit,MetadataStore,DerivedCatalogTools
from expression_tree_schema import SourceSelection
from dynamic_expression_executor import source_series
from statbridge_mcp.statistics_service import StatisticsService
from mcp_gateway import McpToolGateway
from run_derived_eval import dump


def key(source):return (source['table_id'],source['item_id'],tuple(sorted(source['classifications'].items())),source['frequency'])


def main():
    oldfile=ROOT/'eval/derived_goldset_v4_300.jsonl';cases=[json.loads(x) for x in oldfile.read_text(encoding='utf8').splitlines()]
    source_report=json.loads((ROOT/'eval/derived_v2_kosis_source_verification.json').read_text(encoding='utf8'))
    prior_validation=json.loads((ROOT/'eval/derived_goldset_v4_validation.json').read_text(encoding='utf8'))
    store=MetadataStore();catalog=DerivedCatalogTools(store);gateway=McpToolGateway(StatisticsService(store))
    failures={key(r['source']):r for r in source_report['records'] if r['status']=='FAIL'}
    fixes={};probes=[]
    for identity,evidence in failures.items():
        original=evidence['source']
        if evidence['failure_kind']=='validation_error' and evidence.get('observed_unit_set')==['None']:
            fixes[identity]={'kind':'verified_unit_absence','evidence_id':evidence['id']};continue
        metadata=catalog.get_table_metadata(original['table_id']);replacement=None
        # Test actual descendants only, preserving every other selected dimension.
        for dimension in metadata['dimensions']:
            selected=original['classifications'].get(dimension['mcp_param'])
            descendants=[v for v in dimension['values'] if v.get('parent_class_id')==selected]
            for child in descendants[:5]:
                candidate=copy.deepcopy(original);candidate['classifications'][dimension['mcp_param']]=child['class_id']
                parsed=SourceSelection.model_validate(candidate);catalog.validate_source_selection(parsed)
                observation={'source':candidate,'first':evidence['first'],'last':evidence['last'],'origin':'actual_KOSIS_API'}
                response=gateway.get_statistics(table_id=parsed.table_id,item_id=parsed.item_id,classifications=parsed.classifications,
                    frequency=parsed.frequency,start_period=evidence['first'],end_period=evidence['last'],prefer_local=False,allow_fallback=False)
                observation['observed_units']=sorted({str(r.get('UNIT_NM')) for r in response.get('rows',[])})
                observation['response_status']=response.get('status')
                observation['raw_preview']=[{k:r.get(k) for k in ['ORG_ID','TBL_ID','ITM_ID','PRD_DE','PRD_SE','DT','UNIT_NM']} for r in response.get('rows',[])[:2]]
                try:
                    series=source_series(parsed,response)
                    observation.update(status='PASS',unit=series.unit,observations=len(series.values))
                    candidate['required_data']=catalog.selection_text(parsed)
                    replacement=candidate;probes.append(observation);break
                except ValueError as exc:observation.update(status='FAIL',error=str(exc));probes.append(observation)
            if replacement:break
        fixes[identity]={'kind':'verified_descendant' if replacement else 'verified_unavailable_selection',
            'replacement':replacement,'evidence_id':evidence['id']}
    changes=[]
    for case in cases:
        before=copy.deepcopy(case);case['goldset_version']='5.0'
        matches=[(s,fixes[key(s)]) for s in case.get('allowed_sources',[]) if key(s) in fixes]
        if matches:
            source,fix=matches[0]
            if fix['kind']=='verified_descendant':
                replacement={**fix['replacement'],'alias':source['alias']}
                case['query']=case['query'].replace(source['required_data'],replacement['required_data'])
                case['query']+=' 원자료 분류는 '+json.dumps(replacement['classifications'],ensure_ascii=False,sort_keys=True)+'로 특정합니다.'
                case['allowed_sources']=[replacement if key(s)==key(source) else s for s in case['allowed_sources']]
                for field in ['expected_plan','previous_plan']:
                    if case.get(field):case[field]['sources']=[replacement if key(s)==key(source) else s for s in case[field]['sources']]
                case['question_style']='explicit_observed_descendant_of_unqueryable_catalog_heading'
            else:
                condition='실제 KOSIS 응답에서 UNIT_NM이 누락되어 검증된 단위를 확정할 수 없습니다' if fix['kind']=='verified_unit_absence' else '이 상위 분류 선택으로는 실제 KOSIS 원자료를 가져오지 못했습니다'
                case['unexecutable_plan_reference']=case.get('expected_plan')
                case['expected_plan']=None;case['expected_result']='safe_stop';case['accepted_statuses']=['unavailable','need_details']
                case['query']=f'{source["required_data"]} (통계표 {source["table_id"]}, 항목 {source["item_id"]})의 원자료 점검 결과, {condition}. 단위나 다른 세부항목을 임의로 추정해 대체하지 말고 현재 이 자료로 파생 계산을 진행할 수 없는 이유와 필요한 보완 자료를 알려주세요.'
                case['question_style']='verified_actual_API_failure_or_unit_absence'
                case['observed_blocker']={'kind':fix['kind'],'evidence_id':fix['evidence_id'],'source':source}
        if case['query']!=before['query'] or case['expected_result']!=before['expected_result']:
            changes.append({'id':case['id'],'before_query':before['query'],'after_query':case['query'],
                'reason':matches[0][1]['kind'],'source_evidence':matches[0][1]['evidence_id'],
                'answer_changed':case['expected_plan']!=before.get('expected_plan'),'basis':'actual KOSIS source adapter verification, not evaluated GPT output'})
    errors=[{'id':c['id'],'errors':audit(c,catalog)} for c in cases if audit(c,catalog)]
    for case in cases:
        for s in case.get('allowed_sources',[]):catalog.validate_source_selection(SourceSelection.model_validate(s))
    assert not errors,errors
    assert Counter(c['category'] for c in cases)==Counter(json.loads(x)['category'] for x in oldfile.read_text(encoding='utf8').splitlines())
    assert len({c['query'] for c in cases})==300
    family_splits={}
    for c in cases:family_splits.setdefault(c['family'],set()).add(c['split'])
    assert all(len(s)==1 for s in family_splits.values())
    body=''.join(json.dumps(c,ensure_ascii=False,sort_keys=True)+'\n' for c in cases);destination=ROOT/'eval/derived_goldset_v5_300.jsonl'
    if destination.exists() and destination.read_text(encoding='utf8')!=body:raise RuntimeError('v5 sealed; do not overwrite answers')
    destination.write_text(body,encoding='utf8',newline='\n')
    validation={**prior_validation,'version':'5.0','v5_sha256':hashlib.sha256(body.encode()).hexdigest(),'pre_evaluation_validation_errors':errors,
        'changes_from_v4':changes,'actual_descendant_probes':probes,'repair_source':'registered metadata and actual KOSIS responses only; no model evaluation files read',
        'positive_planning_expected':sum(c['expected_result']=='compute' for c in cases),'safe_stop_expected':sum(c['expected_result']=='safe_stop' for c in cases),
        'unchanged_v4_questions':300-len(changes),'source_question_compatibility':'actual missing-unit/error cases explicitly ask to stop; no positive computation answer for an unverified source',
        'human_expert_approval':False}
    dump(ROOT/'eval/derived_goldset_v5_validation.json',validation)
    print(json.dumps({'version':'5.0','cases':300,'changed_from_v4':len(changes),'positive_plans':validation['positive_planning_expected'],'block_requests':validation['safe_stop_expected'],'errors':len(errors)},ensure_ascii=False))

if __name__=='__main__':main()
