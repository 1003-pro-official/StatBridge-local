"""Check the installed environment against the launcher requirements."""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import subprocess
import sys

from pip._vendor.packaging.requirements import Requirement


def requirement_errors(lines, lookup=version):
    errors = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            installed = lookup(requirement.name)
        except PackageNotFoundError:
            errors.append(f'{requirement.name}: missing')
            continue
        if not requirement.specifier.contains(installed):
            errors.append(f'{requirement.name}: {installed} does not satisfy {requirement.specifier}')
    return errors


def main():
    requirements = Path(__file__).resolve().parents[2] / 'src/backend/requirements.txt'
    errors = requirement_errors(requirements.read_text(encoding='utf-8').splitlines())
    for error in errors:
        print(error)
    if errors:
        return 1
    return subprocess.run([sys.executable, '-m', 'pip', 'check'], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
