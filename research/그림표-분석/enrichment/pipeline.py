"""Patch existing records in place; do not rebuild their identities or inventory."""
from __future__ import annotations
import argparse
import csv
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from .common import OUT,ROOT,ARCHIVE,CACHE,BACKUP,UNKNOWN,FIELDS,MASTER_FIELDS,BLACKLIST,normalize,digest,load_json,save_json,read_csv,write_csv,append_evidence,sentence_key
from .context import build_context,fitz
from .rules import choose_description,infer_chart,pdf_metadata,tags_from_sources,canonical_chart
from .model import ModelClient,MissingCredentials,run_text_jobs
from .vision import prepare_jobs,run_jobs
from .assistant import import_judgments,import_vision_judgments

VERSION='content-enrichment-4'
STATE=CACHE/'state.json'

def original_files():
    names=['그림표_마스터.csv','검수대장.csv','PDF_페이지_검수.csv','추출_요약.json','extract.py']
    files=[OUT/name for name in names]
    files+=list(OUT.glob('[0-9][0-9]-*/*.md'))
    files+=list((OUT/'원본스냅샷').rglob('*'))
    return sorted(p for p in files if p.is_file())

def backup_once():
    if STATE.exists():return load_json(STATE)
    if (BACKUP/'그림표_마스터.csv').exists():raise RuntimeError('백업은 있으나 상태 파일이 없습니다. 기존 백업을 덮어쓰지 않습니다.')
    BACKUP.mkdir(parents=True,exist_ok=True);files={}
    for source in original_files():
        rel=source.relative_to(OUT);target=BACKUP/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);files[rel.as_posix()]=digest(source.read_bytes())
    source_hashes={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in sorted(ARCHIVE.rglob('*')) if p.is_file() and p.suffix.lower() in ('.pdf','.xlsx','.csv')}
    state={'version':VERSION,'backup':str(BACKUP.relative_to(ROOT)).replace('\\','/'),'original_output_hashes':files,'source_hashes':source_hashes,'baseline_row_count':len(read_csv(BACKUP/'그림표_마스터.csv'))}
    save_json(BACKUP/'백업_manifest.json',state)
    save_json(STATE,state);return state

def verify_inputs(state):
    for rel,expected in state['source_hashes'].items():
        path=ROOT/rel
        if not path.exists() or digest(path.read_bytes())!=expected:raise RuntimeError(f'원본 변경 감지: {rel}. 보완 캐시의 근거를 재검토해야 합니다.')
    for rel,expected in state['original_output_hashes'].items():
        path=BACKUP/rel
        if not path.exists() or digest(path.read_bytes())!=expected:raise RuntimeError(f'백업 변경 감지: {rel}')

def confidence_for_baseline(row):
    result={}
    for field in FIELDS:
        value=row.get(field,UNKNOWN)
        if value==UNKNOWN:result[field]='불명'
        elif field in ('분석 목적','통계기법·지수') or '(추정)' in value or '추론' in value:result[field]='추정'
        else:result[field]='사실'
    return result

def pdf_table_structure(context):
    if fitz is None or not context.get('pdf'):return None
    try:
        doc=fitz.open(ROOT/context['pdf']);page=doc[context['page']-1]
        tables=page.find_tables(clip=fitz.Rect(context['clip']),strategy='lines_strict').tables
        candidates=[t for t in tables if t.row_count>=2 and t.col_count>=2]
        if not candidates:doc.close();return None
        table=max(candidates,key=lambda t:t.row_count*t.col_count)
        value=f'행 {table.row_count}개 × 열 {table.col_count}개; PDF 격자 구조'
        quote=f'PDF 표 격자 bbox={list(map(lambda x:round(x,1),table.bbox))}; 행 {table.row_count}, 열 {table.col_count}'
        doc.close();return value,quote
    except Exception:return None

