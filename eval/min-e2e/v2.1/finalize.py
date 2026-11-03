"""Package reviewable evaluation artifacts, excluding credentials and caches."""
import json,hashlib,zipfile,collections,subprocess,os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
s=json.loads((HERE/'scores.json').read_text(encoding='utf8'))
names={'DA':'데이터 조회 정확도','CQ':'역질문 적절성','QT':'질의 유형 분류 정확도'}
lines=['# v2.1 고난도 60문항 평가 결과','',
'ai-assisted · 공개 개발셋 · 사람 검토 대기 · 2026-10-27','',
'모델·제품 입력에는 원본 questions.jsonl의 질의만 사용했다. 정답·기준 문항·난이도 태그를 전달하지 않았다. 각 요청에는 이전 상태나 후속 답변이 없으며, 원본 응답 60개와 SHA-256을 확정한 뒤 별도 scorer가 공개 정답을 읽었다.','',
'데이터 조회와 역질문은 실제 /api/query 경로를 FastAPI TestClient로 실행했다. 실제 KOSIS 원자료를 사용하며 고정 정답 수치나 모의 응답을 주입하지 않았다. 질의 유형 20개는 제품 is_derived_request()의 로컬 분기 평가다. 브라우저 화면·그래프 생성·클릭까지의 UI E2E 점수 또는 단일 LLM의 성능으로 해석하지 않는다.','',
'| 평가 항목 | 통과 | 미통과 | 보류/검토대기 | 통과율 |','|---|---:|---:|---:|---:|']
for g,name in names.items():
 c=s['summary'][g];pending=sum(v for k,v in c.items() if k not in ['통과','미통과'])
 lines.append(f"| {name} | {c.get('통과',0)}/20 | {c.get('미통과',0)} | {pending} | {c.get('통과',0)/20:.0%}{' (잠정)' if pending else ''} |")
lines+=['','평가 항목별 점수를 분리했으며 팀원의 v2 또는 v1.1의 과거 UI 점수와 합산·직접 비교하지 않았다. 동일 조건의 v1.1 재실행 없이 난이도 상승의 효과를 수치로 단정하지 않는다.','',
'## 세부 분포','', '| 구분 | 통과 | 미통과 | 보류/검토대기 |','|---|---:|---:|---:|']
for g,key,values in [('QT','expected',['general','derived']),('CQ','clarification_required',[True,False])]:
 for v in values:
  rows=[r for r in s['results'] if r['group']==g and r['details'].get(key)==v]
  c=collections.Counter(r['status'] for r in rows)
  label=('역질문 필요' if v else '역질문 불필요') if g=='CQ' else v
  lines.append(f"| {label} | {c['통과']}/10 | {c['미통과']} | {len(rows)-c['통과']-c['미통과']} |")
