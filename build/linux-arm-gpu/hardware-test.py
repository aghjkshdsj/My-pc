#!/usr/bin/env python3
"""On-device ARM/FEX diagnostics; structured hardware data, no account logs."""
import argparse
import json
import os
import pathlib
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ITERATIONS = 1000000
MASK = (1 << 64) - 1
SNAPSHOT_TIMEOUT = 3
CPU_TIMEOUT = 30
GPU_TIMEOUT = 60
PROCESS_GROUPS = os.name == 'posix'


def spawn_child(command, timeout, tick=None, **options):
    """Bound fork/exec as well as the subsequent child workload.

    Popen can wait on its exec-error pipe before returning a child handle.
    Keep that wait off the reporting thread; a late child is killed if the
    caller has already timed out or cancelled. Never start another workload
    in the abandoned launch thread.
    """
    ready, abandoned, gate = threading.Event(), threading.Event(), threading.Lock()
    result = {}
    started = time.monotonic()
    def launch():
        try: value = subprocess.Popen(command, **options)
        except BaseException as error:
            with gate: result['error'] = error
        else:
            with gate:
                late = abandoned.is_set()
                if not late: result['child'] = value
            if late: stop_child(value)
        finally: ready.set()
    threading.Thread(target=launch, daemon=True).start()
    try:
        while not ready.wait(0.1):
            elapsed = time.monotonic()-started
            if tick: tick(elapsed)
            if elapsed >= timeout: raise subprocess.TimeoutExpired('diagnostic-launch',timeout)
        if 'error' in result: raise result['error']
        return result['child']
    except BaseException:
        with gate:
            abandoned.set()
            child = result.get('child')
        if child is not None: stop_child(child)
        raise


def stop_child(child):
    """Terminate only our new process group; cleanup is itself bounded."""
    if child.poll() is None:
        try:
            if PROCESS_GROUPS: os.killpg(child.pid, signal.SIGTERM)
            else: child.terminate()
        except ProcessLookupError: pass
    try:
        child.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        try:
            if PROCESS_GROUPS: os.killpg(child.pid, signal.SIGKILL)
            else: child.kill()
        except ProcessLookupError: pass
        # A stuck procfs read must never make cleanup wait indefinitely.
        try: child.communicate(timeout=1)
        except subprocess.TimeoutExpired: pass


def wait_child(child, timeout, tick=None):
    started = time.monotonic()
    try:
        while True:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0: raise subprocess.TimeoutExpired('diagnostic-child', timeout)
            try:
                stdout, stderr = child.communicate(timeout=min(0.5, remaining))
                if tick: tick(stdout, time.monotonic() - started)
                return stdout, stderr
            except subprocess.TimeoutExpired as error:
                # communicate retains partial output across timeouts. Only a
                # bounded tail is examined for the last actual work counter.
                if tick: tick(error.output or b'', time.monotonic() - started)
    except BaseException:
        stop_child(child)
        raise


def work_progress(output, mode, kind):
    for line in output[-65536:].decode(errors='replace').splitlines()[::-1]:
        if not line.startswith('MYPC_BENCH_PROGRESS ') or len(line) > 1024: continue
        try:
            row = json.loads(line[len('MYPC_BENCH_PROGRESS '):])
            total = 3 if kind == 'cpu' else 60
            if (row['kind'] == kind and row['arch'] == ('aarch64' if mode == 'arm64' else 'x86_64') and
                type(row['done']) is int and type(row['total']) is int and row['total'] == total and
                0 <= row['done'] <= total and row['stage'] in ('warmup','samples','libraries','EGL','shader','pixel','frames')):
                return row
        except (ValueError, KeyError, TypeError): pass
    return None


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


def execute(folder, mode, kind, workers, env, iterations=ITERATIONS, tick=None, timeout=None):
    binary = folder / 'bin' / ('hardware-bench-arm64' if mode == 'arm64' else 'hardware-bench-x86_64')
    command = [str(binary), kind]
    if kind == 'cpu':
        command += [str(workers), str(iterations)]
    if mode == 'fex':
        command.insert(0, str(folder / 'fex/usr/bin/FEX'))
    started = time.monotonic()
    limit = timeout or (CPU_TIMEOUT if kind == 'cpu' else GPU_TIMEOUT)
    child = spawn_child(command, min(10,limit), lambda elapsed: tick(None,elapsed) if tick else None,
                        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, start_new_session=True)
    def update(output, elapsed):
        if tick: tick(work_progress(output, mode, kind), elapsed)
    stdout, stderr = wait_child(child, max(0.001,limit-(time.monotonic()-started)), update)
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


