"""Import judgments authored by the current Codex session, without an API key.

The bank contains explicit judgments for reviewed title groups, not generated
keyword templates. This module only expands those reviewed groups to stable IDs.
"""
from __future__ import annotations
import re
from .common import CACHE,UNKNOWN,normalize,compact,digest,save_json,load_json

def title_key(title):
    return compact(re.sub(r'\s*\d+\)','',normalize(title)))

def prepare_groups(jobs,contexts):
    groups={}
    for job in jobs:
        key=title_key(job['title'])
        groups.setdefault(key,[]).append(job)
    inputs=[]
    for index,(title,members) in enumerate(groups.items(),1):
        informative=sorted(members,key=lambda j:(j['description']!=UNKNOWN,j['series']!=UNKNOWN,len(j['description'])),reverse=True)
        reps=[]
        for j in informative[:2]:
            reps.append({k:j.get(k) for k in ('title','source','series','description')})
        inputs.append({'group':f'G{index:04d}','title':members[0]['title'],'key':title,'count':len(members),'examples':reps,'ids':[j['id'] for j in members]})
    save_json(CACHE/'assistant_group_inputs.json',inputs);return inputs

def import_judgments(jobs,contexts):
    groups=prepare_groups(jobs,contexts)
    files=sorted((CACHE/'assistant_judgments').glob('*.json')) if (CACHE/'assistant_judgments').exists() else []
    bank={}
    for path in files:
        for judgment in load_json(path,[]):
            if isinstance(judgment,list):
                item={'group':judgment[0],'purpose':judgment[1],'tags':judgment[2] if len(judgment)>2 else []}
            else:item=judgment
            bank[item['group']]=item
    results=load_json(CACHE/'llm_results.json',{});by_id={j['id']:j for j in jobs};accepted=0
    for group in groups:
        item=bank.get(group['group'])
        if not item:continue
        purpose=item.get('purpose',UNKNOWN)
        if not isinstance(purpose,str) or '제목 기반 추론' in purpose or '수준과 변화' in purpose:raise ValueError('유효하지 않은 Codex 목적 판단: '+group['group'])
        for identifier in group['ids']:
            job=by_id[identifier]
            # Specific title text is part of the actual reviewed model input.
            quotes=[job['title']] if purpose!=UNKNOWN and job['title']!=UNKNOWN else []
            if quotes and job.get('series') not in (None,UNKNOWN,''):
                quotes.append(job['series'])
            if purpose!=UNKNOWN and not quotes:continue
            tag_values=[]
            for tag in item.get('tags',[]):
                if isinstance(tag,str):tag={'tag':tag,'quote':job['title'],'inferred':True}
                source='\n'.join(str(job.get(k,'')) for k in ('title','source','series','description'))
                if tag.get('quote') and tag['quote'] in source:tag_values.append(tag)
            results[identifier]={'purpose':purpose,'purpose_quotes':quotes,'tags':tag_values,'context_hash':digest(job),'response_hash':digest(item),'model':'Codex 현재 대화 직접 판단','source':'assistant-authored','reviewed_group':group['group'],'judgment_file_hashes':[digest(p.read_bytes()) for p in files]}
            accepted+=1
    save_json(CACHE/'llm_results.json',results)
    return accepted,len(groups),len(bank)

def import_vision_judgments(jobs):
    bank=load_json(CACHE/'assistant_vision_judgments.json',{})
    results=load_json(CACHE/'vision_results.json',{})
    for job in jobs:
        result=bank.get(job['id'])
        if not result:continue
        if result.get('context_hash')!=digest(job):continue
        results[job['id']]={**result,'model':'Codex 현재 대화 비전 직접 판별','source':'assistant-authored'}
    save_json(CACHE/'vision_results.json',results)