lines+=['','## 관측된 주요 문제','',
'- 부정·인용 처리: 제목의 증가율, ‘전월 대비 변화는 다음 작업’, ‘이동평균 처리는 빼줘’를 실제 계산 의도로 처리한다.',
'- 간접 연산 인식: 1/6씩 반영한 한 숫자, 두 금리 사이 간격, 최댓값과 최솟값 사이 거리 등을 일반 조회로 분류한다.',
'- 확정 조건 유지: 잔액 금리만 요청했는데 신규취급액까지 포함하거나, 중소기업만 요청했는데 대기업도 함께 조회한다.',
'- 기간 해석: ‘첫 석 달’·‘첫 분기’를 월별 1~12월로 확대하는 사례가 있다.',
'- 최신 관측: CQ21-16은 202608로 종료했지만 독립 KOSIS 조회의 마지막 관측월은 202609였다. 원계열만 요청했는데 순환변동치도 포함했다.','',
'## 채점·재실행 원칙','',
'데이터 조회는 기관·표·항목·분류·주기·기간·단위·수치를 모두 비교했다. 수치 허용오차는 1e-6이다. 연간 A/Y, 전각 등호, (단위)^1의 수학적으로 동일한 단위는 정규화했다. 공식 원자료 개정 가능성이 있는 수치 단독 차이는 제품 오류와 분리한다.','',
'역질문은 질문 문장의 동일성이 아니라 미확정 조건을 정확하게 물었는지 채점했다. 불필요 문항은 재질문이 없더라도 폐기된 기준이나 이전 기본값으로 진행하면 통과로 보지 않았다. CQ21-15의 기간 오류는 별도 기록하고 두 계열을 모두 선택한 역질문 판단은 통과로 보았다. CQ21-17/20의 계산 수치는 역질문 점수에 사용하지 않았다. 의미 판정은 ai-assisted이며 사람 검토가 필요하다.','',
'초기 12문항은 실제 메타데이터 확인 대기였으므로 의미 오류로 판정하지 않았다. retry-policy.json에 먼저 고정한 이 12개만 메타데이터 준비 후 동일 질문·빈 상태로 재실행했다. 최초 응답은 predictions/, 재실행을 반영한 응답은 final-predictions/에 보존한다. 의미 오류를 보인 다른 문항은 재시도하거나 문장을 고치지 않았다. 재실행기는 정답 파일을 열지 않는다.','',
'초기 실행 프로세스 종료 시 백그라운드 수집기가 개별 API 응답 349개까지 저장하고 최종 캐시 목록은 저장하지 못했다. finish_inventory.py가 이번 실행에서 수집한 실제 응답만 확인해 제품과 같은 형식의 목록을 저장했고 제품 snapshot 검증을 통과했다. 원자료·메타데이터를 생성하거나 정답에서 가져오지 않았다. 각 응답의 해시는 inventory-finalization.json에 기록했다.','',
'## 실행·검증','',
'- 기준 커밋: ef02d2471c5d928f7de1382b2dd5c9db82322e9d, 브랜치 eval/v2.1-high-difficulty-60. 제품 코드·평가 문항 수정 없음.',
'- 실행 관측 모델: HCX-003, HCX-007, gpt-6.1-sol. 규칙으로 처리된 요청은 모델 호출 없이 종료될 수 있다.',
'- v2.1 데이터셋 검증기 통과, 전용 테스트 10개 통과. pytest 캐시 쓰기 권한 경고 1건.',
'- 제품 코드 변경·PR 제출이 없어 전체 회귀 테스트와 프런트엔드 빌드는 이번 평가에서 재실행하지 않았다.',
'- 인증은 격리된 테스트 DB를 사용했다. 계정 DB·키·환경 파일·원자료 캐시는 묶음에서 제외했다.','',
'재현 명령(저장소 루트, 키가 구성된 환경):','',
'```powershell',
'.venv\\Scripts\\python.exe -X utf8 evaluation_runs/v21-evaluation-20261027/run.py',
'.venv\\Scripts\\python.exe -X utf8 evaluation_runs/v21-evaluation-20261027/finish_inventory.py',
'.venv\\Scripts\\python.exe -X utf8 evaluation_runs/v21-evaluation-20261027/retry.py',
'.venv\\Scripts\\python.exe -X utf8 evaluation_runs/v21-evaluation-20261027/verify_latest.py',
'.venv\\Scripts\\python.exe -X utf8 evaluation_runs/v21-evaluation-20261027/score.py',
'.venv\\Scripts\\python.exe -X utf8 evaluation_runs/v21-evaluation-20261027/finalize.py',
'```','',
'기존 결과가 있으면 실행기는 덮어쓰지 않는다. 새 독립 실행은 새 실행 디렉터리에 스크립트를 복사해 진행한다. 라이브 원자료·모델 응답은 시점에 따라 달라질 수 있다.','']
for g,name in names.items():
 lines += [f'## {name}: 문항별 결과','', '| ID | 판정 | 근거 |','|---|---|---|']
 for r in s['results']:
  if r['group']==g:lines.append(f"| {r['id']} | {r['status']} | {'; '.join(r['reasons']).replace('|','/').replace(chr(10),' ')} |")
 lines.append('')
report=HERE/'평가결과.md';report.write_text('\n'.join(lines),encoding='utf8')
files=[p for p in HERE.iterdir() if p.suffix in {'.py','.md','.json','.jsonl'}]
files += list((HERE/'predictions').glob('*.json'))+list((HERE/'final-predictions').glob('*.json'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
secrets=[v for k,v in os.environ.items() if ('API_KEY' in k or k.endswith('_SECRET')) and len(v)>8]
for p in files:
 content=p.read_text(encoding='utf8')
 assert not any(secret in content for secret in secrets),f'Secret scan failed: {p.name}'
archive=HERE/'v2.1_고난도60_질의전용평가_20261027.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,str(p.relative_to(HERE)))
print(str(report));print(str(archive))
