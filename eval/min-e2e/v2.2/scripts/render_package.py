raise SystemExit("Legacy v1 generator disabled in vNext; use patch_reviewed_dataset.py and render_reviewed.py. Original files are preserved at baseline_reference/source_hashes.json references.")
"""Render human-readable datasets and review forms from scorer contracts."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]
cases=[json.loads(l) for l in (ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines()]
NAMES={'QT':'질의 유형 분류','CQ':'역질문 적절성','DA':'데이터 조회 정확성','D':'파생 계산 정확성','E':'편집 계약','F':'화면·파일 일치'}
def write(name,s):(ROOT/name).write_text(s,encoding='utf-8-sig')
def safe(s):return str(s).replace('|','&#124;').replace('\r','').replace('\n','<br>')
def reference(c):
    e=c['expected'];g=c['group']
    if g=='QT':return e['label']+' — '+e['rationale']
    if g=='CQ':
        return ('확인 필요: '+e['question_target'] if e['clarification_required'] else '재질문 불필요')+'; 유지: '+', '.join(e['preserve_conditions'])+('; 결과 확정 전 실행 금지' if e['clarification_required'] else '')
    if g=='DA':
        s=e['sources'][0];p=ROOT/e['snapshot_file'];d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        values='; '.join(r['period']+': '+r['value']+' '+str(r['unit']) for r in d.get('rows',[]))
        alt='; 검증된 동등 GDP 표 후보 '+e['allowed_source_sets'][1][0]['table_id'] if e.get('allowed_source_sets') else ''
        return s['table_id']+' / '+s['item_id']+' / '+json.dumps(s['classifications'],ensure_ascii=False)+' / '+s['frequency']+'; '+values+alt
    return c['reference_text']
head='# StatBridge 전용 정량 평가 · 질의 전용 120문항\n\n2026-10-28 · 공개 개발 평가 · 제품 입력에는 질문 본문만 전달. E/F는 순서별 UI 단계를 실제 수행. 정답은 별도 파일에 보관.\n'
gold='# StatBridge 전용 정량 평가 · 채점자용 질의와 정답 120문항\n\n2026-10-28 · ai-assisted · 사람 정답 검토 대기. 제품 입력 금지. 기존 두 세트의 원문 질의 120개이며 새로 생성된 미노출 질의가 아니다. DA 값은 2026-10-28 독립 KOSIS 수집 스냅샷, D/E/F는 계승 고정 fixture 기준.\n\n| 지표 | 질의 | 정답 |\n|---|---|---|\n'
review='# 정답 사람 검토 · 120문항\n\n작성자와 다른 검토자가 질의·계열·단위·산식·기간·출력·허용 대체·채점 기준을 검토합니다. 빈칸은 미검토이며 자동 승인하지 않습니다. 수정 시 이전 정답·hash·수정 이유를 보존하고 새 버전으로 검증합니다.\n\n| ID | 영역 | 상태 | 검토자 | 판정 근거·수정 사항 |\n|---|---|---|---|---|\n'
for g in ['QT','CQ','DA','D','E','F']:
    head+='\n## '+NAMES[g]+' · 20문항\n'
    for c in [c for c in cases if c['group']==g]:
        head+='\n### '+c['id']+'\n\n'+c['query']+'\n'
        gold+='| '+safe(c['id']+' · '+NAMES[g])+' | '+safe(c['query'])+' | '+safe(reference(c))+' |\n'
        review+='| '+c['id']+' | '+NAMES[g]+' | 검토 대기 | | |\n'
write('01_질의전용_120문항.md',head);write('02_질의와_정답_120문항.md',gold);write('04_정답_사람검토_120문항.md',review)
pilot=['QT21-01','QT21-02','CQ21-01','CQ21-11','DA21-03','DA21-06','D32','D33','E24','E33','F23','F30']
(ROOT/'runner/pilot_ids.json').write_text(json.dumps(pilot,indent=2),encoding='utf-8')
template={'evaluation_id':None,'checkout':None,'commit':None,'dirty_diff_sha256':None,'models':None,'evaluator_model':None,'ragas_version':None,'judge_prompt_version':None,'data_mode':None,'metadata_readiness':None,'viewport':None,'attempt_policy':'first and retry separate; never choose best result','product_evaluation_executed':False,'ragas_judge_executed':False}
(ROOT/'results/run_manifest.template.json').write_text(json.dumps(template,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'results/observations.empty.jsonl').write_text('',encoding='utf-8')
write('docs/3인_검토와_실행분담.md','''# 3인 진행 제안

1명은 QT/CQ 정답의 의도·미확정 조건·부정·정정 처리를 검토하고, 1명은 DA/D의 식별자·기간·단위·독립 계산을 검토하며, 1명은 E/F의 단계·이력·부분 범위·실제 파일 계약을 검토합니다. 각 영역의 다른 팀원이 교차 검토합니다.

pilot 12문항의 동일 응답을 각자 먼저 판정한 뒤 기준을 조정합니다. 공동 합의 또는 AI 보조를 독립 사람 평가로 표현하지 않습니다. 합의 전 원점수와 이견을 보존합니다. 평가자가 접근한 정답을 제품/모델에 입력하지 않습니다.

검토 승인 이후 실행 담당은 질문·UI 시나리오만 사용하고, 채점 담당은 응답·화면·파일을 동결한 뒤 정답을 대조합니다. 120문항을 운영할 때 평가용 계정과 결과 디렉터리를 별도로 준비합니다. 저장·재개는 같은 계정·동일 백엔드 실행 범위입니다.
''')
print('Rendered 120 query sections, 120 reference rows, 120 human review rows, pilot 12.')
