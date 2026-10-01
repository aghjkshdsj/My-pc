#!/usr/bin/env python3
"""Exercise the phone's private diagnostic protocol without exporting logs.

The host sends fixed commands through the same virtio port as the phone. The
guest gate independently observes the private atomic workload reports. Both
must see actual CPU/GPU work, cancellation during rendering, and a clean retry.
"""
import collections
import json
import math
import pathlib
import re
import socket
import time
import uuid

MAX_FRAME = 16384
CANCEL_GPU_FRAMES = 6000
CPU_ID, CANCEL_GPU_ID, RETRY_GPU_ID, CANCEL_ID = (digit * 32 for digit in '1234')
GUEST_DIRECTORY = pathlib.Path('/tmp/my-pc-hardware-control-ci')
MARKERS = {
    CPU_ID: 'MYPC_HARDWARE_GUEST_CPU_COMPLETE=1',
    CANCEL_GPU_ID: 'MYPC_HARDWARE_GUEST_GPU_CANCELLED=1',
    RETRY_GPU_ID: 'MYPC_HARDWARE_GUEST_GPU_COMPLETE=1',
}

# Values are code-owned constants, never exception messages, paths or JSON
# supplied by a guest. The release wrapper validates this schema again.
FAILURE_MESSAGES = {
    'Idle/load sample missing': 'load-missing', 'Six-core sample required': 'six-core-sample-required',
    'Six-core sample incomplete': 'six-core-sample-incomplete', 'Core identities invalid': 'core-identities-invalid',
    'Core load invalid': 'core-load-invalid', 'Process sample invalid': 'process-sample-invalid',
    'Memory sample invalid': 'memory-sample-invalid', 'State schema invalid': 'state-schema-invalid',
    'State kind/status invalid': 'state-kind-status-invalid', 'Run identity invalid': 'run-identity-invalid',
    'State heartbeat invalid': 'state-heartbeat-invalid', 'State progress invalid': 'state-progress-invalid',
    'State stage invalid': 'state-stage-invalid', 'State result list invalid': 'state-result-list-invalid',
    'Result identity invalid': 'result-identity-invalid', 'CPU result invalid': 'cpu-result-invalid',
    'Accelerated GPU pixels required': 'gpu-pixels-invalid', 'Accelerated GPU renderer required': 'gpu-renderer-invalid',
    'Workload timing invalid': 'workload-timing-invalid', 'Workload timing missing': 'workload-timing-missing',
    'Completion results invalid': 'completion-results-invalid', 'ARM/FEX coverage incomplete': 'arm-fex-coverage-incomplete',
    'Metric summary invalid': 'metric-summary-invalid', 'Metric summary has unexpected fields': 'metric-summary-fields-invalid',
    'Response frame too large': 'response-frame-oversize', 'Response schema invalid': 'response-schema-invalid',
    'Diagnostic transport disconnected': 'transport-disconnected', 'Ready response invalid': 'ready-response-invalid',
    'ACK correlation invalid': 'ack-correlation-invalid', 'Diagnostic request rejected': 'request-rejected',
    'State request correlation invalid': 'state-request-correlation-invalid',
    'State workload correlation invalid': 'state-workload-correlation-invalid', 'State regressed': 'state-regressed',
    'Heartbeat replay changed': 'heartbeat-replay-changed', 'Excess diagnostic updates': 'excess-updates',
    'Diagnostic control failure': 'control-service-failure', 'Diagnostic response type invalid': 'response-type-invalid',
    'Diagnostic host stopped': 'host-stopped', 'Diagnostic control deadline': 'host-deadline',
    'Diagnostic drain exceeded limit': 'drain-limit',
    'Workload terminal status invalid': 'terminal-status-invalid', 'GPU finished before cancellation': 'gpu-finished-before-stop',
    'Initial/progress/completion observations missing': 'progress-observations-missing',
    'Diagnostic socket unavailable': 'socket-unavailable', 'Guest diagnostic observation deadline': 'guest-deadline',
    'Private report exceeds limit': 'private-report-oversize', 'Private report request identity invalid': 'private-report-identity-invalid',
    'Private workload identity mismatch': 'private-workload-identity-invalid', 'Private report regressed': 'private-report-regressed',
    'Private workload terminal status invalid': 'private-terminal-status-invalid',
    'Cancellation happened before actual GPU work': 'gpu-stopped-before-work',
    'Independent CPU checksum invalid': 'independent-cpu-checksum-invalid',
}
GENERIC_CODES = {'invalid-json', 'missing-file', 'permission-error', 'io-error', 'missing-field',
                 'invalid-type', 'invalid-value', 'unexpected-error'}