def snapshot(include_processes=True):
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
        # Process accounting is optional and is never on the benchmark's
        # critical path. The caller bounds this entire helper process.
        scan_started = time.monotonic()
        for index, pid in enumerate(pathlib.Path('/proc').iterdir() if include_processes else []):
            if index >= 1024 or time.monotonic() - scan_started > 1: break
            if not pid.name.isdecimal(): continue
            try:
                text = (pid / 'stat').read_text(); name = text[text.index('(')+1:text.rindex(')')]
                # Fixed labels only: no command lines, game names or accounts.
                label = {'steam':'steam', 'steamwebhelper':'steam_webhelper', 'Xorg':'xorg',
                         'FEX':'fex', 'FEXInterpreter':'fex'}.get(name)
                if name.startswith('hardware-bench-'): label = 'test'
                if label:
                    fields = text[text.rindex(')')+2:].split()
                    result['processes'][label] = result['processes'].get(label, 0) + int(fields[11]) + int(fields[12])
            except (OSError, ValueError): pass
    except (OSError, ValueError): pass
    return result


def collect_snapshot(tick=None, include_processes=True):
    command = [sys.executable, str(pathlib.Path(__file__).resolve()), '--snapshot']
    if not include_processes: command.append('--no-processes')
    started = time.monotonic()
    try:
        child = spawn_child(command, SNAPSHOT_TIMEOUT, tick, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        output, _ = wait_child(child, max(0.001,SNAPSHOT_TIMEOUT-(time.monotonic()-started)),
                              lambda _output, elapsed: tick(elapsed) if tick else None)
        if child.returncode or len(output) > 65536: return {'status':'unavailable'}
        value = json.loads(output)
        if not isinstance(value.get('cores'), dict) or not value.get('cores'): return {'status':'unavailable'}
        value['status'] = 'measured'
        return value
    except subprocess.TimeoutExpired:
        return {'status':'timeout'}
    except (ValueError, TypeError):
        return {'status':'unavailable'}


def pressure(before, after):
    if not before.get('cores') or not after.get('cores'):
        return {'status':'unavailable', 'reason':'sampling-timeout' if 'timeout' in
                (before.get('status'),after.get('status')) else 'sampling-unavailable'}
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
    return {'status':'measured', 'online_cpus': after['online_cpus'], 'sample_seconds': round(max(0,elapsed),2),
            'per_core': cpus, 'process_cpu_percent': processes,
            'mem_available_mib': after.get('mem_available_mib'), 'swap_used_mib': after.get('swap_used_mib')}


def run(kind, folder=None, emit=None, iterations=ITERATIONS):
    folder = pathlib.Path(folder or __file__).resolve().parent if folder is None else pathlib.Path(folder).resolve()
    identifier = str(uuid.uuid4())
    started = time.monotonic()
    stage_started = started
    last_emit = 0
    state = {'schema':1, 'run':identifier, 'kind':kind, 'status':'running', 'stage':'sampling-idle',
             'progress_percent':0, 'heartbeat_seq':0, 'elapsed_s':0, 'stage_elapsed_s':0, 'results':[]}
    def publish(force=True):
        nonlocal last_emit
        now = time.monotonic()
        if not force and now - last_emit < 1: return
        state.update(heartbeat_seq=state['heartbeat_seq']+1, elapsed_s=round(now-started,2),
                     stage_elapsed_s=round(now-stage_started,2))
        if emit: emit(json.loads(json.dumps(state)))
        last_emit = now
    def sample(include_processes=True):
        state['work_stage'] = 'starting-sampler'; publish()
        return collect_snapshot(lambda _elapsed: publish(False), include_processes)
    # Signals cancel children through execute's finally path, then return a
    # structured cancelled result instead of leaving a test using the CPU.
    def cancelled(*_): raise InterruptedError()
    old = signal.signal(signal.SIGTERM, cancelled)
    try:
        publish(); before = sample()
        state['work_stage'] = 'sampling'; publish()
        idle_start = time.monotonic()
        while time.monotonic() - idle_start < 3:
            state['progress_percent'] = min(8, round(2 + (time.monotonic()-idle_start)*2,1))
            publish(False); time.sleep(0.25)
        state['idle_guest'] = pressure(before, sample())
        state['progress_percent'] = 10; publish()
        workers = min(64, max(1, os.cpu_count() or 1))
        steps = [(mode,count) for mode in ('arm64','fex')
                 for count in ([1] + ([workers] if workers > 1 else []) if kind == 'cpu' else [1])]
        with tempfile.TemporaryDirectory(prefix='my-pc-hardware-') as temporary:
            env = environment(folder, temporary)
            for index,(mode,count) in enumerate(steps):
                stage_started = time.monotonic()
                base, span = 10 + 90*index/len(steps), 90/len(steps)
                state.update(stage=f'{mode}-{kind}-{count}', progress_percent=round(base,1),
                             work_done=0, work_total=3 if kind=='cpu' else 60,
                             work_unit='samples' if kind=='cpu' else 'frames', work_stage='launching')
                publish(); before = sample(False)
                state['work_stage'] = 'launching'; publish()
                def tick(work, _elapsed):
                    first_work = work is not None and work['done'] > 0 and state.get('work_done', 0) == 0
                    if work:
                        state.update(work_done=work['done'],work_total=work['total'],work_stage=work['stage'])
                        state['progress_percent'] = max(state['progress_percent'], round(base+span*0.95*work['done']/work['total'],1))
                    # A fast first frame/sample is evidence of real work. Send
                    # it immediately so Stop/CI can observe it, even inside the
                    # usual one-second heartbeat interval. Benchmark timing
                    # has already ended before its work counter is printed.
                    publish(first_work)
                try: row = execute(folder, mode, kind, count, env, iterations, tick=tick)
                except subprocess.TimeoutExpired:
                    row = {'mode':mode,'kind':kind,'workers':count,'status':'timeout', 'stage':'workload-timeout'}
                row['guest_load'] = pressure(before, sample(False))
                state['results'].append(row)
                if row['status'] != 'passed': break
                state['progress_percent'] = round(base+span,1); publish()
        passed = len(state['results']) == len(steps) and all(row['status']=='passed' for row in state['results'])
        state['status'] = 'complete' if passed else 'failed'
        state['stage'] = 'finished' if passed else 'workload-failed'
    except InterruptedError:
        state.update(status='cancelled',stage='cancelled')
    except Exception:
        state.update(status='failed',stage='diagnostic-runtime')
    finally:
        signal.signal(signal.SIGTERM, old)
    publish(); return state


class SerialReporter:
    """Serial backpressure must not block work, heartbeats or cancellation."""
    def __init__(self, fd):
        self.fd, self.pending = fd, b''

    def emit(self, state, limit=0.25):
        import select
        line = ('MYPC_HARDWARE_TEST '+json.dumps(state,separators=(',',':'),allow_nan=False)+'\n').encode()
        assert len(line) <= 16385
        deadline = time.monotonic()+limit
        # Finish a partial record first; retain at most that single record.
        if self.pending: self.flush(deadline,select)
        if not self.pending:
            self.pending = line
            self.flush(deadline,select)

    def flush(self, deadline, select):
        while self.pending and time.monotonic()<deadline:
            try:
                count = os.write(self.fd,self.pending)
                if count == 0: return
                self.pending = self.pending[count:]
            except BlockingIOError:
                select.select([], [self.fd], [], min(0.05,max(0,deadline-time.monotonic())))


def main():
    if '--snapshot' in sys.argv[1:]:
        print(json.dumps(snapshot('--no-processes' not in sys.argv[1:]),separators=(',',':')))
        return
    import fcntl
    parser = argparse.ArgumentParser(); parser.add_argument('kind', choices=['cpu','gpu'])
    # CI reads the same CLI result independently of UART delivery. The phone
    # launcher does not accept any user-controlled file or command argument.
    parser.add_argument('--result-file',type=pathlib.Path)
    parser.add_argument('--no-serial',action='store_true',
                        help='Report only to the private atomic result file owned by the control service')
    args = parser.parse_args()
    if args.no_serial and args.result_file is None:
        parser.error('--no-serial requires --result-file')
    lock = open('/tmp/my-pc-hardware-test.lock', 'a+')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('A hardware test is already running.'); raise SystemExit(1)
    console = None if args.no_serial else os.open('/dev/ttyAMA0',os.O_WRONLY|os.O_NONBLOCK|os.O_NOCTTY|os.O_CLOEXEC)
    reporter = None if console is None else SerialReporter(console)
    def emit(state):
        if args.result_file:
            temporary = args.result_file.with_suffix('.new')
            temporary.write_text(json.dumps(state,separators=(',',':')))
            temporary.replace(args.result_file)
        if reporter is not None: reporter.emit(state)
    try:
        state = run(args.kind, emit=emit)
        if reporter is not None: reporter.emit(state,limit=2)
    finally:
        if console is not None: os.close(console)


if __name__ == '__main__': main()
