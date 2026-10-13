"""Start only this checkout's services; never kill an unrelated port owner."""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from windows_process import identity as process_identity, matches as identity_matches

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('STATBRIDGE_RUNTIME_STATE',str(ROOT / '.venv/cache/evaluation_runs' / 'portable_runtime.json')))


def free_port(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def healthy(url: str) -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=2) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def key_status() -> dict[str, bool]:
    from dotenv import dotenv_values
    values = dotenv_values(ROOT / '.env')
    def present(*names: str) -> bool:
        for name in names:
            value = str(os.environ.get(name, values.get(name)) or '').strip()
            if value and not any(token in value.lower() for token in ('your_', 'replace', '여기에', '<', '>')):
                return True
        return False
    return {'KOSIS': present('KOSIS_API_KEY'),
            'NCP': present('NCP_CLOVA_API_KEY', 'NCP_API_KEY', 'CLOVA_STUDIO_API_KEY'),
            'OpenAI': present('OPENAI_API_KEY'), 'Jev': present('JEV_API_KEY', 'TYPESAFE_API_KEY')}


def valid_keys() -> bool:
    status = key_status()
    return status['KOSIS'] and status['NCP']


def diagnose() -> None:
    print('[INFO] Project: ' + str(ROOT))
    for name, present in key_status().items():
        print(f'[INFO] {name} key: {"configured" if present else "not configured"}')
    print('[INFO] Keys are never displayed. Configure this project .env for the features you use.')
    print('[INFO] Missing NCP vectors use dictionary search; --build-index builds them explicitly.')


def vector_ready() -> bool:
    path = ROOT / '.venv/cache/vector_store_349'
    if not (path / 'chroma.sqlite3').exists():
        return False
    try:
        import chromadb
        sys.path.insert(0, str(ROOT / 'tools'))
        from build_stat_vector_index import documents
        dictionary = json.loads((ROOT / 'src/agent/stat_dictionary/stat_language_dictionary.json').read_text(encoding='utf-8'))
        db = chromadb.PersistentClient(path=str(path))
        for name, expected in documents(dictionary).items():
            rows = db.get_collection(name).get(include=['documents'])
            actual = dict(zip(rows['ids'], rows['documents']))
            if actual != {row['id']: row['document'] for row in expected}:
                return False
        return True
    except Exception:
        return False


def stop() -> None:
    if not STATE.exists():
        return
    state = json.loads(STATE.read_text(encoding='utf-8'))
    if state.get('root') and Path(state['root']).resolve() != ROOT.resolve():
        raise RuntimeError('Runtime state belongs to another project; no process was stopped.')
    remaining = []
    for service in state.get('services', []):
        pid = int(service['pid'])
        try:
            live = process_identity(pid)
        except OSError:
            remaining.append(service)
            continue
        if live is None or not identity_matches(live, service.get('identity')):
            # PID disappeared/reused: it is no longer this launcher's process.
            continue
        result = subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode != 0 and process_identity(pid) is not None:
            remaining.append(service)
    if remaining:
        STATE.write_text(json.dumps({**state, 'services': remaining}, ensure_ascii=False, indent=2), encoding='utf-8')
        raise RuntimeError('Could not stop a recorded service. Its identity was kept; close that service and retry.')
    STATE.unlink(missing_ok=True)


