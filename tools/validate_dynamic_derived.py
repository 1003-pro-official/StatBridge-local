"""Explicit live-provider smoke check. Run with --live; never loads evaluation answers."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'/'agent'), str(ROOT/'src'/'backend')]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--query', default='2023년 1월부터 2024년 12월까지 생산자물가 총지수의 전년동월 대비 상승률을 계산해 주세요.')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--trace', action='store_true')
    args=parser.parse_args()
    if not args.live:
        parser.error('실제 GPT 및 KOSIS 호출에는 --live가 필요합니다.')
    import bridge_api as api
    if args.trace:
        client=api.agent.workflow.derived_runtime.planner.client
        original=client.request
        def traced(*args,**kwargs):
            text,metadata=original(*args,**kwargs)
            print('MODEL_ACTION',text[:3000],flush=True)
            return text,metadata
        client.request=traced
    result=api.agent.workflow.invoke(query=args.query, execute=True)
    safe={k: result.get(k) for k in ('status','question','missing','searches','derivedEvidence','orchestration')}
    safe['row_count']=(result.get('execution') or {}).get('row_count',0)
    safe['preview']=((result.get('execution') or {}).get('rows') or [])[:3]
    if result.get('_derived'):
        safe['source_preview']={alias:response['rows'][:3] for alias,response in result['_derived']['responses'].items()}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(safe,ensure_ascii=False,indent=2))
    return 0 if result.get('status')=='resolved' else 1


if __name__=='__main__':
    raise SystemExit(main())
