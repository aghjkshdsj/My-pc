#!/usr/bin/env python3
"""Test production Metal boot-update arguments; publish bounded results only."""
import argparse
import hashlib
import importlib.util
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
parser.add_argument('--hardware', action='store_true')
parser.add_argument('--legacy', action='store_true', help='Migration/input only on Linux QEMU, without a Metal host')
parser.add_argument('--expect-update-reuse', action='store_true')
args = parser.parse_args()
if args.hardware:
    spec = importlib.util.spec_from_file_location('hardware_control_ci', 'build/linux-arm-gpu/hardware-control-ci.py')
    harness = importlib.util.module_from_spec(spec); spec.loader.exec_module(harness)
guest, runtime = args.guest.resolve(), args.runtime.resolve()
manifest = json.loads((guest / 'graphics.json').read_text())
assert hashlib.sha256((guest / 'Image').read_bytes()).hexdigest() == manifest['kernelSHA256']
assert hashlib.sha256((guest / 'graphics-initrd.img').read_bytes()).hexdigest() == manifest['initrdSHA256']
assert (guest / 'graphics-initrd.img').stat().st_size == manifest['initrdBytes']
source = pathlib.Path('build/linux-arm/smoke-guest.py').read_text()
anchor = 'str(guest / "initrd.img")'
assert source.count(anchor) == 1
source = source.replace(anchor, 'str(guest / "graphics-initrd.img")')
anchor = '            if args.launcher:\n'
assert source.count(anchor) == 1
source = source.replace(anchor, '''            # Match the shipping disk path, cache size and six-core CPU model.
            drive = command.index('-drive'); del command[drive:drive + 2]
            command += ['-object', 'iothread,id=linux-disk-io,poll-max-ns=0',
                '-blockdev', json.dumps({'driver': 'file', 'filename': str(guest / 'rootfs.raw'),
                    'node-name': 'linux-file', 'aio': 'threads',
                    'cache': {'direct': False, 'no-flush': False}}),
                '-blockdev', json.dumps({'driver': 'raw', 'file': 'linux-file', 'node-name': 'linux-root'}),
                '-device', 'virtio-blk-pci,drive=linux-root,iothread=linux-disk-io,num-queues=6']
            command[command.index('-accel') + 1] = 'tcg,thread=multi,tb-size=256'
''' + anchor)
anchor = '            if args.verify_cpu_count:\n'
assert source.count(anchor) == 2
source = source.replace(anchor, '''            command[command.index('-append') + 1] += ' my_pc_graphics=virgl'
''' + anchor, 1)
if args.hardware:
    source = source.replace(" my_pc_graphics=virgl'", " my_pc_graphics=virgl my_pc_hardware_ci=1'")
    anchor = "                            if args.steam and 'MYPC_GUEST_STEAM_FAILED' in log.read_text(errors=\"replace\"):\n"
    assert source.count(anchor) == 1
    source = source.replace(anchor, "                            if 'MYPC_HARDWARE_RUNTIME_FAILED=1' in log.read_text(errors=\"replace\"):\n"
        "                                raise RuntimeError('Hardware diagnostic failed')\n" + anchor)
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
    if args.hardware:
        assert not args.steam, 'Hardware control CI requires the account-free desktop gate'
        command += ['--controller', '--hardware-control-ci', str(pathlib.Path('build/linux-arm-gpu/hardware-control-ci.py').resolve())]
    with (guest / 'metal-host.log').open('w') as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
    content = (guest / ('boot-4.log' if args.steam else 'boot-3.log')).read_text(errors='replace')
    host_content = (guest/'metal-host.log').read_text(errors='replace')
    if result.returncode != 0:
        # Export only predefined booleans/stages. Keep raw guest/host output
        # private to the runner, including profiles, paths and error strings.
        evidence = content + host_content
        if args.hardware:
            for diagnostic_source, diagnostic_content in (('GUEST', content), ('HOST', host_content)):
                prefix = f'MYPC_HARDWARE_{diagnostic_source}_FAILURE '
                for line in diagnostic_content.splitlines():
                    if not line.startswith(prefix) or len(line) > 2048: continue
                    try: bounded = harness.validated_failure(json.loads(line[len(prefix):]))
                    except (ValueError, KeyError, TypeError): continue
                    print(prefix + json.dumps(bounded, sort_keys=True), flush=True)
        patterns = {'controller_service_ready':'MYPC_CONTROLLER_READY=1',
            'controller_observer_ready':'MYPC_CONTROLLER_OBSERVER_READY=1',
            'controller_passed':'MYPC_CONTROLLER_EVDEV_ANALOG_BUTTONS_HOTPLUG_OK=1',
            'hardware_keys_ready':'MYPC_HARDWARE_TEST_READY=1',
            'hardware_failed':'MYPC_HARDWARE_RUNTIME_FAILED=1',
            'hardware_control_failed':'MYPC_HARDWARE_HOST_CONTROL_FAILED=1',
            'desktop_deadline':'Desktop did not become ready',
            'controller_deadline':'Controller observation timed out',
            'device_removed':'No such device',
            'permission_error':'Permission denied',
            'cli_deadline':'CLI test deadline',
            'cli_heartbeat_missing':'CLI test heartbeat stopped',
            'missing_file':'FileNotFoundError',
            'assertion_failed':'AssertionError',
            'process_timeout':'TimeoutExpired',
            'invalid_name':'NameError',
            'invalid_value':'ValueError'}
        failure = {key:value in evidence for key,value in patterns.items()}
        failure['startup_stages'] = re.findall(r'MYPC_DESKTOP_STARTUP=(session|screen-settings|window-manager|graphics-probe|graphics-finished|hardware-ci)\b',content)[-12:]
        print('MYPC_RUNTIME_FAILURE '+json.dumps(failure,sort_keys=True),flush=True)
    if args.hardware:
        assert 'MYPC_CONTROLLER_EVDEV_ANALOG_BUTTONS_HOTPLUG_OK=1' in content, 'Actual gamepad input must pass in Linux as the Steam user'
        print('MYPC_CONTROLLER_EVDEV_ANALOG_BUTTONS_HOTPLUG_OK=1',flush=True)
        assert 'MYPC_HARDWARE_RUNTIME_OK=1' in content, 'Production ARM/FEX diagnostics did not pass'
        assert 'MYPC_HARDWARE_IDLE_PROGRESS_AND_HEARTBEAT_OK=1' in content, 'On-device idle/progress path must pass'
        assert 'MYPC_HARDWARE_PRIVATE_CONTROL_AND_CANCEL_OK=1' in content, 'Independent guest cancellation/retry observations required'
        assert 'MYPC_HARDWARE_HOST_PRIVATE_CONTROL_AND_CANCEL_OK=1' in host_content, 'Same private phone command/ACK/state channel must pass'
        guest_results = {}
        for line in content.splitlines():
            if line.startswith('MYPC_HARDWARE_GUEST_RESULT ') and len(line) <= 16384:
                state = json.loads(line.removeprefix('MYPC_HARDWARE_GUEST_RESULT '))
                guest_results[state['kind']] = state
        host_results = []
        for line in host_content.splitlines():
            if line.startswith('MYPC_HARDWARE_HOST_CONTROL_RESULT ') and len(line) <= 32768:
                host_results.append(json.loads(line.removeprefix('MYPC_HARDWARE_HOST_CONTROL_RESULT ')))
        assert len(host_results) == 1 and set(guest_results) == {'cpu', 'gpu'}, 'Independent metric observations missing'
        observed = host_results[0]
        assert set(observed) == {'cpu', 'gpu', 'gpu_cancelled_during_work', 'ack_and_state_ids_matched', 'independent_guest_reports_matched'}
        assert all(observed[key] is True for key in ('gpu_cancelled_during_work', 'ack_and_state_ids_matched', 'independent_guest_reports_matched'))
        for kind in ('cpu', 'gpu'):
            assert observed[kind] == guest_results[kind], 'Host/independent guest measurements disagree'
            print('MYPC_HARDWARE_CONTROL_RESULT ' + json.dumps(harness.validated_metrics(observed[kind]), sort_keys=True), flush=True)
        print('MYPC_HARDWARE_PRIVATE_CONTROL_AND_CANCEL_OK=1', flush=True)
    for item in re.findall(r'MYPC_STEAM_INPUT_LATENCY (\{[^\r\n]{1,256}\})', content):
        state = json.loads(item)
        if set(state) == {'samples', 'median_ms', 'p95_ms'}:
            print('MYPC_STEAM_INPUT_LATENCY ' + json.dumps(state), flush=True)
    presentation = re.findall(r'MYPC_GPU_PRESENT flushes=(\d+) readbacks=(\d+) readback_us=(\d+)', content)
    if presentation:
        flushes, readbacks, microseconds = map(int, presentation[-1])
        print('MYPC_GPU_PRESENT_RESULT ' + json.dumps({'flushes': flushes, 'readbacks': readbacks,
            'mean_readback_ms': round(microseconds / max(1, readbacks) / 1000, 2)}), flush=True)
    for item in re.findall(r'MYPC_STEAM_GPU_INFO (\{[^\r\n]{1,1024}\})', content):
        state = json.loads(item)
        if set(state) == {'renderer', 'compositing', 'webgl_status', 'webgl_renderer', 'shader_readback_ok', 'accelerated'}:
            print('MYPC_STEAM_GPU_INFO ' + json.dumps(state), flush=True)
    guest_graphics = None
    for item in re.findall(r'MYPC_GUEST_GRAPHICS (\{[^\r\n]{1,1024}\})', content):
        state = json.loads(item)
        if state.get('schema') == 1:
            guest_graphics = state
            print('MYPC_GUEST_GRAPHICS ' + json.dumps(state), flush=True)
    timing = re.findall(r'MYPC_GRAPHICS_UPDATE_TIMING (\d+\.\d+) (\d+\.\d+)', content)
    update_seconds = round(float(timing[-1][1]) - float(timing[-1][0]), 2) if timing else None
    assert update_seconds is not None and 0 <= update_seconds <= 600, 'Require an actual bounded update timing'
    summary = {'host_success': result.returncode == 0,
               'hook_seen': 'MYPC_GRAPHICS_HOOK_SEEN=1' in content,
               'update_phases': re.findall(r'MYPC_GRAPHICS_UPDATE_PHASE=(shell-ready|validate-root|verify-payload|replace-launcher|sync)', content)[-8:],
               'tool_not_found': bool(re.search(r'(?:my-pc-graphics|ld-linux)[^\r\n]*not found', content)),
               'shell_trap_error': bool(re.search(r'(?:bad trap|invalid signal specification)', content)),
               'unset_parameter': 'parameter not set' in content or 'unbound variable' in content,
               'update_ok': 'MYPC_GRAPHICS_UPDATE_OK=1' in content,
               'update_reused': 'MYPC_GRAPHICS_UPDATE_REUSED=1' in content,
               'update_elapsed_s': update_seconds,
               'update_failed': 'MYPC_GRAPHICS_UPDATE_FAILED' in content,
               'cpu_count_verified': 'MYPC_LINUX_CPU_COUNT=6' in content,
               'storage_queues_verified': 'MYPC_GUEST_DISK_QUEUES=6' in content,
               'metal': 'ANGLE Metal Renderer' in content,
               'cef_gpu': 'MYPC_STEAM_GPU_CEF_OK' in content,
               'guest_graphics_verified': bool(guest_graphics and guest_graphics.get('accelerated') is True and guest_graphics.get('readback_ok') is True),
               'legacy_migration_only': args.legacy}
    print('MYPC_METAL_RUNTIME_RESULT ' + json.dumps(summary), flush=True)
    assert summary['host_success'] and summary['update_ok'] and not summary['update_failed']
    assert summary['storage_queues_verified'], 'The guest must expose all six disk queues'
    if args.expect_update_reuse:
        assert summary['update_reused'], 'An unchanged installed payload must be reused'
    if not args.legacy:
        assert summary['metal'] and summary['cpu_count_verified']
        assert summary['guest_graphics_verified'], 'The actual guest driver/readback check must pass'
    if args.steam:
        assert summary['cef_gpu'], 'Steam GPU fallback cannot pass the release gate'
        assert 'MYPC_STEAM_SDK_WRAPPER_OK' in content, 'Downloaded Valve SDK wrapper must launch successfully'
        print('MYPC_STEAM_SDK_WRAPPER_OK=1', flush=True)
print('PASS: reserved launcher update, desktop/input or full Steam gate, persistence and clean shutdown')