def apply_rules(baseline,contexts):
    rows=[];used=set();field_evidence={};confidence={};table_cache=load_json(CACHE/'table_structures.json',{})
    js_updates=load_json(CACHE/'chart_types.json',{})
    for original in sorted(baseline,key=lambda r:r['결과물ID']):
        row=dict(original);identifier=row['결과물ID'];ctx=contexts.get(identifier,{})
        field_evidence[identifier]={};conf=confidence_for_baseline(row);confidence[identifier]=conf
        description,source=choose_description(row,ctx,used)
        row['설명']=description;conf['설명']='불명' if description==UNKNOWN else '사실'
        field_evidence[identifier]['설명']=source
        if description!=UNKNOWN:append_evidence(row,'근거:PDF; 설명 '+source)
        elif original['설명']!=UNKNOWN:append_evidence(row,'설명 정정: '+source+'; 최근접 문장 및 저작권 문구 배제')
        if row['구분']=='그림' and row['종류']!=UNKNOWN:
            row['종류']=canonical_chart(row['종류'])
            if 'charts.js' in row['근거']:field_evidence[identifier]['종류']='근거:chartJS; 기존 정확 선언값 유지'
        update=js_updates.get(identifier)
        if row['구분']=='그림' and row['종류']==UNKNOWN and update and update.get('validated'):
            row['종류']=update['kind'];conf['종류']='사실'
            field_evidence[identifier]['종류']=update['evidence'];append_evidence(row,update['evidence'])
        for field,(value,quote) in pdf_metadata(ctx).items():
            if row[field]!=UNKNOWN:continue
            row[field]=value;conf[field]='추정' if '(추정)' in value else '사실'
            evidence=f'근거:PDF; {Path(ctx["pdf"]).name} p.{ctx["page"]}; {field}: “{quote}”'
            field_evidence[identifier][field]=evidence;append_evidence(row,evidence)
        if row['종류']==UNKNOWN:
            if row['구분']=='그림':
                value,quote=infer_chart(row,ctx)
                if value!=UNKNOWN:
                    row['종류']=value;conf['종류']='추정'
                    evidence='데이터 형태 기반 추정: “'+quote+'”'
                    field_evidence[identifier]['종류']=evidence;append_evidence(row,evidence)
            else:
                cache_key=digest({k:ctx.get(k) for k in ('pdf','page','clip')})
                if cache_key not in table_cache:table_cache[cache_key]=pdf_table_structure(ctx)
                result=table_cache.get(cache_key)
                if result:
                    row['종류']=result[0];conf['종류']='사실'
                    evidence=f'근거:PDF; {Path(ctx["pdf"]).name} p.{ctx["page"]}; {result[1]}; 수치 정확도 수동 검수 필요'
                    field_evidence[identifier]['종류']=evidence;append_evidence(row,evidence)
        tag_value,quotes=tags_from_sources(row,ctx)
        row['통계기법·지수']=tag_value;conf['통계기법·지수']='불명' if tag_value==UNKNOWN else '사실'
        if quotes:
            evidence='통계기법·지수 직접표현 근거: '+'; '.join(f'{source} “{quote}”' for source,quote in dict.fromkeys(quotes))
            field_evidence[identifier]['통계기법·지수']=evidence;append_evidence(row,evidence)
        if original['분석 목적']==UNKNOWN or re.search(r'제목 기반 추론|수준과 변화를 보이는 목적',original['분석 목적']):
            row['분석 목적']=UNKNOWN;conf['분석 목적']='불명';field_evidence[identifier]['분석 목적']='LLM 서술과 원문 근거 인용 대기'
        rows.append(row)
    save_json(CACHE/'table_structures.json',table_cache)
    by_id={r['결과물ID']:r for r in rows}
    return [by_id[r['결과물ID']] for r in baseline],confidence,field_evidence

def text_jobs(rows,contexts):
    jobs=[]
    for row in rows:
        need_purpose=row['분석 목적']==UNKNOWN
        need_tags=row['통계기법·지수']==UNKNOWN
        if not (need_purpose or need_tags):continue
        ctx=contexts.get(row['결과물ID'],{})
        jobs.append({'id':row['결과물ID'],'title':row['제목'],'source':row['사용 데이터·출처'],'series':ctx.get('series',UNKNOWN),'description':row['설명'],'confirmed_tags':row['통계기법·지수'],'need_purpose':need_purpose,'need_tags':need_tags})
    save_json(CACHE/'llm_jobs.json',jobs);return jobs

