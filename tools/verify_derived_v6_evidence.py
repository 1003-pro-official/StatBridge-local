"""Verify immutable evidence from the actual-provider browser experiment."""
import hashlib, json, shutil
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = ['34584431a69f4b26a3dc6f7322dcef5c', 'c0a39a7c2b424b8b8c0c8f11e4865703']

def main():
    folder = ROOT / 'eval/derived_v6_ui_records'
    folder.mkdir(exist_ok=True)
    workspace_path = next((ROOT / '.venv/cache/derived-v6/live-supplements/user-1').glob('*/workspace.json'))
    workspace = json.loads(workspace_path.read_text(encoding='utf8'))
    file = workspace['files']['synthetic_cost_index']
    raw = workspace_path.parent / 'files' / (file['file_id'] + '.csv')
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == file['sha256']
    shutil.copy2(raw, folder / 'synthetic_cost_index.csv')
    records = []
    for index, cid in enumerate(IDS):
        path = ROOT / 'runtime_data/derived_evidence' / (cid + '.json')
        payload = json.loads(path.read_text(encoding='utf8')); e = payload['evidence']
        canonical = json.dumps(e, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str)
        assert hashlib.sha256(canonical.encode()).hexdigest() == payload['sha256']
        api = e['source_data']['ppi_total']; uploaded = e['source_data']['synthetic_cost']
        assert api['source'] == 'kosis_api' and uploaded['source'] == 'user_file'
        assert uploaded['sha256'] == file['sha256']
        assert all(r['ORG_ID'] == '301' and r['TBL_ID'] == 'DT_404Y014' and r['ITM_ID'] == '13103134604999' and r['C1'] == '13102134604ACC_CD.*AA' for r in api['rows'])
        assert all('ORG_ID' not in r for r in uploaded['rows'])
        assert e['source_metadata'][0]['metadata_origin'] == 'actual_KOSIS_metadata_API'
        costs = {r['PRD_DE']: Decimal(str(r['DT'])) for r in uploaded['rows']}
        checked = 0
        for r in api['rows']:
            period = r['PRD_DE']
            if not e['plan']['start_period'] <= period <= e['plan']['end_period']: continue
            expected = Decimal(str(r['DT'])) / costs[period]
            actual = Decimal(str(e['node_results']['ratio_ppi_to_synth']['values'][period]))
            assert abs(expected - actual) <= Decimal('1e-12')
            checked += 1
        assert checked == (4 if index == 0 else 3)
        assert e['previous'] == (None if index == 0 else IDS[0])
        assert all(u['model'] == 'gpt-5.4' for u in e['usage'])
        assert len(e['usage']) == (3 if index == 0 else 0)
        shutil.copy2(path, folder / path.name)
        records.append({'calculation_id': cid, 'sha256': payload['sha256'], 'checked_Decimal_points': checked,
                        'plan_GPT_calls': len(e['usage']), 'previous': e['previous'], 'status': 'PASS'})
    state = (ROOT / 'eval/derived_v6_live_restore_state.txt').read_text(encoding='utf8')
    assert IDS[1] in state and file['sha256'] in state and '1.169100' in state and 'synthetic_cost' in state
    result = {'status': 'PASS', 'provider': 'actual GPT-5.4 and actual KOSIS API',
              'file_data': 'explicitly synthetic user-provided CSV; NOT official KOSIS data',
              'api_observations': 4, 'checked_Decimal_points': 7, 'file_sha256': file['sha256'], 'records': records,
              'browser_verified': ['question', 'API fetched before file', 'CSV template', 'CSV paste/upload', 'graph', 'table',
                                   'period widget 4 to 3 observations', 'undo', 'redo', 'save', 'restore', 'evidence', 'raw API and file data'],
              'native_file_picker': 'NOT_EXECUTED; CSV paste used the same authenticated upload endpoint',
              'checkout': 'StatBridge-local1; second checkout independently tested with offline HTTP/regressions/build',
              'proof': ['derived_v6_live_upload_graph_proof.jpg', 'derived_v6_live_upload_table_proof.jpg', 'derived_v6_live_restore_state.txt']}
    (ROOT / 'eval/derived_v6_ui_evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__': main()
