"""Run the pinned protocol fixtures with the packaged Swift optimization."""
from pathlib import Path
import subprocess
import sys

runtime = Path(__file__).resolve().parent / 'runtime'
paths = [runtime / 'tests/host' / name for name in
         ('check-steam-signin-native.py', 'check-steam-library.py')]
before = "[SWIFTC, '-parse-as-library'"
after = "[SWIFTC, '-O', '-parse-as-library'"
sources = []
for path in paths:
    source = path.read_text()
    if source.count(before) != 1:
        raise SystemExit(f'Unexpected pinned test compiler invocation: {path.name}')
    sources.append(source.replace(before, after, 1))
for path, source in zip(paths, sources):
    path.write_text(source)
    subprocess.run([sys.executable, str(path)], cwd=runtime, check=True)
for name in ('check-dock-path.py', 'check-gamepad.py'):
    subprocess.run([sys.executable, str(runtime / 'tests/host' / name)], cwd=runtime, check=True)
