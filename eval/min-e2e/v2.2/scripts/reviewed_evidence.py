"""Evidence bindings for reviewed evaluation. Input text is never authority."""
from pathlib import Path
import hashlib,json,math
def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True)
def contract_sha(case):return sha(canonical({k:v for k,v in case.items() if k!='approval'}).encode())
def capture(ref,case_id,run_id,root,origins):
    if not isinstance(ref,dict) or root is None or not run_id:return None,'capture_missing'
    base=Path(root).resolve();path=(base/str(ref.get('path',''))).resolve()
    if not path.is_relative_to(base) or not path.is_file():return None,'capture_file_missing_or_outside_root'
    if any(part in {'oracle','fixtures','baseline_reference','reports'} for part in path.relative_to(base).parts):return None,'oracle_or_report_is_not_run_evidence'
    data=path.read_bytes()
    if sha(data)!=ref.get('sha256'):return None,'capture_hash_mismatch'
    try:d=json.loads(data)
    except (ValueError,UnicodeError):return None,'capture_not_json'
    if d.get('case_id')!=case_id or d.get('run_id')!=run_id:return None,'capture_wrong_case_or_run'
    if d.get('origin') not in origins:return None,'capture_origin_not_allowed'
    if not d.get('captured_at') or 'payload' not in d:return None,'capture_metadata_missing'
    return d,None
def finite_positive(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>0
def lookup(data,pointer):
    if not isinstance(pointer,str) or not pointer.startswith('/payload/'):raise ValueError('Select captured payload, never wrapper or question')
    result=data
    for part in pointer.split('/')[1:]:
        key=part.replace('~1','/').replace('~0','~')
        if key.lower() in {'summary','explanation','rationale','generated_text','response_text','user_input','query','gold','reference_answer'}:raise ValueError('generated text or oracle is not evidence')
        result=result[int(key)] if isinstance(result,list) else result[key]
    return result
