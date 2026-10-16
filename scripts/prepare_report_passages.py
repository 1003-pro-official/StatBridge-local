"""Extract page-bound evidence candidates; never automatically approve OCR/text.

Usage: python scripts/prepare_report_passages.py --pdf original.pdf --title TITLE
       --publication-date YYYY-MM-DD --reference OFFICIAL_URL --output candidates.jsonl
Visually check original pages, period definitions and associated notes before
setting verified=true. Original PDFs and generated excerpts must remain local.
"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re


def clean_page(text):
    lines=[]
    for line in text.splitlines():
        if re.search(r'이 문서는 한국은행의 자산|복사,?\s*촬영|\S+\s*/\s*\S+\s*/\s*20\d{2}-\d{2}-\d{2}|[\w.+-]+@[\w.-]+',line):continue
        lines.append(line)
    return '\n'.join(lines).strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ['pdf','title','publication-date','reference','output']:parser.add_argument('--'+flag,required=True)
    args=parser.parse_args();date.fromisoformat(args.publication_date)
    from pypdf import PdfReader
    pdf=Path(args.pdf);fingerprint=hashlib.sha256(pdf.read_bytes()).hexdigest()
    records=[]
    for page,original in enumerate(PdfReader(pdf).pages,1):
        text=clean_page(original.extract_text() or '')
        if not text:continue
        records.append(dict(id=f'{fingerprint[:16]}-p{page}',title=args.title,publication_date=args.publication_date,
            page=page,reference=args.reference,original_sha256=fingerprint,text=text,
            verified=False,human_reviewed=False,kind='observation',
            review_required='본문·각주·그림·표 연결과 분석 기간·단위·자료 상태를 원본 페이지로 확인하세요.'))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in records)+'\n',encoding='utf-8')
    print(f'{len(records)} unverified page candidates; no entry promoted to report evidence.')


if __name__=='__main__':main()
