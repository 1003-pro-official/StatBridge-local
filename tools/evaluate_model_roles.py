"""Opt-in live role evaluation. Synthetic dev inputs, never private holdout data.
Run with the project's configured API key; writes results only to ignored cache.
"""
from pathlib import Path
import sys,json,time,concurrent.futures
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
from openai_chart_client import OpenAIChartClient
from output_agent import OutputAgent
from report_summary import explain


def case(index):
    # Distinct units, periods, turning/flat/growth patterns and 1-3 series.
    frequency=('M','Q','Y')[index%3]
    dates={'M':['202401','202402','202403','202404','202405','202406'], 'Q':['202301','202302','202303','202304','202401','202402'], 'Y':['2019','2020','2021','2022','2023','2024']}[frequency]
    units=['지수','%','억원','천명','원'][index%5]
    patterns=[[100,102,104,106,108,110],[110,108,106,104,102,100],[100,100,100,100,100,100],[100,105,103,108,104,110],[100,95,90,94,98,101]]
    series=[{'label':f'합성 검증지표{index+1}-{j+1}','frequency':frequency,'unit':units,'points':[{'date':d,'value':v+j*10} for d,v in zip(dates,patterns[(index+j)%5])]} for j in range(1+index%3)]
    chart=('line','bar')[index%2]
    title=f'합성 지표 검증 {index+1}'
    request={'natural_language':f'제목은 "{title}"로 하고 '+('선 그래프' if chart=='line' else '묶음 막대그래프')+'로 보여줘.'}
    return series,request,chart,title


def evaluate(index):
    client=OpenAIChartClient(model='gpt-6-luna');series,request,chart,title=case(index);t=time.perf_counter()
    result=explain(series,client)
    proposed=OutputAgent(client)._propose_spec(series,request)
    return dict(case=index+1,source=result['source'],summary_ok=result['source']=='gpt-6-luna',style_ok=proposed.get('chart_type')==chart and proposed.get('title')==title,seconds=round(time.perf_counter()-t,3))


def main():
    load_dotenv(ROOT/'.env',override=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(evaluate,range(30)))
    summary=sum(r['summary_ok'] for r in results);style=sum(r['style_ok'] for r in results)
    payload={'model':'gpt-6-luna','dev_cases':30,'summary_pass':summary,'style_title_pass':style,'rules_ratio':(30-summary)/30,'gate_pass':summary>=29 and style>=27,'cases':results}
    folder=ROOT/'.venv/cache/model-migration-20261021';folder.mkdir(parents=True,exist_ok=True)
    (folder/'luna-dev30.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k!='cases'}),flush=True)
    return 0 if payload['gate_pass'] else 1

if __name__=='__main__':raise SystemExit(main())
