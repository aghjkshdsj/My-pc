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
CPU_ID, CANCEL_GPU_ID, RETRY_GPU_ID, CANCEL_ID = (digit * 32 for digit in '1234')
GUEST_DIRECTORY = pathlib.Path('/tmp/my-pc-hardware-control-ci')
MARKERS = {
    CPU_ID: 'MYPC_HARDWARE_GUEST_CPU_COMPLETE=1',
    CANCEL_GPU_ID: 'MYPC_HARDWARE_GUEST_GPU_CANCELLED=1',
    RETRY_GPU_ID: 'MYPC_HARDWARE_GUEST_GPU_COMPLETE=1',
}


def require(condition, message):
    if not condition: raise ValueError(message)


def number(value, maximum=1e12):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


def pressure(value):
    require(isinstance(value, dict) and value.get('status') == 'measured', 'Idle/load sample missing')
    require(value.get('online_cpus') == 6 and number(value.get('sample_seconds'))
            and value['sample_seconds'] > 0, 'Six-core sample required')
    cores = value.get('per_core')
    require(isinstance(cores, list) and len(cores) == 6, 'Six-core sample incomplete')
    require({row.get('core') for row in cores if isinstance(row, dict)} == set(range(6)), 'Core identities invalid')
    for row in cores:
        require(type(row['core']) is int and number(row.get('busy_percent'), 100)
                and number(row.get('iowait_percent'), 100), 'Core load invalid')
    labels = value.get('process_cpu_percent')
    require(isinstance(labels, dict) and set(labels) <= {'steam', 'steam_webhelper', 'xorg', 'fex', 'test'}
            and all(number(item, 600) for item in labels.values()), 'Process sample invalid')
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
    if 'idle_guest' in value: pressure(value['idle_guest'])
    for row in rows:
        require(isinstance(row, dict) and row.get('mode') in ('arm64', 'fex')
                and row.get('kind') == value['kind'] and row.get('status') in
                ('passed', 'failed', 'timeout'), 'Result identity invalid')
        if row['status'] != 'passed': continue
        pressure(row.get('guest_load'))
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
        pressure(value.get('idle_guest'))
        require(value['progress_percent'] == 100 and all(row['status'] == 'passed' for row in rows),
                'Completion results invalid')
        expected = [('arm64', 1), ('arm64', 6), ('fex', 1), ('fex', 6)] if value['kind'] == 'cpu' else [('arm64', None), ('fex', None)]
        require([(row['mode'], row.get('workers') if value['kind'] == 'cpu' else None) for row in rows] == expected,
                'ARM/FEX coverage incomplete')
    return value


def gpu_work(value):
    return (value.get('kind') == 'gpu' and value.get('status') == 'running'
            and value.get('work_stage') == 'frames' and type(value.get('work_done')) is int
            and type(value.get('work_total')) is int and 0 < value['work_done'] < value['work_total'])


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
            'idle_guest': pressure(value['idle_guest']),
            'results': [dict(mode=row['mode'], kind=row['kind'], status=row['status'],
                             guest_load=pressure(row['guest_load']),
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

    def send(self, command, identifier=None, target=None):
        identifier = identifier or uuid.uuid4().hex
        self.commands[identifier] = command
        payload = {'schema': 1, 'id': identifier, 'command': command}
        if target is not None: payload['target'] = target
        self.transport.sendall((json.dumps(payload, separators=(',', ':')) + '\n').encode())
        return identifier

    def poll(self):
        if not self.queue:
            try: chunk = self.transport.recv(4096)
            except socket.timeout: return
            require(bool(chunk), 'Diagnostic transport disconnected')
            self.queue.extend(self.parser.feed(chunk))
        if not self.queue: return
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
            current = state(value['state'])
            require(current['kind'] == self.commands[identifier], 'State workload correlation invalid')
            previous = self.states.get(identifier)
            if previous:
                require(current['run'] == previous['run'] and current['heartbeat_seq'] >= previous['heartbeat_seq']
                        and current['progress_percent'] >= previous['progress_percent'], 'State regressed')
                if current['heartbeat_seq'] == previous['heartbeat_seq']:
                    require(current == previous, 'Heartbeat replay changed'); return
            self.states[identifier] = current
            history = self.history.setdefault(identifier, [])
            history.append((current['heartbeat_seq'], current['progress_percent']))
            require(len(history) <= 4096, 'Excess diagnostic updates')
        elif kind == 'failure':
            raise ValueError('Diagnostic control failure')
        else: raise ValueError('Diagnostic response type invalid')

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
        self.wait(lambda: identifier in self.states and self.states[identifier]['status'] != 'running')
        require(self.states[identifier]['status'] == status, 'Workload terminal status invalid')
        self.wait(lambda: MARKERS[identifier] in self.observation(), 20)
        self.idle()

    def run(self):
        self.wait(lambda: self.ready is not None and 'MYPC_HARDWARE_GUEST_OBSERVER_READY=1' in self.observation(), 300)
        self.send('cpu', CPU_ID); self.acknowledge(CPU_ID); self.finished(CPU_ID, 'complete')
        self.send('gpu', CANCEL_GPU_ID); self.acknowledge(CANCEL_GPU_ID)
        self.wait(lambda: gpu_work(self.states.get(CANCEL_GPU_ID, {})))
        self.wait(lambda: 'MYPC_HARDWARE_GUEST_GPU_WORK_OBSERVED=1' in self.observation(), 10)
        # Recheck after waiting for independent evidence: completion cannot
        # masquerade as Stop during GPU work.
        require(gpu_work(self.states[CANCEL_GPU_ID]), 'GPU finished before cancellation')
        self.send('cancel', CANCEL_ID, CANCEL_GPU_ID); self.acknowledge(CANCEL_ID)
        self.finished(CANCEL_GPU_ID, 'cancelled')
        self.send('gpu', RETRY_GPU_ID); self.acknowledge(RETRY_GPU_ID); self.finished(RETRY_GPU_ID, 'complete')
        for identifier in (CPU_ID, RETRY_GPU_ID):
            updates = self.history[identifier]
            require(len(updates) > 1 and updates[0][1] <= 10 and updates[-1][1] == 100,
                    'Initial/progress/completion observations missing')
        return {'cpu': metrics(self.states[CPU_ID]), 'gpu': metrics(self.states[RETRY_GPU_ID]),
                'gpu_cancelled_during_work': True, 'ack_and_state_ids_matched': True,
                'independent_guest_reports_matched': True}


def run_socket(path, observation, stop):
    deadline = time.monotonic() + 300
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as transport:
        while True:
            try: transport.connect(str(path)); break
            except OSError:
                require(not stop.is_set() and time.monotonic() < deadline, 'Diagnostic socket unavailable')
                stop.wait(0.1)
        transport.settimeout(0.1)
        return Host(transport, observation, stop).run()
