#!/usr/bin/env python3
"""Compile the actual patched Wine placement functions with ASan/UBSan."""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

DRIVER = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('wine_fixes', DRIVER / 'wine-build-fixes.py')
fixes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixes)
source = Path(sys.argv[1]) if len(sys.argv) > 1 else DRIVER / 'runtime/build/ntdll-unix/virtual_ios.c'
patched = fixes.repair_virtual_source(source.read_text(encoding='utf-8'))


def function(marker):
    start = patched.index(marker)
    end = patched.index('\n}\n', start) + 3
    return patched[start:end]


functions = '\n\n'.join([function('static int ios_exe_win_claim('),
                           function('static BOOL ios_exe_win_fixed_main(')])
harness = (DRIVER / 'tests/fixed_image_harness.c').read_text(encoding='utf-8')
assert harness.count('/* ACTUAL_WINE_FUNCTIONS */') == 1
harness = harness.replace('/* ACTUAL_WINE_FUNCTIONS */', functions)
compiler = os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
if not compiler:
    raise SystemExit('A host C compiler is required for the fixed-image regression checks')
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    c = root / 'fixed-image.c'
    exe = root / ('fixed-image.exe' if os.name == 'nt' else 'fixed-image')
    c.write_text(harness, encoding='utf-8')
    subprocess.run([compiler, '-std=c11', '-D_DEFAULT_SOURCE', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-pthread', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
