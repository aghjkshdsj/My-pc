#!/usr/bin/env python3
"""Require a real Metal-backed ANGLE context, rather than software fallback."""
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1]).resolve()
command = [str(root / 'host-launcher'),
           str(root / 'Frameworks/qemu-aarch64-softmmu.framework/Versions/A/qemu-aarch64-softmmu'),
           '-machine', 'none', '-nodefaults', '-S', '-display', 'egl-headless,gl=es',
           '-qmp', 'stdio', '-L', str(root / 'qemu')]
result = subprocess.run(command, input='{"execute":"qmp_capabilities"}\n{"execute":"quit"}\n',
                        text=True, capture_output=True, timeout=60)
log = result.stdout + result.stderr
(root / 'metal-probe.log').write_text(log)
print(log)
renderer = next((line for line in log.splitlines() if line.startswith('MYPC_HOST_GL_RENDERER=')), '')
assert result.returncode == 0, f'QEMU EGL initialization failed: {result.returncode}'
assert 'ANGLE' in renderer and 'Metal' in renderer, 'No verified Metal ANGLE renderer'
assert not any(word in renderer.lower() for word in ['swiftshader', 'llvmpipe', 'software']), renderer
print('PASS: QEMU headless EGL creates an ANGLE Metal context on macOS; guest/iPhone GPU tests still required')
