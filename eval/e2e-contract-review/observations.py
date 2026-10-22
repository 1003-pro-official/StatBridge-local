"""Observe actual report responses without receiving expected source labels."""
import copy


def report_observation(series, answer):
    observed=[]
    for item in series:
        identity=item.get('sourceIdentity')
        if not isinstance(identity,dict) or not all(k in identity for k in
                ('table_id','item_id','classifications','frequency')):
            raise ValueError('actual sourceIdentity is required; expected labels are not evidence')
        observed.append({**copy.deepcopy(identity),'unit':item.get('unit'),
            'points':[{'period':p['date'],'value':p.get('value')} for p in item.get('points',[])]})
    text=answer.get('answer') or answer.get('markdown') or answer.get('text')
    if not text:
        paragraphs=answer.get('paragraphs') or []
        if not isinstance(paragraphs,list) or not all(isinstance(p,str) for p in paragraphs):
            raise ValueError('unsupported report paragraphs')
        text='\n\n'.join(paragraphs)
    if not isinstance(text,str) or not text.strip():
        raise ValueError('no actual report text')
    return {'series':observed,'report':{'text':text,'method':answer.get('method'),
            'claims':copy.deepcopy(answer.get('claims',[])),
            'sources':copy.deepcopy(answer.get('sources') or answer.get('facts') or [])}}
