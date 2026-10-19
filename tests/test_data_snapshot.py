import csv
import json
from pathlib import Path

import pytest

from statbridge_mcp import data_snapshot


def row(value='10', period='202501', **fields):
    return dict(TBL_ID='DT_TEST', PRD_SE='M', PRD_DE=period, ITM_ID='item', C1='code', DT=value, UNIT_NM='억원', **fields)


def write(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_refresh_backs_up_and_preserves_revision_evidence(tmp_path):
    path = tmp_path / 'DT_TEST.csv'; write(path, [row()]); original = path.read_bytes()
    result = data_snapshot.replace_snapshot(path, [row('11')], 'DT_TEST', tmp_path / 'versions')
    assert Path(result['backup']).read_bytes() == original
    assert result['changed_values'] == 1
    assert list(csv.DictReader(path.open(encoding='utf-8-sig')))[0]['DT'] == '11'
    assert json.loads(Path(result['manifest']).read_text())['sha256_before'] != result['sha256_after']


@pytest.mark.parametrize('bad', [[], [row(), row()], [row(period='202502')], [row('nan')], [dict(row(), TBL_ID='WRONG')], [dict(row(), UNIT_NM='원')]])
def test_invalid_refresh_never_changes_existing_data(tmp_path, bad):
    path = tmp_path / 'DT_TEST.csv'; write(path, [row()]); before = path.read_bytes()
    with pytest.raises(ValueError):
        data_snapshot.replace_snapshot(path, bad, 'DT_TEST', tmp_path / 'versions')
    assert path.read_bytes() == before


def test_fingerprint_is_order_independent_and_detects_revision():
    a, b = row(), row('12', period='202502')
    assert data_snapshot.observation_version([a,b]) == data_snapshot.observation_version([b,a])
    assert data_snapshot.observation_version([a]) != data_snapshot.observation_version([row('11')])


def test_multi_table_fetch_failure_applies_nothing(monkeypatch):
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location('refresh', Path(__file__).parents[1] / 'tools/refresh_kosis_snapshot.py')
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    monkeypatch.setattr(sys, 'argv', ['refresh', 'DT_A', 'DT_B', '--live', '--apply'])
    monkeypatch.setattr(cli, 'StatisticsService', lambda: type('Service', (), {'client':True})())
    def fetch(service, table):
        if table == 'DT_B': raise ValueError('incomplete response')
        return Path('unused'), [row()]
    applied = []
    monkeypatch.setattr(cli, 'fetch_existing_domain', fetch)
    monkeypatch.setattr(cli, 'replace_snapshot', lambda *args: applied.append(args) or {})
    assert cli.main() == 1
    assert applied == []


def test_failed_atomic_replace_keeps_original_and_backup(tmp_path, monkeypatch):
    path=tmp_path/'DT_TEST.csv';write(path,[row()]);before=path.read_bytes()
    def fail(*args):raise OSError('disk failure')
    monkeypatch.setattr(data_snapshot.os,'replace',fail)
    with pytest.raises(OSError):data_snapshot.replace_snapshot(path,[row('11')],'DT_TEST',tmp_path/'versions')
    assert path.read_bytes()==before
    assert next((tmp_path/'versions').glob('*.csv')).read_bytes()==before
    assert not list(tmp_path.glob('*.tmp'))
