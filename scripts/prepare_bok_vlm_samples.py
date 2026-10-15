"""Download public reports and render reproducible graph crops; never commit PDFs."""
import argparse,json,hashlib,shutil,subprocess
from pathlib import Path
import requests
from pypdf import PdfReader,PdfWriter
ROOT=Path(__file__).resolve().parents[1]
def prepare(manifest,out,poppler):
    cases=json.loads(manifest.read_text(encoding='utf-8-sig'))['cases'];out.mkdir(parents=True,exist_ok=True)
    for case in cases:
        pdf=out/(case['report']+'.pdf')
        if not pdf.exists():
            response=requests.get(case['download_url'],timeout=60);response.raise_for_status()
            if not response.content.startswith(b'%PDF'):raise ValueError('공식 PDF를 받지 못했습니다.')
            pdf.write_bytes(response.content)
        reader=PdfReader(pdf);page=reader.pages[case['pdf_page']-1]
        width=float(page.mediabox.width);height=float(page.mediabox.height);x0,y0,x1,y1=case['crop']
        page.cropbox.lower_left=(width*x0,height*(1-y1));page.cropbox.upper_right=(width*x1,height*(1-y0))
        writer=PdfWriter();writer.add_page(page);cropped=out/(case['id']+'.pdf')
        with cropped.open('wb') as stream:writer.write(stream)
        subprocess.run([poppler,'-cropbox','-scale-to','1400','-png','-singlefile',str(cropped),str(out/case['id'])],check=True,capture_output=True)
        case.update(reference_file=case['id']+'.png',pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
    (out/'samples.json').write_text(json.dumps({'cases':cases},ensure_ascii=False,indent=2),encoding='utf-8')
    return cases
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--pdftoppm',default=shutil.which('pdftoppm'));p.add_argument('--manifest',type=Path,default=ROOT/'eval/chart-reference/v1/cases.json');args=p.parse_args()
    if not args.pdftoppm:p.error('pdftoppm 경로를 --pdftoppm으로 지정해 주세요.')
    prepare(args.manifest,args.output_dir,args.pdftoppm)
