import re,json,html,io,base64,decimal,math,textwrap
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
D=decimal.Decimal
matplotlib.rcParams['font.family']='Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus']=False
root=Path(__file__).resolve().parent
out=root/'reference.regenerated.html'
text=(root/'answers.md').read_text(encoding='utf-8')
data=json.loads((root/'observations.json').read_text(encoding='utf-8'))
bykey={(s['table'],s['item'],s['frequency'],tuple(sorted(s['classification'].items()))):s for s in data}
titles=['M2 평잔·원계열 총액','가계대출 신규취급액 금리','저축성수신 신규취급액 금리','제조업 중소기업 대출잔액','부산 가계대출 말잔','실질 GDP · 계절조정','명목 GDP · 원계열','경상수지 · 원계열','대중국 경상수지','대외금융자산 총액','수입물가지수 · 원화 기준','순상품교역조건지수','가계대출 금리 · 신규취급액과 잔액','가계대출 금리와 저축성수신 금리','수출금액지수와 수출물량지수','M2 평잔·원계열과 말잔·계절조정','현금 발행 및 예수금 · 잔액과 거래','수입물가지수와 순상품교역조건지수','서울·부산 가계대출 말잔','전체·대중국 경상수지','M2 평잔·원계열 전년동월 증가율','M2 말잔·계절조정 전년동월 증가율','가계대출 신규취급액 금리 전월 차이','가계대출 잔액 금리 전월 차이','저축성수신 금리 전월 차이','제조업 중소기업 대출 전년동기 증가율','부산 가계대출 전년동월 증가율','실질·계절조정 GDP 전년동기 증가율','명목 GDP 전년 대비 증가율','경상수지 전월 증감액','대중국 경상수지 전년 증감액','대외금융자산 전년동기 증가율','원화 기준 수입물가 전년동월 증가율','달러 기준 수출물가 전년동월 증가율','수출금액지수 전년동월 증가율','수출물량지수 전년동월 증가율','순상품교역조건지수 전년동월 증가율','현금 발행·예수금 잔액 전년 증가율','가계대출과 저축성수신 금리 차이','가계대출 신규취급액·잔액 금리 차이','서울 대비 부산 가계대출 잔액 비율','수출금액·물량 전년동월 증가율','M2 평잔·원계열 수준과 전년동월 증가율','제조업 중소기업 대출잔액과 증가율','실질·계절조정 GDP와 전년동기 증가율','명목 GDP와 전년 대비 증가율','대외금융자산과 전년동기 증가율','수출금액지수와 전년동월 증가율','명목 GDP 재기준화 · 2015년=100','실질 GDP 재기준화 · 2019년 1분기=100']
assert len(titles)==50
sections=[]; checked=0; problems=[]
def pp(v):
 if v is None:return '미확인'
 if isinstance(v,D):
  return format(v.quantize(D('0.000001'),rounding=decimal.ROUND_HALF_UP),'f').rstrip('0').rstrip('.') or '0'
 return str(v)
def display_period(t,f):
 return t[:4]+'Q'+str(int(t[4:])) if f=='Q' else t
def prior(t,f,offset):
 y=int(t[:4]); z=int(t[4:]) if f!='Y' else 1
 if f=='Y': return str(y-offset)
 size=12 if f=='M' else 4; n=y*size+z-1-offset; return f'{n//size:04}{n%size+1:02}'
def periods(start,end,f):
 if f=='Y':return [str(y) for y in range(start,end+1)]
 size=12 if f=='M' else 4
 return [f'{y}{p:02}' for y in range(start,end+1) for p in range(1,size+1)]
