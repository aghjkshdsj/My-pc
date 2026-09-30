#!/usr/bin/env python3
"""Run the existing Steam startup gate with isolated virgl/Metal arguments."""
import os
import pathlib
import subprocess
import sys
import tempfile

guest, runtime = map(lambda p: pathlib.Path(p).resolve(), sys.argv[1:3])
source = pathlib.Path('build/linux-arm/smoke-guest.py').read_text()
anchor = 'f"virtio-gpu-pci,xres={display_width},yres={display_height}"'
assert source.count(anchor) == 1
source = source.replace(anchor, 'f"virtio-gpu-gl-pci,xres={display_width},yres={display_height}"')
anchor = '            if args.display:\n'
assert source.count(anchor) == 2
source = source.replace(anchor, '''            command[command.index('-display') + 1] = 'egl-headless,gl=es'
''' + anchor, 1)
# The detailed serial log stays local. Publish bounded status and GPU metadata.
with tempfile.TemporaryDirectory() as temporary:
    probe = pathlib.Path(temporary, 'gpu-steam-probe.py')
    probe.write_text(source)
    environment = os.environ.copy()
    environment['MYPC_GPU_FRAME_PATH'] = str(guest / 'steam-frame.bgra')
    with (guest / 'host-steam.log').open('w') as output:
        result = subprocess.run([sys.executable, str(probe), str(guest), '--cpus', '6',
            '--verify-cpu-count', '--steam', '--expect-existing', '--display',
            '--launcher', str(runtime / 'gpu-host-launcher'),
            '--library', str(runtime / 'Frameworks/qemu-aarch64-softmmu.framework/Versions/A/qemu-aarch64-softmmu')],
            stdout=output, stderr=subprocess.STDOUT, env=environment)
    content = (guest / 'boot-4.log').read_text(errors='replace')
    import json, re
    for item in re.findall(r'MYPC_STEAM_GPU_INFO (\{[^\r\n]{1,1024}\})', content):
        state = json.loads(item)
        if set(state) == {'renderer', 'compositing', 'webgl_status', 'webgl_renderer', 'shader_readback_ok', 'accelerated'}:
            print('MYPC_STEAM_GPU_INFO ' + json.dumps(state), flush=True)
    print('MYPC_STEAM_GPU_RESULT ' + json.dumps({
        'host_exit_success': result.returncode == 0,
        'metal': 'MYPC_HOST_GL_RENDERER=ANGLE' in content and 'ANGLE Metal Renderer' in content,
        'cef_accelerated': 'MYPC_STEAM_GPU_CEF_OK' in content,
        'login_ready': 'MYPC_GUEST_STEAM_WINDOW_OK' in content,
        'segfaults': len(re.findall(r'Segmentation fault|received signal SIGSEGV', content)),
        'missing_cdp_endpoint': 'GPU diagnostic endpoint must be guest loopback' in content,
        'cdp_method_rejected': 'CEF rejected the GPU diagnostic method' in content,
        'readback_error': 'MYPC_GPU_RGBA_READBACK_ERROR' in content,
    }), flush=True)
    assert result.returncode == 0, 'Full Steam Metal guest gate failed; no GPU-ready release'
    assert 'MYPC_STEAM_GPU_CEF_OK' in content, 'Steam did not prove actual GPU acceleration'
    assert 'MYPC_HOST_GL_RENDERER=ANGLE' in content and 'ANGLE Metal Renderer' in content
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('gpu_readback', 'build/linux-arm-gpu/probe-guest.py')
    module = module_from_spec(spec); spec.loader.exec_module(module)
    stats = module.frame_stats(guest / 'steam-frame.bgra')
    assert stats and (stats['width'], stats['height']) == (1280, 800)
    print('MYPC_STEAM_GPU_FRAME_OK=1280x800', flush=True)
print('PASS: full Steam responsive login, actual virgl CEF compositing/WebGL, Metal display bridge and clean shutdown; no account or iPhone timing test')
