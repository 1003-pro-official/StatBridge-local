raise SystemExit("Legacy v1 generator disabled in vNext; use patch_reviewed_dataset.py and render_reviewed.py. Original files are preserved at baseline_reference/source_hashes.json references.")
"""Package only evaluation artifacts; refuse if configured secrets leaked."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,hashlib,zipfile,sys,platform,subprocess,importlib.metadata,re
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--local1',type=Path,required=True);args=ap.parse_args()
    validation=json.loads((ROOT/'validation/dataset_validation.json').read_text(encoding='utf-8'))
    assert validation['status']=='pass','Dataset checks must pass before packaging'
    from dotenv import dotenv_values
    env=dotenv_values(args.local1/'.env')
    secrets=[str(v).encode() for k,v in env.items() if re.search('KEY|SECRET|PASSWORD|TOKEN|COOKIE',k,re.I) and v and len(str(v))>=12]
    files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    leaks=[]
    for p in files:
        if p.name in ['.env','accounts.sqlite3'] or p.suffix in ['.sqlite3','.db']:leaks.append(str(p.relative_to(ROOT)))
        data=p.read_bytes()
        if any(secret in data for secret in secrets):leaks.append(str(p.relative_to(ROOT)))
    assert not leaks,'Secret/database content found in: '+','.join(leaks)
    commit=subprocess.run(['git','-C',str(args.local1),'rev-parse','HEAD'],capture_output=True,text=True,check=False).stdout.strip()
    diff=subprocess.run(['git','-C',str(args.local1),'diff','--binary','HEAD'],capture_output=True,check=False).stdout
    versions={}
    for name in ['pydantic','pandas','numpy','requests','python-dotenv','ragas']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    (ROOT/'validation/environment.json').write_text(json.dumps({'python':platform.python_version(),'platform':platform.platform(),'local1':str(args.local1),'commit':commit,'tracked_diff_sha256':hashlib.sha256(diff).hexdigest(),'note':'Tracked diff hash excludes untracked files; selected source file hashes below. No model inference performed.','module_hashes':{str(p.relative_to(args.local1)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.local1/'src/agent/expression_tree_schema.py',args.local1/'src/agent/expression_tree_validator.py',args.local1/'src/agent/dynamic_expression_executor.py']},'validation_dependency_versions':versions},ensure_ascii=False,indent=2),encoding='utf-8')
    snapshots=list((ROOT/'oracle/source_snapshots').glob('*.json'))
    fetched=sum(json.loads(p.read_text(encoding='utf-8')).get('status')=='fetched' for p in snapshots)
    report=f'''# 평가셋 검증 결과

2026-10-28 · ai-assisted · 평가셋 자체 검증

'''
    report+=f'''| 검증 항목 | 결과 |
|---|---|
| 문항 수·영역 | 120개, QT/CQ/DA/D/E/F 각20개 |
| 원문 보존·입력/정답 분리 | 검증 통과 |
| 자동 검증 | **{validation['passed']}/{validation['checks']} 통과, 실패 {validation['failed']}** |
| 독립 API 원자료 | DA20개와 동등 GDP 후보2개, 스냅샷 {fetched}개 확보 |
| DA 기관·표·항목·분류·주기·기간·단위 | 실제 KOSIS 응답 및 카탈로그 대조20/20 |
| GDP 대체 표 | 요청 전 기간 값·단위 동일2/2 확인 |
| D 독립 Decimal 산식 검산 | 20/20 |
| D local1 계산 엔진·계획·이력 대조 | 20/20, 오프라인 |
| E/F 단계별 정답 상태 계약 | 40개 구성·단계 수·원수치 보존 검사 |
| 채점기 양성·오류 주입 검사 | 120쌍. F는 checkpoint 계약과 파일 증거 미관측 보류를 검사 |
| RAGAS 입력 변환 | 실제 근거 필수·정답 context 사용 거부·근거 누락 보류 검사 |
| 빈 실제 실행 방어 | 120개 모두 not_executed, 성공 생성 없음 |
| 사람 정답 승인 | **대기** |
| 제품 자연어 120문항 평가 | **미실행** |
| 브라우저·다운로드 E2E | **미실행** |
| RAGAS 라이브러리·판정 모델 실행 | **미실행** |

이 결과는 제품 성능 120/120 또는 RAGAS 점수가 아니다. 검증 수는 데이터셋·채점기·계산기 준비 검사의 수다. 합성 관측값은 채점기 검증에만 사용했으며 제품 예측으로 제출하지 않았다.

v2.1 원본 정답이 ZIP과 확인한 local1 경로에 없어 질의·카탈로그에서 독립 재작성했다. 원본 정답 파일을 복원했다는 주장은 하지 않는다. CQ 의미 판정과 E/F 시각·단계 계약에는 사람 검토가 필요하다. 정답을 제품 입력에 넣어 높은 점수를 만드는 방식은 사용하지 않았다.

DA oracle은 공식 API에서 독립 수집했다. 첫 일반 권한 실행에서 연결 오류가 발생해 권한을 확보한 재실행으로 원자료를 수집했다. 이 오류는 제품의 질의 실패로 집계하지 않았다. 제품 응답을 정답 생성에 사용하지 않았다.

수정한 것은 이 별도 평가 패키지뿐이다. 원본 StatBridge-local1과 StatBridge/StatBridge-local1의 앱 코드·환경·계정·저장 분석을 변경하지 않았고 서비스도 시작·중지하지 않았다.

키·계정 DB 포함 검사: 현재 구성된 키 값이 패키지에 포함되지 않았고 .env·계정 DB도 포함되지 않았다. 비밀 값과 원본 환경 파일은 출력하지 않았다.

재현 명령과 검증 범위는 README.md, 세부 결과는 validation/dataset_validation.json, 실행 환경·계산 엔진 hash는 validation/environment.json을 확인한다.
'''
    (ROOT/'05_평가셋_검증결과.md').write_text(report,encoding='utf-8-sig')
    manifests={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts}
    manifest={'name':'StatBridge 전용 정량 평가: 규칙 검증 및 RAGAS 기반 평가셋','version':'1.0.0','date':'2026-10-28','cases':120,'human_review':'pending','dataset_validation':'pass','product_evaluation_executed':False,'ragas_judge_executed':False,'source_snapshots':fetched,'files_sha256':manifests}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=ROOT.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:z.write(p,Path(ROOT.name)/p.relative_to(ROOT))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps({'folder':str(ROOT),'zip':str(archive),'archive_bytes':archive.stat().st_size,'files':len(manifests)+1,'dataset_checks':validation['checks'],'secret_scan':'pass','archive_integrity':'pass','human_review':'pending','product_evaluation_executed':False},ensure_ascii=False))
if __name__=='__main__':main()