for part in text.split('\n## ')[1:]:
 lines=part.splitlines(); ident=lines[0].split()[0]; num=int(ident[-2:]); query=next(x[len('**질의:** '):] for x in lines if x.startswith('**질의:**'))
 years=re.findall(r'(\d{4})년',query); y0,y1=int(years[0]),int(years[1]); freq='M' if '월별' in query else ('Q' if '분기별' in query else 'Y'); ts=periods(y0,y1,freq)
 sources=[]
 for line in lines:
  if not line.startswith('- **원천'):continue
  table,item=re.search(r'\((DT_\w+)\); 항목 (\w+)',line).groups(); cla=dict(re.findall(r'(objL\d)=[^;]*\(([0-9][^)]*)\)',line)); s=bykey[(table,item,freq,tuple(sorted(cla.items())))]; rows=s['rows']; vals={r['PRD_DE']:D(r['DT']) for r in rows}; unit=rows[0].get('UNIT_NM',''); name=line.split('** ',1)[1].split('; 항목',1)[0]
  if not all(t in vals for t in ts): problems.append((ident,table,'requested values absent',len([t for t in ts if t not in vals])))
  labels=[rows[0].get('C1_NM',''),rows[0].get('C2_NM',''),rows[0].get('C3_NM','')]; pretty=' · '.join(x for x in labels if x) or rows[0].get('TBL_NM',table); sources.append((name,table,unit,vals,pretty))
 v=[s[3] for s in sources]; heads=['시점']; records=[]; chart=[]; chartunits=[]
 if num<=20:
  heads += [f'계열{i+1}: {s[0]} ({s[2]})' for i,s in enumerate(sources)]
  for t in ts:records.append([t]+[x.get(t) for x in v])
  for i,s in enumerate(sources):chart.append([s[3].get(t) for t in ts]); chartunits.append(s[2])
 elif num<=38 or 43<=num<=48:
  diff=num in (23,24,25,30,31); offset=1 if diff else (12 if freq=='M' else 4 if freq=='Q' else 1); unit=('%p' if num in (23,24,25) else sources[0][2] if diff else '%')
  heads += [f'원자료 ({sources[0][2]})','비교시점','비교시점 원자료',f'계산값 ({unit})']; series=[]
  for t in ts:
   prev=prior(t,freq,offset); a=v[0].get(t); b=v[0].get(prev)
   if a is None or b is None:problems.append((ident,sources[0][1],'prior missing',prev)); result=None
   elif not diff and b==0: result=None; problems.append((ident,sources[0][1],'zero denominator',prev))
   else:
    result=a-b if diff else (a/b-1)*100
    check=(float(a)-float(b)) if diff else (float(a)/float(b)-1)*100
    assert math.isclose(float(result),check,rel_tol=1e-11,abs_tol=1e-9)
   records.append([t,a,prev,b,result]);series.append(result)
  chart=([[v[0].get(t) for t in ts],series] if num>=43 else [series]);chartunits=([sources[0][2],unit] if num>=43 else [unit])
 elif 39<=num<=40:
  unit='%p'; heads += [f'계열1 ({sources[0][2]})',f'계열2 ({sources[1][2]})',f'차이 ({unit})',f'전월 차이 ({unit})',f'차이 변화 ({unit})']; gaps=[]
  for t in ts:
   prev=prior(t,freq,1); a,b=v[0].get(t),v[1].get(t); pa,pb=v[0].get(prev),v[1].get(prev)
   if any(x is None for x in (a,b,pa,pb)):problems.append((ident,'spread','missing',t));records.append([t,a,b,None,None,None]);gaps.append(None);continue
   gap=a-b; pgap=pa-pb; change=gap-pgap
   assert math.isclose(float(change),(float(a)-float(b))-(float(pa)-float(pb)),rel_tol=1e-11,abs_tol=1e-8)
   records.append([t,a,b,gap,pgap,change]);gaps.append(gap)
  chart=[gaps];chartunits=[unit]
 elif num==41:
  heads += ['부산 잔액 (십억원)','서울 잔액 (십억원)','전월 비율 (%)','부산/서울 비율 (%)','비율 변화 (%p)']; ratios=[]
  for t in ts:
   prev=prior(t,freq,1); b,s0=v[0].get(t),v[1].get(t); pb,ps=v[0].get(prev),v[1].get(prev)
   if any(z is None for z in (b,s0,pb,ps)) or not s0 or not ps: problems.append((ident,'ratio missing or zero',t));continue
   rat=b/s0*100; prev_rat=pb/ps*100; delta=rat-prev_rat
   assert math.isclose(float(delta),float(b)/float(s0)*100-float(pb)/float(ps)*100,abs_tol=1e-9)
   records.append([t,b,s0,prev_rat,rat,delta]);ratios.append(rat)
  chart=[ratios];chartunits=['%']
 elif num==42:
  heads += ['수출금액지수 (2020=100)','전년 동월 금액지수','수출물량지수 (2020=100)','전년 동월 물량지수','금액 증가율 (%)','물량 증가율 (%)','증가율 차이 (%p)']; first=[];second=[]
  for t in ts:
   prev=prior(t,freq,12); a,b=v[0].get(t),v[1].get(t); pa,pb=v[0].get(prev),v[1].get(prev)
   if any(z is None for z in (a,b,pa,pb)) or not pa or not pb:problems.append((ident,'year comparison missing or zero',t));continue
   va=(a/pa-1)*100;vb=(b/pb-1)*100;gap=va-vb
   assert math.isclose(float(gap),(float(a)/float(pa)-float(b)/float(pb))*100,abs_tol=1e-9)
   records.append([t,a,pa,b,pb,va,vb,gap]);first.append(va);second.append(vb)
  chart=[first,second];chartunits=['%','%']
 else:
  baseline=ts[0]; base=v[0].get(baseline); heads += [f'원자료 ({sources[0][2]})','기준시점 원자료','재기준화 지수 (기준=100)','기준 대비 변화율 (%)'];reb=[]
  for t in ts:
   a=v[0].get(t)
   if a is None or not base:problems.append((ident,'rebase','missing',t));records.append([t,a,base,None,None]);reb.append(None);continue
   val=a/base*100; rate=val-100
   assert math.isclose(float(val),float(a)/float(base)*100,rel_tol=1e-11,abs_tol=1e-8)
   records.append([t,a,base,val,rate]);reb.append(val)
  chart=[reb];chartunits=['기준=100']
 checked+=len(records)
 # separate panels preserve independent scales; indexed unit may differ despite identical descriptions
 panels=2 if len(chart)==2 and (chartunits[0]!=chartunits[1] or num>=43 or num in (17,19)) else 1
 fig,axes=plt.subplots(panels,1,figsize=(10,3.3*panels),squeeze=False,layout='constrained'); axes=axes[:,0]
 for i,ys in enumerate(chart):
  ax=axes[i] if panels==2 else axes[0]; label=('계열 '+str(i+1) if num<=20 else '원자료' if len(chart)==2 and i==0 else '계산 결과')
  if num<=12: label=sources[i][4]
  if 21<=num<=38: label=('전기 대비 변화폭' if num in (23,24,25) else '전기 대비 증감액' if num in (30,31) else '전년 동기 대비 증가율')
  if 39<=num<=40: label='금리 차이'
  if 43<=num<=48: label=(sources[0][4] if i==0 else '전년 동기 대비 증가율')
  if num in (49,50): label='기준 시점 대비 지수'
  if num in {13,14,15,16,17,18,19,20}:
   label={13:['신규취급액 금리','잔액 금리'],14:['가계대출 금리','저축성수신 금리'],15:['수출금액지수','수출물량지수'],16:['평잔 원계열','말잔 계절조정'],17:['잔액','거래'],18:['수입물가지수','순상품교역조건지수'],19:['서울','부산'],20:['전체 경상수지','대중국 경상수지']}[num][i]
  if num==42: label='수출금액 증가율' if i==0 else '수출물량 증가율'
  if num==41: label='부산/서울 잔액 비율'
  ax.plot(range(len(ts)),[float(y) if y is not None else float('nan') for y in ys],label=label,linewidth=1.6);ax.set_ylabel(chartunits[i]);ax.grid(alpha=.25);ax.legend(loc='best',fontsize=8)
  if num>=21 and (panels==1 or i==1) and num not in (49,50):ax.axhline(0,color='#777',linewidth=.7)
  if num in (49,50):ax.axhline(100,color='#777',linewidth=.7)
 for ax in axes:
  ticks=list(range(0,len(ts),max(1,math.ceil(len(ts)/9)))); ax.set_xticks(ticks,[display_period(ts[i],freq) for i in ticks],rotation=35,ha='right',fontsize=8);ax.set_xlabel('시점')
 fig.suptitle(ident+' · '+titles[num-1],fontsize=11); fig.supxlabel('자료: '+ '\n'.join(textwrap.wrap(' / '.join(z[0] for z in sources),width=88))+'  |  조회 기준: 2026-10-27',fontsize=7);buf=io.BytesIO();fig.savefig(buf,format='png',dpi=110);plt.close(fig)
 img=base64.b64encode(buf.getvalue()).decode(); hdr=''.join('<th>'+html.escape(str(h))+'</th>' for h in heads); body=''.join('<tr>'+''.join('<td>'+html.escape(display_period(x,freq) if isinstance(x,str) and len(x)==6 and x.isdigit() and freq=='Q' else pp(x))+'</td>' for x in row)+'</tr>' for row in records)
 sources_html='<br>'.join(html.escape(f'{s[0]} · {s[1]} · {s[2]}') for s in sources)
 sections.append(f'<section><h2>{ident}</h2><p>{html.escape(query)}</p><p><b>원천:</b> {sources_html}</p><img alt="{ident} 참고 그래프" src="data:image/png;base64,{img}"><table><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table></section>')
