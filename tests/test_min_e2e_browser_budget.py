"""Execute the actual frontend budget classifier with Node's TS loader."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest


def test_arithmetic_queries_keep_derived_budget_without_extending_visual_edits():
    node=shutil.which('node')
    if not node:pytest.skip('Node is required for the actual TypeScript classifier')
    module=Path(__file__).resolve().parents[1]/'src/agent/frontend/src/derivedDeadline.ts'
    cases=[
        ('2025년 1~6월 가계대출 금리−저축성수신 금리를 계산해줘.',None,120000),
        ('같은 기간 수신금리-가계대출금리로 바꿔줘.',None,120000),
        ('금리/다른 금리를 계산해줘.',None,120000),
        ('금리 선 색상을 파랑으로 바꿔줘.',None,20000),
        ('2025-01부터 2025-06까지 금리 비교',None,20000),
        ('제목을 ‘금리−대출금리’로 바꿔줘.',None,20000),
        ('계산하지 말고 금리 제목만 바꿔줘.',None,20000),
        ('평균 대출금리 추이를 보여줘.',None,20000),
        ('다시 계산해줘.',{'_derived_query':True},120000)]
    # Keep regression inputs independent of disposable evaluation artifacts.
    cases += [
        ('2025년 1~3월 수신금리의 월별 공표값을 단순 산술평균해줘. 결과는 종료 월에 한 점으로 표시해줘.',None,120000),
        ('가계대출 금리의 2025년 6월 값이 1월보다 몇 %p 변했는지 계산해줘.',None,120000),
    ]
    code=f"import {{derivedBudget}} from {json.dumps(module.as_uri())};import fs from 'node:fs';const rows=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(rows.map(([q,s])=>derivedBudget(q,s))));"
    result=subprocess.run([node,'--experimental-strip-types','--input-type=module','-e',code],input=json.dumps(cases,ensure_ascii=False),text=True,encoding='utf-8',capture_output=True,timeout=20,check=True)
    assert json.loads(result.stdout)==[c[2] for c in cases]
