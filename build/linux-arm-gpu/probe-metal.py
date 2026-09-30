#!/usr/bin/env python3
"""Require a real Metal-backed ANGLE context, rather than software fallback."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1]).resolve()
devices = subprocess.run(['system_profiler', 'SPDisplaysDataType'], capture_output=True,
                         text=True, timeout=30)
(root / 'host-displays.log').write_text(devices.stdout + devices.stderr)
print(devices.stdout + devices.stderr)
with tempfile.TemporaryDirectory(prefix='my-pc-metal-capability-') as temporary:
    folder = pathlib.Path(temporary)
    source = folder / 'capability.m'
    source.write_text('''#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
int main(void) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        printf("MYPC_HOST_METAL_AVAILABLE=%d\\n", device != nil);
        if (device) { printf("MYPC_HOST_METAL_DEVICE=%s\\n", device.name.UTF8String); }
    }
    return 0;
}
''')
    subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-framework', 'Foundation',
                    '-framework', 'Metal', str(source), '-o', str(folder / 'capability')],
                   check=True, timeout=30)
    capability = subprocess.run([str(folder / 'capability')], text=True,
                                capture_output=True, check=True, timeout=30)
    (root / 'host-metal.log').write_text(capability.stdout + capability.stderr)
    print(capability.stdout + capability.stderr)
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
assert 'ANGLE' in renderer and 'Metal' in renderer, 'No verified Metal ANGLE renderer; inspect host-displays.log for GPU availability'
assert not any(word in renderer.lower() for word in ['swiftshader', 'llvmpipe', 'software']), renderer
print('PASS: QEMU headless EGL creates an ANGLE Metal context on macOS; guest/iPhone GPU tests still required')