if problems:
 print('INCOMPLETE',len(problems),problems[:20]);raise SystemExit(2)
assert len(sections)==50
page='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>v1.4 참고 표와 그래프</title><style>body{font:15px Malgun Gothic,sans-serif;color:#172536;max-width:1100px;margin:30px auto;padding:0 20px}section{margin:45px 0;border-top:2px solid #243f59}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #ccd5df;padding:5px;text-align:right}th{background:#edf3f7}td:first-child,th:first-child{text-align:left}th{position:sticky;top:0}p{line-height:1.6}</style></head><body><h1>v1.4 참고 표와 그래프 · 50문항</h1><p>2026-10-27 KOSIS 조회값 기반. 이 결과는 공개 스냅샷과 다를 수 있으며 사람의 원자료·산식·그래프 최종 검수 전입니다. 표의 파생값은 중간 반올림 없이 계산 후 소수 여섯째 자리까지 표시합니다. 모든 시점은 요청된 기간만 표시하고 계산용 선행 관측은 표의 비교시점에 표기합니다. 오류·원천 개정 가능성을 검토하세요.</p>'''+''.join(sections)+'</body></html>'
out.write_text(page,encoding='utf-8')
print('cases',len(sections),'output rows',checked,'missing',len(problems),'html bytes',out.stat().st_size,'file',out)
