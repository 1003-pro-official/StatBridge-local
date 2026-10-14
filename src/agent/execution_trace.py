"""Public execution evidence: actual node paths, never provider prompts or keys."""
from datetime import datetime, timezone
from uuid import uuid4

def run_trace(kind, engine, path, *, stage='complete', revision=None, changes=()):
    return {'id':uuid4().hex,'kind':kind,'engine':engine,'path':[str(node) for node in path],
            'stage':stage,'revision':revision,'time':datetime.now(timezone.utc).isoformat(),
            'changes':[str(value) for value in changes]}

def result_trace(result, kind, previous_path=()):
    trace=result.get('orchestration') or {}
    path=list(trace.get('path') or [])
    prefix=list(previous_path)
    if prefix and path[:len(prefix)]==prefix:path=path[len(prefix):]
    if not path:return None
    return run_trace(kind,trace.get('engine') or 'unknown',path,stage=trace.get('stage') or 'complete')

def initial_traces(results, rendered, merged):
    runs=[trace for result in results if (trace:=result_trace(result,'query'))]
    trace=result_trace(rendered,'output',(merged.get('orchestration') or {}).get('path') or [])
    if trace:runs.append(trace)
    return runs

def edit_trace(payload, output, *, used_edit_graph=False, period_update=False):
    if used_edit_graph:
        path=(output.get('editAgent') or {}).get('path') or []
        engine='langgraph'
    else:
        engine='direct'
        action=getattr(payload,'action','edit')
        operation='restore_initial' if getattr(payload,'restore_initial',False) else 'restore_document' if getattr(payload,'document',None) is not None else 'restore_property' if getattr(payload,'undo_property',None) else action if action in {'undo','redo'} else 'apply_validated_settings'
        path=['validate_revision',*(['execute_statistics'] if period_update else []),operation,'render_output']
    return run_trace('edit',engine,path,revision=output.get('editVersion'),changes=output.get('editChanges') or [])