CONTROL_CODES = {'launch-timeout', 'launch-failed', 'report-invalid', 'launch-cancelled',
                 'runner-exited', 'cancellation-timeout'}
PHASES = {'unknown', 'connect', 'await-ready', 'cpu-start', 'cpu-ack', 'cpu-work', 'cpu-guest-report', 'cpu-idle',
          'gpu-cancel-start', 'gpu-cancel-ack', 'gpu-work', 'gpu-guest-work', 'gpu-drain', 'gpu-cancel', 'gpu-cancel-command-ack',
          'gpu-cancel-work', 'gpu-cancel-guest-report', 'gpu-cancel-idle', 'gpu-retry-start', 'gpu-retry-ack',
          'gpu-retry-work', 'gpu-retry-guest-report', 'gpu-retry-idle', 'validate-results',
          'guest-controller', 'guest-read-report', 'guest-validate-report', 'guest-validate-state',
          'guest-validate-checksum', 'guest-publish-result'}
STAGES = {'unknown', 'sampling-idle', 'finished', 'workload-failed', 'cancelled', 'diagnostic-runtime'} | {
    f'{mode}-{kind}-{workers}' for mode in ('arm64', 'fex') for kind in ('cpu', 'gpu') for workers in (1, 6)}
WORK_STAGES = {'unknown', 'starting-sampler', 'sampling', 'launching', 'warmup', 'samples', 'libraries',
               'EGL', 'shader', 'pixel', 'frames'}
RESULT_STAGES = {'runtime', 'workload-timeout', 'libraries', 'X11', 'EGL', 'window', 'context', 'shader', 'pixel', 'frames'}


class GateError(ValueError):
    def __init__(self, message, service_code='unknown'):
        super().__init__(message)
        self.code = FAILURE_MESSAGES.get(message, 'unexpected-error')
        self.service_code = service_code if service_code in CONTROL_CODES else 'unknown'


def failure(error, context=None, observation=''):
    """Bounded enum/boolean/numeric evidence only, even for untrusted errors."""
    if isinstance(error, GateError): code = error.code
    elif isinstance(error, json.JSONDecodeError): code = 'invalid-json'
    elif isinstance(error, FileNotFoundError): code = 'missing-file'
    elif isinstance(error, PermissionError): code = 'permission-error'
    elif isinstance(error, OSError): code = 'io-error'
    elif isinstance(error, KeyError): code = 'missing-field'
    elif isinstance(error, TypeError): code = 'invalid-type'
    elif isinstance(error, ValueError): code = 'invalid-value'
    else: code = 'unexpected-error'
    context = context if isinstance(context, dict) else {}
    value = context.get('state'); value = value if isinstance(value, dict) else {}
    rows = value.get('results'); rows = rows if isinstance(rows, list) else []
    last = rows[-1] if rows and isinstance(rows[-1], dict) else {}
    idle = value.get('idle_guest'); idle = idle if isinstance(idle, dict) else {}
    def enum(item, choices): return item if isinstance(item, str) and item in choices else 'unknown'
    sequence = value.get('heartbeat_seq')
    return {'code': code, 'phase': enum(context.get('phase'), PHASES),
            'kind': enum(value.get('kind'), {'cpu', 'gpu'}),
            'status': enum(value.get('status'), {'running', 'complete', 'failed', 'cancelled'}),
            'heartbeat_seq': sequence if type(sequence) is int and 0 <= sequence <= 10000000 else 0,
            'stage': enum(value.get('stage'), STAGES), 'work_stage': enum(value.get('work_stage'), WORK_STAGES),
            'result_count': len(rows) if len(rows) <= 4 else 0,
            'idle_status': enum(idle.get('status'), {'measured', 'unavailable', 'timeout'}),
            'last_result_mode': enum(last.get('mode'), {'arm64', 'fex'}),
            'last_result_status': enum(last.get('status'), {'passed', 'failed', 'timeout'}),
            'last_result_stage': enum(last.get('stage'), RESULT_STAGES),
            'service_code': error.service_code if isinstance(error, GateError) else 'unknown',
            'controller_ready': 'MYPC_CONTROLLER_READY=1' in observation,
            'controller_observer_ready': 'MYPC_CONTROLLER_OBSERVER_READY=1' in observation,
            'guest_observer_ready': 'MYPC_HARDWARE_GUEST_OBSERVER_READY=1' in observation}


