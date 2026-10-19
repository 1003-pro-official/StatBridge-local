"""Independent Decimal/calendar oracle. Does not import the production executor.

All generated observations are explicitly synthetic. Catalog IDs are not observations.
"""
from decimal import Decimal, InvalidOperation, localcontext

FREQUENCIES={'M':12,'Q':4,'S':2,'Y':1}


def ordinal(period,freq):
    n=FREQUENCIES[freq]
    return int(period[:4])*n+(int(period[4:]) if n>1 else 1)-1


def shift(period,freq,amount):
    n=FREQUENCIES[freq];value=ordinal(period,freq)+amount
    return str(value//n).zfill(4)+(str(value%n+1).zfill(2) if n>1 else '')


def periods(first,last,freq):
    return [shift(first,freq,i) for i in range(ordinal(last,freq)-ordinal(first,freq)+1)]


def synthetic_data(case,p):
    result={};seed=case['fixture']['seed']
    for j,source in enumerate(p['sources']):
        freq=source['frequency'];first=shift(p['start_period'],freq,-36);last=shift(p['end_period'],freq,12)
        values={period:Decimal(100+seed%17+j*13)+Decimal(i)*Decimal('0.17')+Decimal(i%7)*Decimal('0.03')
                for i,period in enumerate(periods(first,last,freq))}
        scenario=case['scenario']
        if scenario=='missing_start':values={k:v for k,v in values.items() if k>p['start_period']}
        if scenario=='missing_middle':values.pop(shift(p['start_period'],freq,1),None)
        if scenario=='no_history':values={k:v for k,v in values.items() if k>=p['start_period']}
        if scenario=='zero':values={k:Decimal(0) for k in values}
        if scenario in {'negative_log','negative_power'}:values={k:-v for k,v in values.items()}
        if scenario=='no_values':values={k:None for k in values}
        result[source['alias']]={'values':values,'unit':'2020=100','frequency':freq,'source_ids':[source['alias']]}
    return result


def reference_unit(op,units,exponent=None):
    # This is the author-specified dimensional contract, separate from production.
    def delta(unit):return '%p' if unit in {'%','연%','연리%','%p'} else '포인트' if '=100' in unit.replace('＝','=') or unit=='지수' else unit
    if op in {'add','subtract'}:
        if len(set(units))!=1 or not units[0]:raise ValueError('incompatible dimensions')
        return delta(units[0]) if op=='subtract' else units[0]
    if op in {'pct_change','yoy_pct'}:
        if delta(units[0])=='%p':raise ValueError('rate change ambiguity')
        return '%'
    if op=='rebase_100':return '지수(기준=100)'
    if op=='divide':return '배' if units[0]==units[1] else f'({units[0]})/({units[1]})'
    if op=='multiply':return f'({units[0]})·({units[1]})'
    if op=='inverse':return f'1/({units[0]})'
    if op=='power':return f'({units[0]})^{exponent}'
    if op=='log':
        if units[0] not in {'배','지수','지수(기준=100)','1','무차원'} and '=100' not in units[0].replace('＝','='):raise ValueError('dimensioned log')
        return '로그'
    return delta(units[0]) if op=='difference' else units[0]


def evaluate(p,raw):
    cache={};nodes={n['id']:n for n in p['nodes']};freq=p['sources'][0]['frequency']
    units={alias:item['unit'] for alias,item in raw.items()}
    for n in p['nodes']:units[n['id']]=reference_unit(n['operator'],[units[a] for a in n['inputs']],n.get('exponent'))
    def value(name,t):
        key=(name,t)
        if key in cache:return cache[key]
        if name in raw:return raw[name]['values'].get(t)
        n=nodes[name];op=n['operator'];refs=n['inputs'];x=value(refs[0],t);out=None
        try:
            with localcontext() as ctx:
                ctx.prec=50
                if op=='lag':out=value(refs[0],shift(t,freq,-n['lag']))
                elif op=='cumulative_sum':
                    if t>=p['start_period']:
                        points=[value(refs[0],s) for s in periods(p['start_period'],t,freq)]
                        if all(v is not None for v in points):out=sum(points,Decimal(0))
                elif op=='rolling_mean':
                    points=[value(refs[0],shift(t,freq,-k)) for k in range(n['window'])]
                    if all(v is not None for v in points):out=sum(points,Decimal(0))/Decimal(n['window'])
                elif x is not None:
                    if op in {'add','subtract','multiply','divide'}:
                        y=value(refs[1],t)
                        if y is not None:
                            if op=='add':out=x+y
                            elif op=='subtract':out=x-y
                            elif op=='multiply':out=x*y
                            else:out=x/y
                    elif op in {'pct_change','yoy_pct','difference'}:
                        prior=value(refs[0],shift(t,freq,-(FREQUENCIES[freq] if op=='yoy_pct' else n['lag'])))
                        if prior is not None:out=x-prior if op=='difference' else Decimal(100)*(x-prior)/prior
                    elif op=='rebase_100':
                        base=value(refs[0],n['base_period'])
                        if base is not None:out=Decimal(100)*x/base
                    elif op=='inverse':out=Decimal(1)/x
                    elif op=='log':out=x.ln()
                    elif op=='power':out=x**Decimal(str(n['exponent']))
        except (InvalidOperation,ZeroDivisionError,OverflowError):out=None
        if out is not None and not out.is_finite():out=None
        cache[key]=out
        return out
    expected={}
    for output in p['outputs']:
        expected[output['node']]={'unit':units[output['node']], 'values':{
            t:value(output['node'],t) for t in periods(p['start_period'],p['end_period'],freq)}}
    return expected


def compare(expected,computed,atol=Decimal('1e-9'),rtol=Decimal('1e-11')):
    errors=[];checked=0;largest=Decimal(0)
    for name,item in expected.items():
        actual=computed['series'][name]
        if actual.unit!=item['unit']:errors.append(f'unit {name}: {actual.unit} != {item["unit"]}')
        for t,want in item['values'].items():
            got=actual.values.get(t)
            if want is None:
                if got is not None:errors.append(f'{name}/{t}: expected missing, got value')
                continue
            checked+=1
            if got is None:errors.append(f'{name}/{t}: missing computed value');continue
            error=abs(Decimal(str(got))-want);largest=max(largest,error)
            if error>atol+rtol*abs(want):errors.append(f'{name}/{t}: numerical mismatch')
    return {'passed':not errors,'errors':errors[:20],'checked_points':checked,'max_absolute_error':str(largest)}


def canonical_formula(p):
    """Symbolic equivalence for these authored arithmetic families; not expert economics."""
    source={s['alias']:('source',s['table_id'],s['item_id'],tuple(sorted(s['classifications'].items())),s['frequency']) for s in p['sources']}
    for n in p['nodes']:
        op=n['operator'];args=[source[x] for x in n['inputs']]
        if op=='yoy_pct':op='pct_change';parameters=(('lag',FREQUENCIES[p['sources'][0]['frequency']]),)
        else:parameters=tuple(sorted((k,v) for k,v in n.items() if k not in {'id','operator','inputs'} and v is not None))
        if op in {'add','multiply'}:args.sort(key=repr)
        source[n['id']]=(op,tuple(args),parameters)
    return sorted((source[out['node']] for out in p['outputs']),key=repr)
