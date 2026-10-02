#!/usr/bin/env python3
"""Enrich the existing catalog using local rules and opt-in cached model calls."""
import argparse
from enrichment.pipeline import run
from enrichment.model import MissingCredentials

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true',help='로컬 원본·문맥·번호 직결 설명 및 모델 대기 목록 생성')
    parser.add_argument('--apply',action='store_true',help='이미 저장된 로컬 보완·모델 결과만 적용')
    parser.add_argument('--run-llm',action='store_true',help='인증된 모델에 목적·태그 보완 요청 (유효 캐시 제외)')
    parser.add_argument('--run-vision',action='store_true',help='데이터 추정으로도 불명인 그림 영역에 비전 요청')
    parser.add_argument('--max-calls',type=int,default=250)
    parser.add_argument('--batch-size',type=int,default=20)
    parser.add_argument('--model',default=None)
    parser.add_argument('--report',default=None)
    args=parser.parse_args()
    try:run(args.report,llm=args.run_llm,vision=args.run_vision,max_calls=args.max_calls,batch_size=args.batch_size,model=args.model)
    except MissingCredentials as exc:parser.exit(2,str(exc)+'\n')

if __name__=='__main__':main()