def validated_failure(value):
    require(isinstance(value, dict), 'State schema invalid')
    expected = set(failure(GateError('State schema invalid')))
    require(set(value) == expected and value['code'] in set(FAILURE_MESSAGES.values()) | GENERIC_CODES,
            'State schema invalid')
    enum_fields = {'phase': PHASES, 'kind': {'cpu', 'gpu'}, 'status': {'running', 'complete', 'failed', 'cancelled'},
                   'stage': STAGES, 'work_stage': WORK_STAGES, 'idle_status': {'measured', 'unavailable', 'timeout'},
                   'last_result_mode': {'arm64', 'fex'}, 'last_result_status': {'passed', 'failed', 'timeout'},
                   'last_result_stage': RESULT_STAGES,
                   'service_code': CONTROL_CODES}
    require(all(value[key] in choices | {'unknown'} for key, choices in enum_fields.items()), 'State schema invalid')
    require(type(value['heartbeat_seq']) is int and 0 <= value['heartbeat_seq'] <= 10000000
            and type(value['result_count']) is int and 0 <= value['result_count'] <= 4
            and all(type(value[key]) is bool for key in ('controller_ready', 'controller_observer_ready', 'guest_observer_ready')),
            'State schema invalid')
    return value


def require(condition, message):
    if not condition: raise GateError(message)


def number(value, maximum=1e12):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


def pressure(value, required=True, allow_unavailable=False):
    if (not required or allow_unavailable) and isinstance(value, dict) and value.get('status') == 'unavailable':
        reason = value.get('reason')
        require(reason in ('sampling-timeout', 'sampling-unavailable'), 'Idle/load sample missing')
        return {'status': 'unavailable', 'reason': reason}
    require(isinstance(value, dict) and value.get('status') == 'measured', 'Idle/load sample missing')
    require(value.get('online_cpus') == 6 and number(value.get('sample_seconds'))
            and (not required or value['sample_seconds'] > 0), 'Six-core sample required')
    cores = value.get('per_core')
    require(isinstance(cores, list) and (len(cores) == 6 if required else len(cores) <= 6), 'Six-core sample incomplete')
    identities = {row.get('core') for row in cores if isinstance(row, dict)}
    require(identities == set(range(6)) if required else identities <= set(range(6)) and len(identities) == len(cores),
            'Core identities invalid')
    for row in cores:
        require(type(row['core']) is int and number(row.get('busy_percent'), 100)
                and number(row.get('iowait_percent'), 100), 'Core load invalid')
    labels = value.get('process_cpu_percent')
    require(isinstance(labels, dict) and set(labels) <= {'steam', 'steam_webhelper', 'xorg', 'fex', 'test'}
            # /proc/uptime and process ticks are sampled at different instants.
            # These optional observational percentages can exceed nominal CPU
            # capacity over short intervals; workload coverage is checked below.
            and all(number(item, 60000) for item in labels.values()), 'Process sample invalid')
    require(number(value.get('mem_available_mib')) and number(value.get('swap_used_mib')), 'Memory sample invalid')
    return {'status': 'measured', 'online_cpus': 6, 'sample_seconds': value['sample_seconds'],
            'per_core': [{key: row[key] for key in ('core', 'busy_percent', 'iowait_percent')} for row in cores],
            'process_cpu_percent': labels, 'mem_available_mib': value['mem_available_mib'],
            'swap_used_mib': value['swap_used_mib']}


