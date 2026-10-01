#!/usr/bin/env python3
"""Test the framework set shipped in the IPA, including missing-provider recovery."""
import importlib.util
import pathlib
import shutil
import subprocess
import sys

source, destination = map(lambda p: pathlib.Path(p).resolve(), sys.argv[1:])
assert not destination.exists(), 'Use a fresh test bundle so extra frameworks cannot mask omissions'
spec = importlib.util.spec_from_file_location('framework_closure',
    pathlib.Path(__file__).resolve().parents[1] / 'linux-arm/framework-closure.py')
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)
names = closure.copy_frameworks(source / 'Frameworks', destination / 'Frameworks',
                                metal=True, platform='MACOS')
shutil.copytree(source / 'qemu', destination / 'qemu')
shutil.copy2(source / 'host-launcher', destination / 'host-launcher')
for name in names:
    subprocess.run(['codesign', '--force', '--sign', '-',
                    str(destination / 'Frameworks' / name)], check=True)
subprocess.run(['codesign', '--force', '--sign', '-', str(destination / 'host-launcher')], check=True)
command = [str(destination / 'host-launcher'),
           str(destination / 'Frameworks/qemu-aarch64-softmmu.framework/Versions/A/qemu-aarch64-softmmu'),
           '-machine', 'none', '-nodefaults', '-S', '-display', 'egl-headless,gl=es',
           '-qmp', 'stdio', '-L', str(destination / 'qemu')]
for name in closure.ANGLE_PROVIDERS:
    provider = destination / 'Frameworks' / name
    hidden = destination / (name + '.missing-test')
    provider.rename(hidden)
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=30,
                                input='{"execute":"quit"}\n')
        # A SIGABRT, signal death or QEMU startup must fail this control.
        assert result.returncode == 1, (name, result.returncode, result.stderr)
        assert 'Cannot load Metal graphics provider' in result.stderr, result.stderr
        assert 'MYPC_METAL_PROVIDER_PREFLIGHT_OK' not in result.stderr
        print('MYPC_MISSING_PROVIDER_RECOVERY_OK ' + name, flush=True)
    finally:
        hidden.rename(provider)
print('MYPC_PACKAGED_METAL_FRAMEWORKS ' + ', '.join(names), flush=True)