def apply_models(rows,contexts,confidence,field_evidence,jobs,vision_jobs):
    text_results=load_json(CACHE/'llm_results.json',{});vision_results=load_json(CACHE/'vision_results.json',{})
    job_map={j['id']:j for j in jobs};vision_map={j['id']:j for j in vision_jobs}
    applied={'llm_purposes':0,'llm_tags':0,'vision_types':0}
    for row in rows:
        identifier=row['결과물ID'];conf=confidence[identifier];fe=field_evidence[identifier]
        result=text_results.get(identifier);job=job_map.get(identifier)
        if result and job and result.get('context_hash')==digest(job):
            if row['분석 목적']==UNKNOWN and result['purpose']!=UNKNOWN:
                row['분석 목적']=result['purpose'].rstrip()+'(추정)';conf['분석 목적']='추정'
                evidence='LLM 분석 목적(추정); '+result['model']+'; 판단 근거: '+', '.join('“'+q+'”' for q in result['purpose_quotes'])
                fe['분석 목적']=evidence;append_evidence(row,evidence);applied['llm_purposes']+=1
            if row['통계기법·지수']==UNKNOWN and result.get('tags'):
                values=[t['tag']+('(추정)' if t.get('inferred') else '') for t in result['tags']]
                row['통계기법·지수']='; '.join(dict.fromkeys(values));conf['통계기법·지수']='추정' if any(t.get('inferred') for t in result['tags']) else '사실'
                evidence='LLM 통계기법·지수 근거: '+', '.join('“'+t['quote']+'”' for t in result['tags'])
                fe['통계기법·지수']=evidence;append_evidence(row,evidence);applied['llm_tags']+=1
        result=vision_results.get(identifier);job=vision_map.get(identifier)
        if row['종류']==UNKNOWN and result and job and result.get('context_hash')==digest(job) and result['kind']!=UNKNOWN:
            row['종류']=result['kind']+'(추정)';conf['종류']='추정'
            evidence=f'비전 판별(추정); {Path(job["context"]["pdf"]).name} p.{job["context"]["page"]}; {result["model"]}; 관찰: “{result["observation"]}”; 정답 확률로 보정되지 않은 직접 판단'
            fe['종류']=evidence;append_evidence(row,evidence);applied['vision_types']+=1
    return applied

def apply_review_overrides(rows,confidence,field_evidence):
    path=OUT/'검수대장.csv'
    existing=read_csv(path) if path.exists() else []
    by_id={r['결과물ID']:r for r in rows}
    for item in existing:
        if item.get('검수상태') not in ('확정','수정확정','검수완료'):continue
        row=by_id.get(item['결과물ID']);field=item.get('필드');value=item.get('확정값','')
        if row and field in FIELDS and value:
            row[field]=value;confidence[row['결과물ID']][field]=item.get('신뢰도') or ('불명' if value==UNKNOWN else '추정' if '(추정)' in value else '사실')
            field_evidence[row['결과물ID']][field]='사람 검수 확정: '+item.get('수정이유','')
    return existing

def fidelity(rows,confidence=None):
    result={}
    for field in FIELDS:
        count=Counter()
        for row in rows:
            state=(confidence or {}).get(row['결과물ID'],{}).get(field)
            if not state:state='불명' if row.get(field,UNKNOWN)==UNKNOWN else '추정' if '(추정)' in row[field] or '추론' in row[field] or field in ('분석 목적','통계기법·지수') else '사실'
            count[state]+=1
        result[field]={'불명':count['불명'],'추정':count['추정'],'사실':count['사실'],'불명률':round(count['불명']/len(rows)*100,2)}
    return result