def state(value):
    """Validate fixed metrics; never relay arbitrary stages, renderers or text."""
    require(isinstance(value, dict) and type(value.get('schema')) is int and value['schema'] == 1,
            'State schema invalid')
    require(value.get('kind') in ('cpu', 'gpu') and value.get('status') in
            ('running', 'complete', 'failed', 'cancelled'), 'State kind/status invalid')
    require(isinstance(value.get('run'), str) and str(uuid.UUID(value['run'])) == value['run'], 'Run identity invalid')
    require(type(value.get('heartbeat_seq')) is int and 1 <= value['heartbeat_seq'] <= 10000000,
            'State heartbeat invalid')
    require(number(value.get('progress_percent'), 100) and number(value.get('elapsed_s'), 3600)
            and number(value.get('stage_elapsed_s'), 3600), 'State progress invalid')
    require(isinstance(value.get('stage'), str) and len(value['stage']) <= 64, 'State stage invalid')
    rows = value.get('results')
    require(isinstance(rows, list) and len(rows) <= 4, 'State result list invalid')
    if 'idle_guest' in value: pressure(value['idle_guest'], allow_unavailable=True)
    for row in rows:
        require(isinstance(row, dict) and row.get('mode') in ('arm64', 'fex')
                and row.get('kind') == value['kind'] and row.get('status') in
                ('passed', 'failed', 'timeout'), 'Result identity invalid')
        if row['status'] != 'passed': continue
        pressure(row.get('guest_load'), required=False)
        if value['kind'] == 'cpu':
            require(type(row.get('workers')) is int and row['workers'] in (1, 6)
                    and row.get('iterations_per_worker') == 1000000 and row.get('samples') == 3
                    and isinstance(row.get('checksum'), str)
                    and re.fullmatch('[0-9a-f]{16}', row['checksum']), 'CPU result invalid')
            metrics = ('wall_median_ms', 'process_cpu_median_ms', 'million_iterations_s', 'launch_total_ms')
        else:
            require(row.get('arch') == ('aarch64' if row['mode'] == 'arm64' else 'x86_64')
                    and row.get('readback_ok') is True and row.get('accelerated') is True
                    and row.get('frames') == 60 and row.get('width') == 800 and row.get('height') == 500
                    and row.get('draws_per_frame') == 16, 'Accelerated GPU pixels required')
            renderer = row.get('renderer')
            require(isinstance(renderer, str) and len(renderer) <= 256 and 'virgl' in renderer.lower()
                    and not any(word in renderer.lower() for word in ('llvmpipe', 'softpipe', 'software', 'swiftshader')),
                    'Accelerated GPU renderer required')
            metrics = ('wall_ms', 'render_fps', 'submit_median_ms', 'submit_p95_ms', 'finish_median_ms',
                       'finish_p95_ms', 'swap_median_ms', 'swap_p95_ms', 'launch_total_ms')
        require(all(number(row.get(key)) for key in metrics), 'Workload timing invalid')
        require(row['launch_total_ms'] > 0 and (row['wall_median_ms'] > 0 and row['million_iterations_s'] > 0
                if value['kind'] == 'cpu' else row['wall_ms'] > 0 and row['render_fps'] > 0),
                'Workload timing missing')
    if value['status'] == 'complete':
        pressure(value.get('idle_guest'), allow_unavailable=True)
        require(value['progress_percent'] == 100 and all(row['status'] == 'passed' for row in rows),
                'Completion results invalid')
        expected = [('arm64', 1), ('arm64', 6), ('fex', 1), ('fex', 6)] if value['kind'] == 'cpu' else [('arm64', None), ('fex', None)]
        require([(row['mode'], row.get('workers') if value['kind'] == 'cpu' else None) for row in rows] == expected,
                'ARM/FEX coverage incomplete')
    return value


def gpu_work(value, total=60):
    return (type(total) is int and 60 <= total <= CANCEL_GPU_FRAMES
            and value.get('kind') == 'gpu' and value.get('status') == 'running'
            and value.get('stage') in ('arm64-gpu-1', 'fex-gpu-1')
            and value.get('work_stage') == 'frames' and type(value.get('work_done')) is int
            and type(value.get('work_total')) is int and value['work_total'] == total
            and 0 < value['work_done'] < value['work_total'])


def metrics(value):
    """Export only predefined numeric/boolean fields, fixed modes and checksums."""
    state(value)
    allowed = ({'workers', 'iterations_per_worker', 'samples', 'checksum', 'wall_median_ms',
                'process_cpu_median_ms', 'million_iterations_s', 'launch_total_ms'} if value['kind'] == 'cpu' else
               {'launch_total_ms', 'frames', 'width', 'height', 'draws_per_frame', 'wall_ms', 'render_fps',
                'submit_median_ms', 'submit_p95_ms', 'finish_median_ms', 'finish_p95_ms', 'swap_median_ms',
                'swap_p95_ms', 'readback_ok', 'accelerated'})
    return {'kind': value['kind'], 'status': value['status'], 'progress_percent': value['progress_percent'],
            'heartbeat_seq': value['heartbeat_seq'], 'elapsed_s': value['elapsed_s'],
            'idle_guest': pressure(value['idle_guest'], allow_unavailable=True),
            'results': [dict(mode=row['mode'], kind=row['kind'], status=row['status'],
                             guest_load=pressure(row['guest_load'], required=False),
                             **{key: row[key] for key in allowed if key in row}) for row in value['results']]}


