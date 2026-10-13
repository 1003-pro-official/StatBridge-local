"""Existing installations must not hide missing or incompatible requirements."""
import importlib.util
import json
import subprocess
from importlib.metadata import PackageNotFoundError
from pathlib import Path

spec = importlib.util.spec_from_file_location('launcher_dependencies', Path(__file__).resolve().parents[1] / 'scripts/windows/check_dependencies.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_missing_and_incompatible_versions_require_install():
    def lookup(name):
        if name == 'missing':
            raise PackageNotFoundError(name)
        return '1.0'
    errors = module.requirement_errors(['missing>=1', 'present>=2', 'compatible>=1', 'ignored; python_version < "3.0"'], lookup)
    assert len(errors) == 2
    assert errors[0] == 'missing: missing'
    assert errors[1].startswith('present:')


def test_frontend_install_stamp_and_version_changes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    check = root / 'scripts/windows/check_frontend.cjs'
    package = tmp_path / 'package.json'
    package.write_text(json.dumps({'dependencies': {'example': '1.0.0'}}))
    (tmp_path / 'package-lock.json').write_text(json.dumps({'packages': {'node_modules/example': {'version': '1.0.0'}}}))
    installed = tmp_path / 'node_modules/example/package.json'
    installed.parent.mkdir(parents=True)
    installed.write_text(json.dumps({'version': '1.0.0'}))
    def run(mode='check'):
        return subprocess.run(['node', str(check), str(tmp_path), mode], capture_output=True).returncode
    assert run() == 1  # A pre-existing install was never verified.
    assert run('record') == 0
    assert run() == 0
    package.write_text(package.read_text() + '\n')
    assert run() == 1  # A manifest update invalidates the prior stamp.
    assert run('record') == 0
    installed.write_text(json.dumps({'version': '0.9.0'}))
    assert run('record') == 1  # Never certify a mismatched installed package.