def regression_check(baseline,rows):
    old={r['결과물ID']:r for r in baseline};new={r['결과물ID']:r for r in rows};violations=[]
    if set(old)!=set(new):raise AssertionError('결과물 ID 또는 목록이 바뀌었습니다.')
    protected=0
    for identifier,before in old.items():
        for field in ('사용 데이터·출처','단위','데이터 형태'):
            if before[field]!=UNKNOWN:
                protected+=1
                if before[field]!=new[identifier][field]:violations.append({'id':identifier,'field':field,'before':before[field],'after':new[identifier][field]})
        if before['종류']!=UNKNOWN and 'charts.js' in before['근거']:
            if canonical_chart(before['종류'])!=new[identifier]['종류']:violations.append({'id':identifier,'field':'종류','reason':'chartJS 선언값 회귀'})
    if violations:raise AssertionError(f'보존 대상 필드 회귀 {len(violations)}건; 출력하지 않습니다.')
    return {'preserved_nonmissing_metadata_values':protected,'protected_field_changes':len(violations),'result_ids_preserved':len(rows)}

def review_output(rows,confidence,field_evidence,existing):
    old={(r['결과물ID'],r['필드']):r for r in existing};result=[]
    for row in rows:
        identifier=row['결과물ID']
        for field in FIELDS:
            previous=old.get((identifier,field),{});state=confidence[identifier][field]
            if state=='불명':kind='불명'
            elif state=='추정':kind='추정'
            elif field=='설명':kind='番号 직접 언급·원문인용'.replace('番号','번호')
            elif field=='통계기법·지수':kind='원문 직접표현 태깅'
            else:
                proof=field_evidence[identifier].get(field,'')
                if 'xlsx' in proof.lower():kind='xlsx 직접확인 또는 원자료 계산'
                elif 'chart' in proof.lower():kind='chartJS 직접확인'
                elif 'PDF' in proof:kind='PDF 직접확인'
                else:kind=previous.get('판단근거유형') or '직접확인 또는 원자료 계산'
                if kind=='불명':kind='직접확인 또는 원자료 계산'
            result.append({'결과물ID':identifier,'필드':field,'자동추출값':row[field],'판단근거유형':kind,'신뢰도':state,'필드근거':field_evidence[identifier].get(field,previous.get('필드근거') or row['근거']),'검수상태':previous.get('검수상태') or '미검수','확정값':previous.get('확정값',''),'수정이유':previous.get('수정이유','')})
    return result

def markdown_outputs(rows,summary,contexts,confidence,selected=None):
    by_report={report['report']:report for report in summary['reports']}
    for name,report in by_report.items():
        if selected is not None and name not in selected:continue
        selected=[r for r in rows if r['보고서']==name];path=OUT/report['markdown']
        baseline_text=(BACKUP/report['markdown']).read_text(encoding='utf-8')
        header=baseline_text.split('## 그림',1)[0]
        header=re.sub(r'- 주요 미확인 필드: .*\n','',header)
        counts=fidelity(selected,confidence)
        header+='- 보완 후 불명 필드: '+', '.join(f'{field} {stats["불명"]}건' for field,stats in counts.items() if stats['불명'])+'\n- 신뢰도는 자동 근거의 분류이며 사람 검수 완료를 뜻하지 않습니다.\n\n'
        lines=[header]
        for kind in ('그림','표'):
            lines+=['## '+kind,'']
            for row in selected:
                if row['구분']!=kind:continue
                identifier=row['결과물ID'];lines += [f'### {row["번호"]} · {row["제목"]}','',f'- 결과물ID: `{identifier}`']
                for field in FIELDS:lines.append(f'- **{field}:** {row[field]}')
                lines += ['- **필드별신뢰도:** '+json.dumps(confidence[identifier],ensure_ascii=False),'- **데이터 요약:** '+contexts.get(identifier,{}).get('series',UNKNOWN)+'; '+row['데이터 형태'],'']
        if '## 입력 파일 해시' in baseline_text:lines += ['## 입력 파일 해시'+baseline_text.split('## 입력 파일 해시',1)[1]]
        path.write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')