def validated_metrics(value):
    """Revalidate already-redacted host/guest summaries before publishing."""
    require(isinstance(value, dict) and value.get('status') == 'complete', 'Metric summary invalid')
    candidate = json.loads(json.dumps(value))
    candidate.update(schema=1, run=str(uuid.UUID(int=0)), stage='finished', stage_elapsed_s=0)
    if candidate.get('kind') == 'gpu':
        for row in candidate.get('results', []):
            row.update(arch='aarch64' if row.get('mode') == 'arm64' else 'x86_64', renderer='virgl')
    result = metrics(candidate)
    require(result == value, 'Metric summary has unexpected fields')
    return result


class Frames:
    def __init__(self): self.pending = bytearray()

    def feed(self, chunk):
        self.pending.extend(chunk)
        records = []
        while b'\n' in self.pending:
            end = self.pending.index(10)
            require(end + 1 <= MAX_FRAME, 'Response frame too large')
            encoded = bytes(self.pending[:end]); del self.pending[:end + 1]
            value = json.loads(encoded)
            require(isinstance(value, dict) and type(value.get('schema')) is int and value['schema'] == 1,
                    'Response schema invalid')
            records.append(value)
        require(len(self.pending) < MAX_FRAME, 'Response frame too large')
        return records


class Host:
    def __init__(self, transport, observation, stop, timeout=180):
        self.transport, self.observation, self.stop, self.timeout = transport, observation, stop, timeout
        self.parser, self.queue, self.commands = Frames(), collections.deque(), {}
        self.acks, self.states, self.history, self.ready = {}, {}, {}, None
        self.context = {'phase': 'await-ready', 'state': None}

    def send(self, command, identifier=None, target=None):
        identifier = identifier or uuid.uuid4().hex
        self.commands[identifier] = command
        payload = {'schema': 1, 'id': identifier, 'command': command}
        if target is not None: payload['target'] = target
        self.transport.sendall((json.dumps(payload, separators=(',', ':')) + '\n').encode())
        return identifier

    def poll(self):
        received = False
        if not self.queue:
            try: chunk = self.transport.recv(4096)
            except (socket.timeout, BlockingIOError): return False
            require(bool(chunk), 'Diagnostic transport disconnected')
            received = True
            self.queue.extend(self.parser.feed(chunk))
        if not self.queue: return received
        value = self.queue.popleft()
        kind = value.get('type')
        if kind == 'ready':
            require(set(value) == {'schema', 'type', 'ready', 'busy'} and value['ready'] is True
                    and type(value['busy']) is bool, 'Ready response invalid')
            self.ready = value
        elif kind == 'ack':
            identifier = value.get('id')
            require(identifier in self.commands and value.get('command') == self.commands[identifier]
                    and value.get('status') in ('accepted', 'busy', 'duplicate', 'idle', 'stale')
                    and set(value) == {'schema', 'type', 'id', 'command', 'status'}, 'ACK correlation invalid')
            require(value['status'] == 'accepted', 'Diagnostic request rejected')
            self.acks[identifier] = value
        elif kind == 'state':
            identifier = value.get('id')
            require(identifier in self.commands and self.commands[identifier] in ('cpu', 'gpu')
                    and set(value) == {'schema', 'type', 'id', 'state'}, 'State request correlation invalid')
            self.context['state'] = value['state']
            current = state(value['state'])
            require(current['kind'] == self.commands[identifier], 'State workload correlation invalid')
            previous = self.states.get(identifier)
            if previous:
                require(current['run'] == previous['run'] and current['heartbeat_seq'] >= previous['heartbeat_seq']
                        and current['progress_percent'] >= previous['progress_percent'], 'State regressed')
                if current['heartbeat_seq'] == previous['heartbeat_seq']:
                    require(current == previous, 'Heartbeat replay changed'); return True
            self.states[identifier] = current
            history = self.history.setdefault(identifier, [])
            history.append((current['heartbeat_seq'], current['progress_percent']))
            require(len(history) <= 4096, 'Excess diagnostic updates')
        elif kind == 'failure':
            require(value.get('id') in self.commands and set(value) == {'schema', 'type', 'id', 'code', 'busy'}
                    and type(value['busy']) is bool, 'State request correlation invalid')
            raise GateError('Diagnostic control failure', value.get('code'))
        else: raise GateError('Diagnostic response type invalid')
        return True

    def drain(self):
        """Consume available replies before acting on a cached work counter.

        Bounded, nonblocking reads close the stale-state race. The real render
        probe supplies the remaining work window; draining never pauses it.
        """
        previous = self.transport.gettimeout()
        self.transport.setblocking(False)
        try:
            for _ in range(256):
                if not self.poll(): return
            require(False, 'Diagnostic drain exceeded limit')
        finally: self.transport.settimeout(previous)

    def wait(self, predicate, timeout=None):
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while not predicate():
            require(not self.stop.is_set(), 'Diagnostic host stopped')
            require(time.monotonic() < deadline, 'Diagnostic control deadline')
            self.poll()

    def acknowledge(self, identifier):
        self.wait(lambda: identifier in self.acks, 15)

    def idle(self):
        identifier = self.send('status'); self.acknowledge(identifier)
        self.ready = None
        self.wait(lambda: self.ready is not None and self.ready['busy'] is False, 20)

    def finished(self, identifier, status):
        prefix = 'cpu' if identifier == CPU_ID else 'gpu-cancel' if identifier == CANCEL_GPU_ID else 'gpu-retry'
        self.context['phase'] = prefix + '-work'
        self.wait(lambda: identifier in self.states and self.states[identifier]['status'] != 'running')
        require(self.states[identifier]['status'] == status, 'Workload terminal status invalid')
        self.context['phase'] = prefix + '-guest-report'
        self.wait(lambda: MARKERS[identifier] in self.observation(), 20)
        self.context['phase'] = prefix + '-idle'
        self.idle()

    def run(self):
        self.wait(lambda: self.ready is not None and 'MYPC_HARDWARE_GUEST_OBSERVER_READY=1' in self.observation(), 300)
        self.context['phase'] = 'cpu-start'; self.send('cpu', CPU_ID)
        self.context['phase'] = 'cpu-ack'; self.acknowledge(CPU_ID); self.finished(CPU_ID, 'complete')
        self.context['phase'] = 'gpu-cancel-start'; self.send('gpu', CANCEL_GPU_ID)
        self.context['phase'] = 'gpu-cancel-ack'; self.acknowledge(CANCEL_GPU_ID)
        self.context['phase'] = 'gpu-work'
        self.wait(lambda: gpu_work(self.states.get(CANCEL_GPU_ID, {}), CANCEL_GPU_FRAMES))
        self.context['phase'] = 'gpu-guest-work'
        self.wait(lambda: 'MYPC_HARDWARE_GUEST_GPU_WORK_OBSERVED=1' in self.observation(), 10)
        # Recheck after waiting for independent evidence: completion cannot
        # masquerade as Stop during GPU work.
        self.context['phase'] = 'gpu-drain'; self.drain()
        require(gpu_work(self.states[CANCEL_GPU_ID], CANCEL_GPU_FRAMES), 'GPU finished before cancellation')
        self.context['phase'] = 'gpu-cancel'; self.send('cancel', CANCEL_ID, CANCEL_GPU_ID)
        self.context['phase'] = 'gpu-cancel-command-ack'; self.acknowledge(CANCEL_ID)
        self.finished(CANCEL_GPU_ID, 'cancelled')
        self.context['phase'] = 'gpu-retry-start'; self.send('gpu', RETRY_GPU_ID)
        self.context['phase'] = 'gpu-retry-ack'; self.acknowledge(RETRY_GPU_ID); self.finished(RETRY_GPU_ID, 'complete')
        self.context['phase'] = 'validate-results'
        for identifier in (CPU_ID, RETRY_GPU_ID):
            updates = self.history[identifier]
            require(len(updates) > 1 and updates[0][1] <= 10 and updates[-1][1] == 100,
                    'Initial/progress/completion observations missing')
        return {'cpu': metrics(self.states[CPU_ID]), 'gpu': metrics(self.states[RETRY_GPU_ID]),
                'gpu_cancelled_during_work': True, 'ack_and_state_ids_matched': True,
                'independent_guest_reports_matched': True}


def run_socket(path, observation, stop):
    host = None
    deadline = time.monotonic() + 300
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as transport:
            while True:
                try: transport.connect(str(path)); break
                except OSError:
                    require(not stop.is_set() and time.monotonic() < deadline, 'Diagnostic socket unavailable')
                    stop.wait(0.1)
            transport.settimeout(0.1)
            host = Host(transport, observation, stop)
            return host.run()
    except BaseException as error:
        try: observed = observation()
        except BaseException: observed = ''
        context = host.context if host is not None else {'phase': 'connect'}
        print('MYPC_HARDWARE_HOST_FAILURE ' + json.dumps(failure(error, context, observed), sort_keys=True), flush=True)
        raise
