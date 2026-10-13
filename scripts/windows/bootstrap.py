"""Portable Windows setup. Runs with stdlib before installing project packages."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PYTHON_VERSIONS = {(3, 11), (3, 12), (3, 13)}
IMPORTS = ['mcp', 'pandas', 'requests', 'dotenv', 'fastapi', 'uvicorn', 'chromadb',
           'langgraph', 'plotly', 'matplotlib', 'pypdf', 'mcp.server', 'numpy']


def run(command, *, cwd=ROOT, env=None, capture=False):
    return subprocess.run(command, cwd=cwd, env=env, check=False,
                          capture_output=capture, text=True, encoding='utf-8', errors='replace')


def checked(command, **kwargs):
    result = run(command, **kwargs)
    if result.returncode:
        raise RuntimeError(f'Command failed (exit {result.returncode}). See the setup output above.')
    return result


def python_usable(executable, venv):
    if not executable.is_file():
        return False
    script = ('import json,sys,struct;print(json.dumps({"version":list(sys.version_info[:2]),'
              '"bits":struct.calcsize("P")*8,"prefix":sys.prefix,"base":sys.base_prefix}))')
    result = run([str(executable), '-c', script], capture=True)
    try:
        info = json.loads(result.stdout)
        return (result.returncode == 0 and tuple(info['version']) in PYTHON_VERSIONS
                and info['bits'] == 64 and Path(info['prefix']).resolve() == venv.resolve()
                and info['prefix'] != info['base'])
    except (ValueError, KeyError, TypeError):
        return False


def ensure_venv(*, repair=True):
    venv = ROOT / '.venv'
    executable = venv / 'Scripts/python.exe'
    if python_usable(executable, venv):
        return executable
    if not repair:
        raise RuntimeError('The project .venv is missing, copied from another PC, or incompatible. Run START_STATBRIDGE.cmd.')
    # Back up the entry; never recursively remove a copied environment/junction.
    if os.path.lexists(venv):
        allowed = ROOT.parent if ROOT.name == 'StatBridge-official' else ROOT
        if not venv.resolve().is_relative_to(allowed.resolve()):
            raise RuntimeError('The .venv points outside this project. Keep its target and replace the local link manually.')
        backup = ROOT / ('.venv.invalid.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        if not backup.absolute().is_relative_to(ROOT.absolute()):
            raise RuntimeError('Invalid virtual environment backup path.')
        venv.rename(backup)
        print('[SETUP] Preserved incompatible .venv as ' + backup.name, flush=True)
    base = Path(sys._base_executable)
    checked([str(base), '-m', 'venv', str(venv)])
    if not python_usable(executable, venv):
        raise RuntimeError('Could not create a working 64-bit Python 3.11~3.13 environment.')
    return executable


def check_python(executable):
    versions = run([str(executable), str(ROOT / 'scripts/windows/check_dependencies.py')])
    if versions.returncode:
        return False
    imports = run([str(executable), '-c', ';'.join('import ' + name for name in IMPORTS)
                   + ';from mcp.server import MCPServer'], capture=True)
    if imports.returncode:
        print('[WARN] A Python runtime import failed:\n' + imports.stderr.strip(), flush=True)
    return versions.returncode == imports.returncode == 0


def ensure_python(executable, *, repair=True):
    if check_python(executable):
        return
    if not repair:
        raise RuntimeError('Python packages are missing or incompatible. Run START_STATBRIDGE.cmd.')
    checked([str(executable), '-m', 'ensurepip', '--upgrade'])
    checked([str(executable), '-m', 'pip', 'install', '--disable-pip-version-check',
             '--upgrade', '-r', str(ROOT / 'src/backend/requirements.txt')])
    if not check_python(executable):
        raise RuntimeError('Python dependency verification failed after installation. See the errors above.')


def node_supported(version):
    try:
        major, minor = map(int, version.strip().lstrip('v').split('.')[:2])
    except ValueError:
        return False
    return major == 20 and minor >= 19 or major >= 22 and (major > 22 or minor >= 12)


def find_node():
    for folder in [Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'nodejs',
                   Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/nodejs']:
        if (folder / 'node.exe').is_file():
            os.environ['PATH'] = str(folder) + os.pathsep + os.environ.get('PATH', '')
    return shutil.which('node'), shutil.which('npm.cmd')


def ensure_node(*, repair=True):
    node, npm = find_node()
    version = run([node, '--version'], capture=True).stdout if node else ''
    if node and npm and node_supported(version):
        print('[OK] Node.js ' + version.strip(), flush=True)
        return node, npm
    if repair and shutil.which('winget'):
        checked(['winget', 'install', '--id', 'OpenJS.NodeJS.LTS', '-e', '--silent',
                 '--accept-package-agreements', '--accept-source-agreements'])
        node, npm = find_node()
        if node and npm and node_supported(run([node, '--version'], capture=True).stdout):
            return node, npm
    raise RuntimeError('Install 64-bit Node.js LTS (20.19+ or 22.12+) with npm, then run START_STATBRIDGE.cmd.')


def npm_command(npm, *args):
    # find_node has set PATH. Using the batch name avoids cmd's double-quote
    # stripping around "C:\Program Files\nodejs\npm.cmd".
    return ['cmd.exe', '/d', '/c', Path(npm).name, *args]


def ensure_frontend(node, npm, *, repair=True):
    frontend = ROOT / 'src/agent/frontend'
    check = [node, str(ROOT / 'scripts/windows/check_frontend.cjs'), str(frontend)]
    native = [node, str(frontend / 'node_modules/vite/bin/vite.js'), '--version']
    if run(check).returncode == 0 and run(native).returncode == 0:
        return
    if not repair:
        raise RuntimeError('Frontend packages/native binaries are missing or from another PC. Run START_STATBRIDGE.cmd.')
    # npm ci uses the lock and replaces copied node_modules, including native binaries.
    if not (frontend / 'package-lock.json').is_file():
        raise RuntimeError('package-lock.json is missing. Re-extract the complete project ZIP.')
    env = os.environ.copy()
    env.pop('NODE_ENV', None)
    checked(npm_command(npm, 'ci', '--include=dev', '--include=optional'), cwd=frontend, env=env)
    checked([*check, 'record'])
    checked(native)


def validate_files():
    for relative in ['src/backend/server.py', 'src/agent/bridge_api.py',
                     'data/processed/bok_table_master.csv', 'src/backend/requirements.txt',
                     'src/agent/frontend/package-lock.json', '.env.example']:
        if not (ROOT / relative).is_file():
            raise RuntimeError('Missing package file: ' + relative + '. Extract the complete ZIP before running.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Diagnose without installing or starting services')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--build-index', action='store_true', help='Explicitly build optional NCP vectors')
    args = parser.parse_args()
    if sys.version_info[:2] not in PYTHON_VERSIONS or struct.calcsize('P') != 8:
        raise RuntimeError('Use 64-bit Python 3.11, 3.12 or 3.13.')
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    validate_files()
    print('[1/4] Checking machine-local Python environment', flush=True)
    executable = ensure_venv(repair=not args.check)
    runtime = [str(executable), str(ROOT / 'scripts/windows/portable_runtime.py')]
    if not args.check:
        # Windows keeps native .pyd/.node files locked while API/Vite run.
        # Release only this project's recorded services BEFORE pip/npm changes.
        stop_env = os.environ.copy()
        stop_env.pop('STATBRIDGE_RUNTIME_STATE', None)
        checked([*runtime, 'stop'], env=stop_env)
        if os.getenv('STATBRIDGE_RUNTIME_STATE'):
            checked([*runtime, 'stop'])
    ensure_python(executable, repair=not args.check)
    print('[2/4] Checking Node.js and locked frontend packages', flush=True)
    node, npm = ensure_node(repair=not args.check)
    ensure_frontend(node, npm, repair=not args.check)
    print('[3/4] Checking project settings', flush=True)
    env_path = ROOT / '.env'
    if not env_path.is_file() and not args.check:
        shutil.copyfile(ROOT / '.env.example', env_path)
    checked([*runtime, 'diagnose'])
    if args.check:
        print('[OK] Environment check complete. No services were started.', flush=True)
        return
    default_api, default_ui = (8001, 5174) if ROOT.name == 'StatBridge-official' and ROOT.parent.name.lower() == 'statbridge1' else (8000, 5173)
    command = [*runtime, 'start', '--api-port', os.getenv('STATBRIDGE_API_PORT', str(default_api)),
               '--ui-port', os.getenv('STATBRIDGE_UI_PORT', str(default_ui))]
    if args.no_browser or os.getenv('STATBRIDGE_NO_BROWSER'):
        command.append('--no-browser')
    if args.build_index:
        command.append('--build-index')
    print('[4/4] Starting verified services', flush=True)
    checked(command)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print('[ERROR] ' + str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)
