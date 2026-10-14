import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/agent'))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/windows' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap = load('bootstrap')
runtime = load('portable_runtime')
processes = load('windows_process')


@pytest.mark.parametrize('version,expected', [('v18.20.0', False), ('v20.18.0', False),
    ('v20.19.0', True), ('v22.11.0', False), ('v22.12.0', True), ('v23.1.0', True), ('v24.21.0', True)])
def test_node_matches_locked_vite_engines(version, expected):
    assert bootstrap.node_supported(version) is expected


def test_copied_environment_prefix_is_rejected(tmp_path, monkeypatch):
    exe = tmp_path / '.venv/Scripts/python.exe'
    exe.parent.mkdir(parents=True)
    exe.touch()
    info = {'version': [3, 11], 'bits': 64, 'prefix': str(tmp_path / 'another-pc/.venv'), 'base': 'base-python'}
    monkeypatch.setattr(bootstrap, 'run', lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(info)))
    assert not bootstrap.python_usable(exe, tmp_path / '.venv')
    info['prefix'] = str(tmp_path / '.venv')
    assert bootstrap.python_usable(exe, tmp_path / '.venv')
    info['bits'] = 32
    assert not bootstrap.python_usable(exe, tmp_path / '.venv')


def test_broken_venv_is_preserved_before_recreation(tmp_path, monkeypatch):
    old = tmp_path / '.venv'
    old.mkdir()
    (old / 'old-environment.txt').write_text('preserve me')
    monkeypatch.setattr(bootstrap, 'ROOT', tmp_path)
    calls = []
    monkeypatch.setattr(bootstrap, 'python_usable', lambda *_: bool(calls))
    monkeypatch.setattr(bootstrap, 'checked', lambda command, **_: calls.append(command))
    bootstrap.ensure_venv()
    backup, = tmp_path.glob('.venv.invalid.*')
    assert (backup / 'old-environment.txt').read_text() == 'preserve me'
    assert calls[0][-2:] == ['venv', str(old)]


def test_access_denied_keeps_record_and_reused_pid_is_not_killed(tmp_path, monkeypatch):
    state = tmp_path / 'state.json'
    saved = {'root': str(runtime.ROOT.resolve()), 'services': [
        {'pid': 123, 'identity': {'executable': 'python', 'created': 1}}]}
    state.write_text(json.dumps(saved))
    monkeypatch.setattr(runtime, 'STATE', state)
    monkeypatch.setattr(runtime, 'process_identity', lambda _: {'executable': 'python', 'created': 2})
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *_args, **_kwargs: pytest.fail('Reused PID must not be stopped'))
    runtime.stop()
    assert not state.exists()
    state.write_text(json.dumps(saved))
    def denied(_):
        raise PermissionError()
    monkeypatch.setattr(runtime, 'process_identity', denied)
    with pytest.raises(RuntimeError, match='identity was kept'):
        runtime.stop()
    assert json.loads(state.read_text(encoding='utf-8'))['services'] == saved['services']


def test_legacy_wmi_identity_migrates_with_creation_time():
    ticks = 116444736000000000 + 1700000000000 * 10000
    saved = {'ExecutablePath': 'python.exe', 'CreationDate': '/Date(1700000000000)/'}
    current = {'executable': os.path.normcase(os.path.realpath('python.exe')), 'created': ticks}
    assert processes.matches(current, saved)
    assert not processes.matches({**current, 'created': ticks + 10000}, saved)


def test_key_aliases_are_not_reparsed_or_printed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runtime, 'ROOT', tmp_path)
    for key in ('KOSIS_API_KEY', 'NCP_CLOVA_API_KEY', 'NCP_API_KEY', 'CLOVA_STUDIO_API_KEY',
                'OPENAI_API_KEY', 'JEV_API_KEY', 'TYPESAFE_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / '.env').write_text('KOSIS_API_KEY="test-kosis!"\nNCP_API_KEY="test-ncp!"\nOPENAI_API_KEY="test-openai!"\n')
    assert runtime.valid_keys()
    runtime.diagnose()
    text = capsys.readouterr().out
    assert 'configured' in text and 'test-ncp!' not in text and 'test-openai!' not in text


def test_runtime_stops_before_installing_locked_native_packages(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(bootstrap, 'ROOT', tmp_path)
    monkeypatch.setattr(bootstrap, 'validate_files', lambda: None)
    monkeypatch.setattr(bootstrap, 'ensure_venv', lambda **_: tmp_path / '.venv/Scripts/python.exe')
    monkeypatch.setattr(bootstrap, 'ensure_python', lambda *_args, **_kwargs: events.append('pip'))
    monkeypatch.setattr(bootstrap, 'ensure_node', lambda **_: ('node', 'npm.cmd'))
    monkeypatch.setattr(bootstrap, 'ensure_frontend', lambda *_args, **_kwargs: events.append('npm'))
    monkeypatch.setattr(bootstrap, 'checked', lambda command, **_: events.append(command[-1]))
    (tmp_path / '.env.example').touch()
    monkeypatch.setattr(bootstrap.sys, 'argv', ['bootstrap.py', '--no-browser'])
    bootstrap.main()
    assert events.index('stop') < events.index('pip') < events.index('npm')


def test_configured_local_ports_are_allowed_without_allowing_other_hosts(monkeypatch):
    import account_auth
    monkeypatch.setenv('STATBRIDGE_UI_PORT', '5180')
    monkeypatch.setenv('STATBRIDGE_API_PORT', '8010')
    origins = account_auth.allowed_origins()
    assert 'http://127.0.0.1:5180' in origins and 'http://localhost:8010' in origins
    assert 'https://untrusted.example:5180' not in origins


def test_account_database_context_releases_windows_file_handle(tmp_path):
    import sqlite3
    from account_auth import AccountStore
    store = AccountStore(tmp_path / 'accounts.sqlite3')
    with store.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 3
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        connection.execute('SELECT 1')
    store.path.rename(tmp_path / 'renamed.sqlite3')


def test_missing_kosis_key_gives_an_actionable_recovery_message(monkeypatch):
    import bridge_api as api
    def missing(**kwargs):
        raise RuntimeError('KOSIS_API_KEY가 설정되지 않았습니다.')
    monkeypatch.setattr(api.service, 'get_statistics', missing)
    response = api.query(api.QueryRequest(query='DT_513Y001', period_start='2025-01-01',
                                          period_end='2025-12-31', execute=True))
    assert response['status'] == 'data_unavailable'
    assert '.env에 KOSIS_API_KEY' in response['summary']
    assert 'START_STATBRIDGE.cmd' in response['summary']