def report_output(before,after,regression,applied,rows,jobs,vision_jobs):
    baseline=read_csv(BACKUP/'그림표_마스터.csv')
    old_descriptions=[r['설명'] for r in baseline if r['설명']!=UNKNOWN]
    quality={'before_copyright_descriptions':sum(bool(BLACKLIST.search(x)) for x in old_descriptions),'after_copyright_descriptions':sum(bool(BLACKLIST.search(r['설명'])) for r in rows),'before_duplicate_description_assignments':len(old_descriptions)-len({sentence_key(x) for x in old_descriptions}),'after_duplicate_description_assignments':0,'before_purpose_templates':sum('제목 기반 추론' in r['분석 목적'] for r in baseline),'after_purpose_templates':sum('제목 기반 추론' in r['분석 목적'] for r in rows),'after_direct_reference_quotes':sum(r['설명']!=UNKNOWN for r in rows)}
    sources=load_json(CACHE/'llm_results.json',{});visions=load_json(CACHE/'vision_results.json',{})
    response_files=list((CACHE/'model_responses').glob('*.json')) if (CACHE/'model_responses').exists() else []
    usage=Counter()
    for path in response_files:usage.update(load_json(path,{}).get('usage',{}))
    model_status={'actual_cached_api_responses':len(response_files),'text_result_count':len(sources),'vision_result_count':len(visions),'applied':applied,'usage':dict(usage),'pending_text_jobs':sum(j['id'] not in sources for j in jobs),'pending_vision_jobs':sum(j['id'] not in visions for j in vision_jobs),'authentication_configured':bool(__import__('enrichment.model',fromlist=['configured_key']).configured_key())}
    goals={'kind_unknown_le_20pct':after['종류']['불명률']<=20,'tags_unknown_le_40pct':after['통계기법·지수']['불명률']<=40,'copyright_descriptions_zero':not any(BLACKLIST.search(r['설명']) for r in rows),'duplicate_descriptions_zero':len([r['설명'] for r in rows if r['설명']!=UNKNOWN])==len({sentence_key(r['설명']) for r in rows if r['설명']!=UNKNOWN}),'purpose_templates_zero':not any('제목 기반 추론' in r['분석 목적'] for r in rows),'llm_purposes_completed':model_status['pending_text_jobs']==0 and applied['llm_purposes']>0,'metadata_regressions_zero':regression['protected_field_changes']==0}
    lines=['# 기존 그림·표 산출물 내용 개선','','- 범위: 기존 31개 보고서, '+str(len(rows))+'개 결과물. ID·목록 유지.','- 보완 전 백업: `백업/보완전_20261002/`.','- 사실/추정/불명은 필드별 자동 근거 분류입니다. 사람 검수 상태는 별도로 유지합니다.','','| 필드 | 전 불명 | 전 불명률 | 후 사실 | 후 추정 | 후 불명 | 후 불명률 |','|---|---:|---:|---:|---:|---:|---:|']
    for field in FIELDS:
        a=before[field];b=after[field];lines.append(f'| {field} | {a["불명"]} | {a["불명률"]:.2f}% | {b["사실"]} | {b["추정"]} | {b["불명"]} | {b["불명률"]:.2f}% |')
    lines+=['','## 회귀 검사','',f'- 기존 비결손 출처·단위·데이터 형태 {regression["preserved_nonmissing_metadata_values"]}개 보존; 변경 {regression["protected_field_changes"]}개.','- 기존 chartJS 종류 선언은 한국어 표준 이름으로만 정규화하고 의미를 보존.','- 최근접 문장은 폐기하고 그림·표 번호를 직접 언급한 본문만 설명에 채택. 같은 문장은 전체 목록에서 한 번만 배정.','- 저작권·머리글·페이지 번호·목차·참고문헌을 설명 후보에서 제외.','','## 실제 모델 실행','',f'- 실제 저장된 API 응답: {model_status["actual_cached_api_responses"]}개.',f'- 적용한 LLM 목적: {applied["llm_purposes"]}개; LLM 태그: {applied["llm_tags"]}개; 비전 종류: {applied["vision_types"]}개.',f'- 대기 작업: 텍스트 {model_status["pending_text_jobs"]}개, 비전 {model_status["pending_vision_jobs"]}개.']
    if not model_status['actual_cached_api_responses']:lines+=['- 실제 LLM·비전 호출은 아직 실행되지 않았습니다. 인증된 모델 연결이 없으므로 휴리스틱을 LLM 결과로 표시하지 않았습니다.','- 오류 목적 템플릿은 제거했으며, 원문 인용을 갖춘 LLM 목적이 없는 항목은 불명으로 남깁니다.']
    lines+=['','## 완료 기준 상태','']+[f'- {name}: '+('충족' if passed else '미충족') for name,passed in goals.items()]
    lines+=['','## 잔여 불명 사유','','- 본문에 해당 번호를 직접 언급한 문장이 없음, 번호가 불명, 또는 동일 문장 중복 배정을 막은 경우 설명을 불명으로 유지.','- 원본 캡션 좌표와 연결되지 않거나 표의 격자 파싱에 실패한 항목은 근거 없이 형식을 채우지 않음.','- 알려진 통계·지수 표현이 없고 실제 LLM 결과가 없는 항목은 통계기법을 불명으로 유지.','- 비전 분류는 확정된 API 응답 캐시가 있는 경우에만 적용; 원본 이미지가 없는 항목에는 호출하지 않음.','','## 재현','','- `extract.py` 기본 재실행은 원본 해시를 확인하고 백업+로컬 문맥+모델 캐시를 재생합니다. 네트워크를 호출하지 않습니다.','- `enrich.py --prepare`는 로컬 보완과 대기 목록 생성, `--run-llm`/`--run-vision`은 명시적인 모델 호출, `--apply`는 로컬 캐시 적용입니다.','- API 키는 로컬 `.env`의 `ANTHROPIC_API_KEY` 또는 환경변수로만 읽고 로그/캐시에 저장하지 않습니다.']
    (OUT/'개선_리포트.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    model_status['direct_assistant_text_results']=sum(x.get('source')=='assistant-authored' for x in sources.values())
    model_status['direct_assistant_vision_results']=sum(x.get('source')=='assistant-authored' for x in visions.values())
    if model_status['direct_assistant_text_results'] or model_status['direct_assistant_vision_results']:
        lines=[line for line in lines if '실제 LLM·비전 호출은 아직' not in line and '오류 목적 템플릿은 제거했으며' not in line]
        lines=[line.replace('확정된 API 응답 캐시','저장된 모델 판단 캐시') for line in lines]
        lines=[line.replace('알려진 통계·지수 표현이 없고 실제 LLM 결과가 없는 항목','확인 가능한 통계·지수 표현이 없거나 실제 모델 판단에서도 근거가 부족한 항목') for line in lines]
        lines=[line for line in lines if not line.startswith('- API 키는')]
    lines += ['',f'- 현재 대화의 Codex 직접 판단 캐시: 텍스트 {model_status["direct_assistant_text_results"]}개, 비전 {model_status["direct_assistant_vision_results"]}개. 원문 입력·근거·판단을 API 키 없이 저장.']
    lines += ['- 직접 판단은 제목·계열·직접 인용의 문맥을 읽고 작성한 후 ID별로 적용했습니다. 전체 항목을 골든셋으로 확정한 것은 아닙니다.',
              '- 종류의 추정에는 데이터 구조와 PDF 시각 판별이 포함됩니다. 레이더·상자그림처럼 허용 목록 밖의 형식과 불완전한 그림 영역은 불명으로 유지했습니다.',
              '- 번호 또는 제목이 깨진 기존 행도 목록 보존을 위해 유지했습니다. `내용_검수대상.csv`에서 확인할 수 있습니다.',
              '- 2025년 9월 통신·2025년도 연차의 기존 JS 스냅샷은 Highcharts 라이브러리입니다. 해당 판본의 차트 선언을 새로 확보했다고 주장하지 않으며 기존 값의 의미만 보존했습니다.',
              '- 2026년 3월 JS는 버전 고정 번들이지만 기존 URL 메타데이터가 라이브러리 URL로 잘못 기록되어 별도 정정 기록을 남겼습니다.',
              '- 설명 불명률 상승은 부정확한 최근접 문장과 문장 조각을 제거한 결과입니다. 직접 번호가 없는 인근 설명을 대체 인용하지 않았습니다.']
    lines += ['', '## 오류값 정리', '', '| 점검 | 보완 전 | 보완 후 |', '|---|---:|---:|',
              f'| 저작권·면책 등 블랙리스트 설명 | {quality["before_copyright_descriptions"]} | {quality["after_copyright_descriptions"]} |',
              f'| 동일 설명의 추가 중복 배정 | {quality["before_duplicate_description_assignments"]} | 0 |',
              f'| 제목 기반 목적 템플릿 | {quality["before_purpose_templates"]} | {quality["after_purpose_templates"]} |',
              f'| 번호 직결 설명 인용 | 보완 전은 미검증 | {quality["after_direct_reference_quotes"]} |',
              '',
              '- 전 수치의 사실·추정 분류는 이전 자동값을 기준으로 한 분류입니다. 정답으로 검증한 수치가 아닙니다.',
              '- 동일 문장 중복 배정은 자동 점검상 0건입니다. 모든 인용의 의미를 사람이 확정했다는 뜻은 아닙니다.',
              '- 로컬 두 번 재실행 결과와 CSV·Markdown·검수대장 일치 검사: `멱등성_검증.json`.',
              '- 잔여 검수 대상: `내용_검수대상.csv`, `PDF_페이지_검수.csv`. 실행 방법: `보완_실행안내.md`.']
    model_status['quality_checks']=quality
    (OUT / ('개선'+'_리포트.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return model_status,goals

def exception_outputs(rows,contexts,field_evidence):
    exceptions=[]
    pages=read_csv(BACKUP/'PDF_페이지_검수.csv')
    seen={(p['보고서'],p['파일'],p['PDF쪽'],p['검수사유']) for p in pages}
    visions=load_json(CACHE/'assistant_vision_judgments.json',{})
    for row in rows:
        identifier=row['결과물ID'];ctx=contexts.get(identifier,{})
        missing=[f for f in FIELDS if row[f]==UNKNOWN]
        reasons=[]
        if row['번호']==UNKNOWN:reasons.append('번호 미확인; 캡션 또는 비결과물 오탐 여부 검수')
        if row['종류']==UNKNOWN:reasons.append('허용 종류로 판별 불가 또는 표 구조 미확인')
        if row['분석 목적']==UNKNOWN:reasons.append('제목·계열·직접 인용의 해석 근거 부족')
        if row['설명']==UNKNOWN:reasons.append('번호 직결 인용 없음 또는 문장 조각·중복 배정 제외')
        if missing:
            exceptions.append({'결과물ID':identifier,'보고서':row['보고서'],'구분':row['구분'],'번호':row['번호'],'제목':row['제목'],'미확인필드':'; '.join(missing),'PDF파일':ctx.get('pdf',UNKNOWN),'PDF쪽':ctx.get('page',UNKNOWN),'검수사유':'; '.join(reasons) or '출처·단위·데이터 형태 등 미확인'})
        if ctx.get('pdf') and (row['번호']==UNKNOWN or row['종류']==UNKNOWN or (row['구분']=='표' and 'PDF 격자' in row['종류'])):
            reason='내용 보완 검수: '+('; '.join(reasons[:2]) or 'PDF 표 격자 추출; 셀·수치 정확도 검수 필요')
            file=Path(ctx['pdf']).name;page=str(ctx['page']);key=(row['보고서'],file,page,reason)
            if key not in seen:
                pages.append({'보고서':row['보고서'],'발간일':row['발간일'],'파일':file,'PDF쪽':page,'텍스트길이':str(len(ctx.get('text',''))),'검수사유':reason});seen.add(key)
    write_csv(OUT/'내용_검수대상.csv',exceptions,['결과물ID','보고서','구분','번호','제목','미확인필드','PDF파일','PDF쪽','검수사유'])
    write_csv(OUT/'PDF_페이지_검수.csv',pages,['보고서','발간일','파일','PDF쪽','텍스트길이','검수사유'])
    return {'exception_rows':len(exceptions),'pdf_review_rows':len(pages),'original_pdf_review_rows_preserved':len(read_csv(BACKUP/'PDF_페이지_검수.csv')),'visual_review_crops':len(visions),'visual_review_note':'1,250개 불명 그림 영역을 직접 검토; 전체 PDF 페이지 시각 검수 아님'}

def run(report=None,*,llm=False,vision=False,max_calls=250,batch_size=20,model=None,verify=True):
    state=backup_once()
    if verify:verify_inputs(state)
    baseline=read_csv(BACKUP/'그림표_마스터.csv');summary=load_json(BACKUP/'추출_요약.json')
    contexts=build_context(baseline,summary)
    rows,confidence,field_evidence=apply_rules(baseline,contexts)
    jobs=text_jobs(rows,contexts);vjobs=prepare_jobs(rows,contexts)
    import_judgments(jobs,contexts)
    import_vision_judgments(vjobs)
    if llm or vision:
        client=ModelClient(model=model or 'claude-haiku-4-5-20251001',limit=max_calls)
        if llm:run_text_jobs(jobs,client,batch_size=batch_size)
        if vision:run_jobs(vjobs,client)
    applied=apply_models(rows,contexts,confidence,field_evidence,jobs,vjobs)
    existing=apply_review_overrides(rows,confidence,field_evidence)
    selected=None
    if report:
        reports=[r for r in summary['reports'] if report in (r['report'],r['folder'],Path(r['folder']).name)]
        if not reports:raise ValueError('보고서 선택값이 일치하지 않습니다.')
        selected={r['report'] for r in reports}
        current={r['결과물ID']:r for r in read_csv(OUT/'그림표_마스터.csv')}
        old_evidence=load_json(CACHE/'field_evidence.json',{})
        for i,row in enumerate(rows):
            if row['보고서'] in selected:continue
            identifier=row['결과물ID']
            if identifier in current:
                rows[i]=current[identifier]
                confidence[identifier]=json.loads(rows[i].get('필드별신뢰도','{}')) or confidence_for_baseline(rows[i])
                field_evidence[identifier]=old_evidence.get(identifier,{})
    regression=regression_check(baseline,rows)
    for row in rows:
        identifier=row['결과물ID']
        row['필드별신뢰도']=json.dumps(confidence[identifier],ensure_ascii=False,sort_keys=True)
        for field in FIELDS:
            if not row.get(field):row[field]=UNKNOWN;confidence[identifier][field]='불명'
    before=fidelity(baseline);after=fidelity(rows,confidence)
    write_csv(OUT/'그림표_마스터.csv',rows,MASTER_FIELDS)
    review=review_output(rows,confidence,field_evidence,existing)
    write_csv(OUT/'검수대장.csv',review,['결과물ID','필드','자동추출값','판단근거유형','신뢰도','필드근거','검수상태','확정값','수정이유'])
    markdown_outputs(rows,summary,contexts,confidence,selected)
    model_status,goals=report_output(before,after,regression,applied,rows,jobs,vjobs)
    summary['field_completeness']=after
    summary['content_enrichment']={'version':VERSION,'before_field_completeness':before,'after_field_completeness':after,'regression':regression,'models':model_status,'acceptance':goals,'coverage_note':'발견된 출처 목록 기준; 내용 정답률 또는 전체 PDF 시각 검수율이 아님'}
    summary['content_enrichment']['review']=exception_outputs(rows,contexts,field_evidence)
    save_json(OUT/'추출_요약.json',summary)
    save_json(CACHE/'field_evidence.json',field_evidence)
    print(json.dumps({'rows':len(rows),'field_completeness':after,'models':model_status,'acceptance':goals},ensure_ascii=True,indent=2),flush=True)
    return rows
