"""Independent current-observation check; not supplied to query executor."""
import sys,json
from pathlib import Path
from datetime import date
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src/backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
from statbridge_mcp.kosis_client import KosisClient
d=json.loads((HERE/'predictions/CQ21-16.json').read_text(encoding='utf8'))
plans=d['resolved_result']['api_plans'];out=[]
for p in plans:
 rows=KosisClient().get_statistics(p['org_id'],p['table_id'],p['item_id'],p['frequency'],'202401',date.today().strftime('%Y%m'),p['classifications'])
 out.append({'plan':p,'queried_end':date.today().strftime('%Y%m'),'latest_observed':max((str(r['PRD_DE']) for r in rows),default=None),'rows':rows})
(HERE/'latest-observation-check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print([(x['plan']['table_id'],x['latest_observed']) for x in out])