def start(api_port: int, ui_port: int, open_browser: bool, build_index: bool) -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    # Only previously recorded, still-identical processes belong to this launcher.
    stop()
    for port in (api_port, ui_port):
        if not free_port(port):
            raise RuntimeError(f'Port {port} is in use. Stop the other application first; no process was killed.')
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'src/agent'), str(ROOT / 'src/backend')])
    env['STATBRIDGE_DATA_DIR'] = str(ROOT / 'data/processed')
    env['STATBRIDGE_TABLES_DIR'] = str(ROOT / 'data/tables')
    env['STATBRIDGE_VECTOR_PATH'] = str(ROOT / '.venv/cache/vector_store_349')
    env['STATBRIDGE_API_PORT'] = str(api_port)
    env['STATBRIDGE_UI_PORT'] = str(ui_port)
    env['VITE_API_BASE_URL'] = '/api'
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    if ROOT.name == 'StatBridge-official' and ROOT.parent.name.lower() == 'statbridge1':
        env.setdefault('STATBRIDGE_COOKIE_NAME', 'statbridge_session_statbridge1')
    if not (Path(env['STATBRIDGE_VECTOR_PATH']) / 'chroma.sqlite3').is_file() and not build_index:
        env['STATBRIDGE_HYBRID_RETRIEVAL'] = '0'
        print('[INFO] No vector index yet. Dictionary search is available; use --build-index when NCP is configured.', flush=True)
    if build_index:
        print('[SETUP] Checking/building 349-table vectors. First build calls the embedding API and can take several minutes.', flush=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/build_stat_vector_index.py')], cwd=ROOT, env=env, check=True)
        subprocess.run([sys.executable, str(Path(__file__)), 'check-index'], cwd=ROOT, env=env, check=True)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    services: list[dict] = []
    launched = []
    commands = [
        ('agent', [sys.executable, '-m', 'uvicorn', 'bridge_api:app', '--host', '127.0.0.1', '--port', str(api_port)], ROOT / 'src/agent'),
        ('mcp', [sys.executable, str(ROOT / 'src/backend/server.py')], ROOT),
        ('frontend', ['cmd.exe', '/d', '/c', 'npm.cmd', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', str(ui_port), '--strictPort'], ROOT / 'src/agent/frontend'),
    ]
    try:
        for name, command, cwd in commands:
            with (STATE.parent / f'{name}.log').open('w', encoding='utf-8') as log:
                # A named pipe held by a hidden cmd keeps the stdio MCP server alive.
                if name == 'mcp':
                    command = [sys.executable, str(ROOT / 'scripts/windows/hold_mcp.py')]
                process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            launched.append(process)
            identity = process_identity(process.pid)
            if process.poll() is not None or identity is None:
                raise RuntimeError(f'{name} exited; inspect {STATE.parent / (name + ".log")}')
            services.append({'name': name, 'pid': process.pid, 'identity': identity})
            STATE.write_text(json.dumps({'root': str(ROOT.resolve()), 'services': services}, ensure_ascii=False, indent=2), encoding='utf-8')
        for name, url in [('Agent', f'http://127.0.0.1:{api_port}/api/health'), ('UI', f'http://127.0.0.1:{ui_port}/')]:
            deadline = time.monotonic() + 60
            while not healthy(url):
                if any(process.poll() is not None for process in launched):
                    raise RuntimeError(f'A service exited during startup; inspect {STATE.parent}.')
                if time.monotonic() > deadline:
                    raise RuntimeError(f'{name} failed to start; inspect .venv/cache/evaluation_runs/*.log')
                time.sleep(.5)
            print(f'[OK] {name}: {url}', flush=True)
        if open_browser:
            url = f'http://127.0.0.1:{ui_port}/'
            try:
                if os.name == 'nt':
                    os.startfile(url)
                    print('[OK] Requested the default browser to open ' + url, flush=True)
                elif not webbrowser.open(url):
                    print('[INFO] Open this address in your browser: ' + url, flush=True)
            except OSError:
                print('[INFO] Browser could not open automatically. Services remain running. Open ' + url, flush=True)
    except BaseException:
        # The Popen handles identify these exact children, even before state was saved.
        for process in launched:
            if process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        stop()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop', 'check-keys', 'check-index', 'diagnose'])
    parser.add_argument('--api-port', type=int, default=8000)
    parser.add_argument('--ui-port', type=int, default=5173)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--build-index', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'diagnose':
            diagnose()
        elif args.action == 'check-index':
            raise SystemExit(0 if vector_ready() else 1)
        elif args.action == 'check-keys':
            raise SystemExit(0 if valid_keys() else 1)
        elif args.action == 'stop':
            stop()
        else:
            start(args.api_port, args.ui_port, not args.no_browser, args.build_index)
    except Exception as exc:
        # Do not print exception strings from API clients; they can contain keys.
        if isinstance(exc, RuntimeError):
            print(f'[ERROR] {exc}', file=sys.stderr)
        else:
            print(f'[ERROR] Setup failed ({type(exc).__name__}); check service logs.', file=sys.stderr)
        raise SystemExit(1)
