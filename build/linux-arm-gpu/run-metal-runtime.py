#!/usr/bin/env python3
"""Test production Metal boot-update arguments; publish bounded results only."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('guest', type=pathlib.Path)
parser.add_argument('runtime', type=pathlib.Path)
parser.add_argument('--steam', action='store_true')
parser.add_argument('--legacy', action='store_true', help='Migration/input only on Linux QEMU, without a Metal host')
args = parser.parse_args()
guest, runtime = args.guest.resolve(), args.runtime.resolve()
manifest = json.loads((guest / 'graphics.json').read_text())
assert hashlib.sha256((guest / 'Image').read_bytes()).hexdigest() == manifest['kernelSHA256']
assert hashlib.sha256((guest / 'graphics-initrd.img').read_bytes()).hexdigest() == manifest['initrdSHA256']
assert (guest / 'graphics-initrd.img').stat().st_size == manifest['initrdBytes']
source = pathlib.Path('build/linux-arm/smoke-guest.py').read_text()
anchor = 'str(guest / "initrd.img")'
assert source.count(anchor) == 1
source = source.replace(anchor, 'str(guest / "graphics-initrd.img")')
anchor = '            if args.verify_cpu_count:\n'
assert source.count(anchor) == 2
source = source.replace(anchor, '''            command[command.index('-append') + 1] += ' my_pc_graphics=virgl'
''' + anchor, 1)
if not args.legacy:
    anchor = 'f"virtio-gpu-pci,xres={display_width},yres={display_height}"'
    assert source.count(anchor) == 1
    source = source.replace(anchor, 'f"virtio-gpu-gl-pci,xres={display_width},yres={display_height}"')
    anchor = '            if args.display:\n'
    assert source.count(anchor) == 2
    source = source.replace(anchor, '''            command[command.index('-display') + 1] = 'egl-headless,gl=es'
''' + anchor, 1)
with tempfile.TemporaryDirectory() as temporary:
    probe = pathlib.Path(temporary, 'metal-runtime.py'); probe.write_text(source)
    command = [sys.executable, str(probe), str(guest), '--cpus', '6', '--expect-existing',
               '--steam' if args.steam else '--desktop']
    if not args.legacy:
        command += ['--verify-cpu-count', '--display', '--launcher', str(runtime / 'host-launcher'),
                    '--library', str(runtime / 'Frameworks/qemu-aarch64-softmmu.framework/Versions/A/qemu-aarch64-softmmu')]
    with (guest / 'metal-host.log').open('w') as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
    content = (guest / ('boot-4.log' if args.steam else 'boot-3.log')).read_text(errors='replace')
    for item in re.findall(r'MYPC_STEAM_GPU_INFO (\{[^\r\n]{1,1024}\})', content):
        state = json.loads(item)
        if set(state) == {'renderer', 'compositing', 'webgl_status', 'webgl_renderer', 'shader_readback_ok', 'accelerated'}:
            print('MYPC_STEAM_GPU_INFO ' + json.dumps(state), flush=True)
    summary = {'host_success': result.returncode == 0,
               'hook_seen': 'MYPC_GRAPHICS_HOOK_SEEN=1' in content,
               'update_phases': re.findall(r'MYPC_GRAPHICS_UPDATE_PHASE=(shell-ready|validate-root|verify-payload|replace-launcher|sync)', content)[-8:],
               'tool_not_found': bool(re.search(r'(?:my-pc-graphics|ld-linux)[^\r\n]*not found', content)),
               'shell_trap_error': bool(re.search(r'(?:bad trap|invalid signal specification)', content)),
               'unset_parameter': 'parameter not set' in content or 'unbound variable' in content,
               'update_ok': 'MYPC_GRAPHICS_UPDATE_OK=1' in content,
               'update_failed': 'MYPC_GRAPHICS_UPDATE_FAILED' in content,
               'cpu_count_verified': 'MYPC_LINUX_CPU_COUNT=6' in content,
               'metal': 'ANGLE Metal Renderer' in content,
               'cef_gpu': 'MYPC_STEAM_GPU_CEF_OK' in content,
               'legacy_migration_only': args.legacy}
    print('MYPC_METAL_RUNTIME_RESULT ' + json.dumps(summary), flush=True)
    assert summary['host_success'] and summary['update_ok'] and not summary['update_failed']
    if not args.legacy:
        assert summary['metal'] and summary['cpu_count_verified']
    if args.steam:
        assert summary['cef_gpu'], 'Steam GPU fallback cannot pass the release gate'
print('PASS: reserved launcher update, desktop/input or full Steam gate, persistence and clean shutdown')
