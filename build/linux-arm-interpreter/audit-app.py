#!/usr/bin/env python3
"""Audit the separate iPhone product, not merely its visible controls."""
import json
import pathlib
import plistlib
import subprocess
import sys

app = pathlib.Path(sys.argv[1])
entitlements = pathlib.Path('app/Interpreter/Interpreter.entitlements')
assert plistlib.loads(entitlements.read_bytes()) == {}, 'Unexpected interpreter entitlements'
info = plistlib.loads((app / 'Info.plist').read_bytes())
assert info['CFBundleIdentifier'] == 'com.aghjkshdsj.MyPC.Interpreter'
assert not info.get('CFBundleURLTypes') and not info.get('LSApplicationQueriesSchemes')
manifest = json.loads((app / 'runtime-backend.json').read_text())
assert manifest['backend'] == 'tcti' and manifest['requiresJIT'] is False
for item in app.rglob('*'):
    assert not any(word in item.name.lower() for word in ('stik', 'wine', 'fex', 'madeira-jit')), item.name
binaries = [app / info['CFBundleExecutable']]
for framework in (app / 'Frameworks').glob('*.framework'):
    binary_name = plistlib.loads((framework / 'Info.plist').read_bytes())['CFBundleExecutable']
    binaries.append(framework / binary_name)
for binary in binaries:
    subprocess.run(['xcrun', 'lipo', str(binary), '-verify_arch', 'arm64'], check=True)
    platform = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], text=True)
    assert any(line.strip() == 'platform IOS' for line in platform.splitlines()), binary.name
    dependencies = subprocess.check_output(['otool', '-L', str(binary)], text=True)
    assert '/PrivateFrameworks/' not in dependencies, binary.name
    symbols = subprocess.check_output(['nm', '-a', str(binary)], text=True, stderr=subprocess.DEVNULL).lower()
    assert not any(name in symbols for name in ('jit_check_debugged', 'jit_install_trap_handler', 'stikjithelper', 'wine_process_', 'wineserver_', 'fexbridge')), binary.name
print('PASS: interpreter iPhone product, empty entitlements, no Wine/FEX/StikDebug app code or private frameworks')
