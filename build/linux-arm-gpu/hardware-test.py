#!/usr/bin/env python3
"""On-device ARM/FEX diagnostics; structured hardware data, no account logs."""
import argparse
import json
import os
import pathlib
import signal
import statistics
import subprocess
import tempfile
import time
import uuid

ITERATIONS = 1000000
MASK = (1 << 64) - 1


def checksum(workers, iterations):
    combined = 0
    for worker in range(1, workers + 1):
        value = worker
        for _ in range(iterations):
            value ^= value >> 12
            value ^= (value << 25) & MASK
            value ^= value >> 27
            value = value * 2685821657736338717 & MASK
        combined ^= value
    return f'{combined:016x}'


def environment(folder, temporary):
    env = os.environ.copy()
    # Retain the current desktop's X11 cookie location when giving FEX a
    # private HOME. The cookie itself is never copied, read or reported here.
    env.setdefault('XAUTHORITY', str(pathlib.Path(env.get('HOME', '/home/steam')) / '.Xauthority'))
    # Clean only test-child variables. Never edit the user's Steam/FEX config.
    for name in list(env):
        if name.startswith('FEX_') or name in ('LIBGL_ALWAYS_SOFTWARE', 'GALLIUM_DRIVER', 'LD_PRELOAD', 'LD_LIBRARY_PATH'):
            env.pop(name, None)
    home = pathlib.Path(temporary)
    (home / '.fex-emu').mkdir(exist_ok=True)
    (home / '.fex-emu/Config.json').write_text(json.dumps({'Config': {
        'RootFS': str(folder / 'rootfs'),
        'ThunkHostLibs': str(folder / 'fex/usr/lib/aarch64-linux-gnu/fex-emu/HostThunks'),
        'ThunkGuestLibs': str(folder / 'fex/usr/share/fex-emu/GuestThunks')}}))
    env.update(HOME=str(home), FEX_ROOTFS=str(folder / 'rootfs'),
               FEX_THUNKHOSTLIBS=str(folder / 'fex/usr/lib/aarch64-linux-gnu/fex-emu/HostThunks'),
               FEX_THUNKGUESTLIBS=str(folder / 'fex/usr/share/fex-emu/GuestThunks'),
               PATH=str(folder / 'fex/usr/bin') + ':' + env.get('PATH', '/usr/bin:/bin'),
               LD_LIBRARY_PATH=str(folder / 'native/usr/lib/aarch64-linux-gnu'))
    # Honour software recovery mode for comparison, rather than claiming Metal
    # merely because the test was requested.
    if pathlib.Path('/proc/cmdline').exists() and 'my_pc_graphics=software' in pathlib.Path('/proc/cmdline').read_text():
        env.update(LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe')
    return env


def execute(folder, mode, kind, workers, env, iterations=ITERATIONS):
    binary = folder / 'bin' / ('hardware-bench-arm64' if mode == 'arm64' else 'hardware-bench-x86_64')
    command = [str(binary), kind]
    if kind == 'cpu':
        command += [str(workers), str(iterations)]
    if mode == 'fex':
        command.insert(0, str(folder / 'fex/usr/bin/FEX'))
    started = time.monotonic()
    child = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = child.communicate(timeout=180)
    except BaseException:
        if child.poll() is None:
            try: os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError: pass
        try:
            child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            child.communicate()
        raise
    total_ms = (time.monotonic() - started) * 1000
    # Do not relay FEX or X11 logs, environment, paths or arguments to reports.
    records = []
    for line in stdout.decode(errors='replace').splitlines():
        if line.startswith('MYPC_BENCH ') and len(line) <= 4096:
            row = json.loads(line[len('MYPC_BENCH '):])
            assert row['kind'] == kind and row['arch'] == ('aarch64' if mode == 'arm64' else 'x86_64')
            records.append(row)
    if child.returncode or len(records) != (3 if kind == 'cpu' else 1):
        if os.environ.get('MYPC_HARDWARE_CI') == '1':
            print('MYPC_HARDWARE_CI_FAILURE '+(stdout+stderr).decode(errors='replace')[-4096:],flush=True)
        stage = 'runtime'
        for item in stderr.decode(errors='replace').splitlines():
            if item.startswith('MYPC_BENCH_FAILED stage='):
                stage = item.split('=', 1)[1][:32]
        return {'mode': mode, 'kind': kind, 'status': 'failed', 'exit_code': child.returncode,
                'stage': stage, 'launch_total_ms': round(total_ms, 2)}
    if kind == 'cpu':
        # Fixed expected checksums are generated independently at build time.
        expected = json.loads((folder / 'checksums.json').read_text())[f'{workers}:{iterations}']
        assert all(row['checksum'] == expected and row['workers'] == workers and
                   row['iterations_per_worker'] == iterations for row in records), 'CPU result mismatch'
        wall = statistics.median(row['wall_ms'] for row in records)
        return {'mode': mode, 'kind': kind, 'status': 'passed', 'workers': workers,
                'iterations_per_worker': iterations, 'samples': 3, 'checksum': expected,
                'wall_median_ms': round(wall, 4),
                'process_cpu_median_ms': round(statistics.median(row['process_cpu_ms'] for row in records), 4),
                'million_iterations_s': round(iterations * workers / wall / 1000, 4),
                'launch_total_ms': round(total_ms, 2)}
    row = records[0]
    name = row['renderer'].lower()
    row.update(mode=mode, status='passed', launch_total_ms=round(total_ms, 2),
               accelerated=row['readback_ok'] is True and 'virgl' in name and
               not any(word in name for word in ('llvmpipe', 'softpipe', 'software', 'swiftshader')))
    return row


def snapshot():
    result = {'online_cpus': os.cpu_count(), 'cores': {}, 'processes': {}}
    try:
        for line in pathlib.Path('/proc/stat').read_text().splitlines():
            key, *values = line.split()
            if key.startswith('cpu') and key != 'cpu':
                result['cores'][key] = [int(x) for x in values[:8]]
        result['uptime_s'] = float(pathlib.Path('/proc/uptime').read_text().split()[0])
        mem = dict((parts[0].rstrip(':'), int(parts[1])) for line in pathlib.Path('/proc/meminfo').read_text().splitlines()
                   if len(parts := line.split()) >= 2)
        result.update(mem_available_mib=round(mem.get('MemAvailable', 0)/1024, 1),
                      swap_used_mib=round((mem.get('SwapTotal', 0)-mem.get('SwapFree', 0))/1024, 1))
        for pid in pathlib.Path('/proc').iterdir():
            if not pid.name.isdecimal(): continue
            try:
                text = (pid / 'stat').read_text(); name = text[text.index('(')+1:text.rindex(')')]
                # Fixed labels only: no command lines, game names or accounts.
                label = {'steam':'steam', 'steamwebhelper':'steam_webhelper', 'Xorg':'xorg',
                         'FEX':'fex', 'FEXInterpreter':'fex', 'hardware-bench-':'test'}.get(name)
                if label:
                    fields = text[text.rindex(')')+2:].split()
                    result['processes'][label] = result['processes'].get(label, 0) + int(fields[11]) + int(fields[12])
            except (OSError, ValueError): pass
    except (OSError, ValueError): pass
    return result


def pressure(before, after):
    elapsed = after.get('uptime_s', 0)-before.get('uptime_s', 0)
    cpus = []
    for key, end in after['cores'].items():
        start = before['cores'].get(key)
        if not start: continue
        delta = [b-a for a,b in zip(start,end)]; total = sum(delta)
        if total > 0:
            cpus.append({'core': int(key[3:]), 'busy_percent': round((total-delta[3]-delta[4])/total*100,1),
                         'iowait_percent': round(delta[4]/total*100,1)})
    ticks = os.sysconf('SC_CLK_TCK')
    processes = {key: round(max(0, value-before['processes'].get(key, 0))/ticks/elapsed*100,1)
                 for key,value in after['processes'].items() if elapsed > 0 and key in before['processes']}
    return {'online_cpus': after['online_cpus'], 'sample_seconds': round(max(0,elapsed),2),
            'per_core': cpus, 'process_cpu_percent': processes,
            'mem_available_mib': after.get('mem_available_mib'), 'swap_used_mib': after.get('swap_used_mib')}


def run(kind, folder=None, emit=None):
    folder = pathlib.Path(folder or __file__).resolve().parent if folder is None else pathlib.Path(folder).resolve()
    identifier = str(uuid.uuid4())
    state = {'schema':1, 'run':identifier, 'kind':kind, 'status':'running', 'stage':'sampling-idle', 'results':[]}
    def publish():
        if emit: emit(state.copy())
    # Signals cancel children through execute's finally path, then return a
    # structured cancelled result instead of leaving a test using the CPU.
    def cancelled(*_): raise InterruptedError()
    old = signal.signal(signal.SIGTERM, cancelled)
    try:
        publish(); before = snapshot(); time.sleep(3); state['idle_guest'] = pressure(before, snapshot()); publish()
        workers = min(64, max(1, os.cpu_count() or 1))
        with tempfile.TemporaryDirectory(prefix='my-pc-hardware-') as temporary:
            env = environment(folder, temporary)
            for mode in ('arm64', 'fex'):
                for count in ([1] + ([workers] if workers > 1 else []) if kind == 'cpu' else [1]):
                    state['stage'] = f'{mode}-{kind}-{count}'; publish()
                    before = snapshot()
                    try: row = execute(folder, mode, kind, count, env)
                    except subprocess.TimeoutExpired:
                        row = {'mode':mode,'kind':kind,'workers':count,'status':'timeout'}
                    row['guest_load'] = pressure(before, snapshot())
                    state['results'].append(row); publish()
        state['status'] = 'complete' if all(row['status']=='passed' for row in state['results']) else 'failed'
        state['stage'] = 'finished'
    except InterruptedError:
        state.update(status='cancelled',stage='cancelled')
    except Exception:
        state.update(status='failed',stage='diagnostic-runtime')
    finally:
        signal.signal(signal.SIGTERM, old)
    publish(); return state


if __name__ == '__main__':
    import fcntl
    parser = argparse.ArgumentParser(); parser.add_argument('kind', choices=['cpu','gpu']); args = parser.parse_args()
    lock = open('/tmp/my-pc-hardware-test.lock', 'a+')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('A hardware test is already running.'); raise SystemExit(1)
    console = open('/dev/ttyAMA0','w',buffering=1)
    def emit(state):
        line = 'MYPC_HARDWARE_TEST ' + json.dumps(state,separators=(',',':'),allow_nan=False)
        assert len(line) <= 16384
        console.write(line+'\n')
        print(f"{state['kind'].upper()}: {state['stage']} · {state['status']}",flush=True)
    state = run(args.kind, emit=emit)
    print(json.dumps(state,indent=2),flush=True)
    print('\nDone. Results are available in My-pc → Hardware tests.',flush=True)
