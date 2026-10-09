"""Install or package this skill using only Python's standard library."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv
import zipfile

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
NAME = 'tiktok-review-harvest'


def distribution_files():
    # Explicitly exclude browser profiles, output, credentials and virtual environments.
    files = [ROOT / name for name in ('SKILL.md', 'requirements.txt', 'INSTALL.md', 'README.md')]
    files += sorted((ROOT / 'scripts').glob('*.py'))
    files += sorted((ROOT / 'references').glob('*.md'))
    return files


def install(destination, update=False, dependencies=False):
    destination = Path(destination).expanduser().resolve()
    if destination == ROOT or ROOT in destination.parents or destination in ROOT.parents:
        raise ValueError('Installation target must be separate from the source skill.')
    if destination.exists() and not update:
        raise ValueError('Target already exists. Use --update only if you intend to update this skill.')
    if destination.exists():
        skill = destination / 'SKILL.md'
        if not skill.is_file() or 'name: tiktok-review-harvest' not in skill.read_text(encoding='utf-8'):
            raise ValueError('Target is not an existing tiktok-review-harvest skill; choose a new directory.')
    for source in distribution_files():
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    print(f'Installed skill: {destination}')
    if dependencies:
        env = destination / '.venv'
        venv.EnvBuilder(with_pip=True).create(env)
        python = env / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(destination / 'requirements.txt')], check=True)
        print(f'Runtime: {python}')
    else:
        print('Dependencies were not changed. Follow INSTALL.md, or rerun from the extracted package with --update --deps.')
    return destination


def package(output):
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError('Package already exists; choose a new filename.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in distribution_files():
            archive.write(path, Path(NAME) / path.relative_to(ROOT))
    print(f'Package: {output}')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install skill for Codex/Claude, or build a clean ZIP')
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--host', choices=('codex', 'claude'))
    target.add_argument('--destination', help='Exact skill directory (not its parent)')
    target.add_argument('--package', help='ZIP output path')
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--deps', action='store_true', help='Create isolated Python environment and install dependencies')
    args = parser.parse_args(argv)
    try:
        if sys.version_info < (3, 10):
            raise ValueError('Python 3.10 or newer is required.')
        if args.package:
            if args.update or args.deps:
                raise ValueError('--update/--deps are installation options.')
            package(args.package)
        else:
            if args.destination:
                destination = Path(args.destination)
            else:
                base = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) if args.host == 'codex' else Path.home() / '.claude'
                destination = base / 'skills' / NAME
            install(destination, args.update, args.deps)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'[error] {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
