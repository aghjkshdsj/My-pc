#!/usr/bin/env python3
"""Steam-user diagnostic control over a private local virtio-serial port.

Newline JSON requests are <=512 bytes: schema=1, id=32 lowercase UUID hex,
command=cpu|gpu|cancel|status. Cancel additionally requires the active run's
request ID in target. No paths, executable arguments or shell input are accepted.
Responses are <=16384 bytes including newline. Workload state is correlated to
the originating request; status/reconnection replay never starts another test.
"""
import collections
import contextlib
import json
import os
import pathlib
import re
import select
import subprocess
import sys
import tempfile
import threading
import time

MAX_REQUEST = 512
MAX_FRAME = 16384
LAUNCH_TIMEOUT = 10
CANCEL_TIMEOUT = 15
ID = re.compile(r'[0-9a-f]{32}\Z')
PORT = pathlib.Path('/dev/virtio-ports/org.my-pc.diagnostics')
CI_DIRECTORY = pathlib.Path('/tmp/my-pc-hardware-control-ci')


def request(value):
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1:
        return None
    if not isinstance(value.get('id'), str) or not ID.fullmatch(value['id']): return None
    command = value.get('command')
    if command not in ('cpu', 'gpu', 'cancel', 'status'): return None
    expected = {'schema', 'id', 'command'} | ({'target'} if command == 'cancel' else set())
    if set(value) != expected: return None
    if command == 'cancel' and (not isinstance(value['target'], str) or not ID.fullmatch(value['target'])):
        return None
    return value


class Parser:
    def __init__(self): self.pending, self.discarding = bytearray(), False

    def feed(self, chunk):
        values = []
        for byte in chunk:
            if byte == 10:
                if not self.discarding:
                    try: value = request(json.loads(self.pending))
                    except (ValueError, UnicodeError): value = None
                    if value is not None: values.append(value)
                self.pending.clear(); self.discarding = False
            elif not self.discarding:
                self.pending.append(byte)
                if len(self.pending) >= MAX_REQUEST:
                    self.pending.clear(); self.discarding = True
        return values


def frame(value):
    encoded = (json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n').encode()
    if len(encoded) > MAX_FRAME: raise ValueError('Diagnostic frame exceeds limit')
    return encoded


class Writer:
    """Bound memory and preserve partial frames under host backpressure."""
    def __init__(self): self.queue, self.pending = collections.deque(), b''

    def offer(self, value):
        encoded = frame(value)
        kind = value['type']
        if kind in ('ready', 'state', 'failure'):
            self.queue = collections.deque((key, data) for key, data in self.queue if key != kind)
        if len(self.queue) >= 32: self.queue.popleft()
        self.queue.append((kind, encoded))

    def flush(self, fd):
        # At most one frame per iteration; a guest flood cannot monopolize control.
        if not self.pending and self.queue: _, self.pending = self.queue.popleft()
        if self.pending:
            try:
                count = os.write(fd, self.pending)
                self.pending = self.pending[count:]
            except BlockingIOError: pass


def state_record(value, kind):
    """Accept only the fixed benchmark schema from our private child file."""
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1 or value.get('kind') != kind:
        raise ValueError('Invalid diagnostic report')
    import uuid
    if not isinstance(value.get('run'), str) or len(value['run']) != 36:
        raise ValueError('Invalid diagnostic run')
    uuid.UUID(value['run'])
    if value.get('status') not in ('running', 'complete', 'failed', 'cancelled'):
        raise ValueError('Invalid diagnostic status')
    if type(value.get('heartbeat_seq')) is not int or not 1 <= value['heartbeat_seq'] <= 10_000_000:
        raise ValueError('Invalid diagnostic sequence')
    if not isinstance(value.get('results'), list) or len(value['results']) > 4:
        raise ValueError('Invalid diagnostic results')
    if not isinstance(value.get('stage'), str) or len(value['stage']) > 64:
        raise ValueError('Invalid diagnostic stage')
    for row in value['results']:
        if not isinstance(row, dict) or row.get('mode') not in ('arm64', 'fex') or row.get('kind') != kind:
            raise ValueError('Invalid diagnostic result')
        if row.get('status') not in ('passed', 'failed', 'timeout'):
            raise ValueError('Invalid diagnostic result status')
    allowed = {'schema','run','kind','status','stage','progress_percent','heartbeat_seq','elapsed_s',
               'stage_elapsed_s','results','idle_guest','work_done','work_total','work_unit','work_stage'}
    result = {key: item for key, item in value.items() if key in allowed}
    frame({'schema':1, 'type':'state', 'id':'0'*32, 'state':result})
    return result


class Launch:
    """Popen's exec-error pipe cannot block command/Stop/health processing."""
    def __init__(self, command, spawn):
        self.lock, self.child, self.error = threading.Lock(), None, False
        self.abandoned, self.signalled = False, False
        self.finished = threading.Event()
        def start():
            try:
                child = spawn(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, start_new_session=True)
                with self.lock:
                    self.child = child
                    abandoned = self.abandoned
                if abandoned:
                    # The handle belongs only to the process we just launched.
                    self.terminate_once()
            except BaseException:
                with self.lock: self.error = True
            finally: self.finished.set()
        threading.Thread(target=start, daemon=True).start()

    def abandon(self):
        with self.lock:
            self.abandoned = True
        self.terminate_once()

    def terminate_once(self):
        with self.lock:
            child = self.child
            if child is None or self.signalled: return
            self.signalled = True
        if child is not None and child.poll() is None:
            try: child.terminate()
            except ProcessLookupError: pass


class Controller:
    def __init__(self, directory, emit, spawn=subprocess.Popen, clock=time.monotonic):
        self.directory, self.emit, self.spawn, self.clock = pathlib.Path(directory), emit, spawn, clock
        self.runner = pathlib.Path(__file__).with_name('hardware-test.py')
        self.report = self.directory/'runner.json'
        self.evidence = self.directory/'state.json'
        self.job, self.latest, self.last_failure = None, None, None
        self.seen = set()

    @property
    def busy(self): return self.job is not None

    def ready(self):
        self.emit({'schema':1, 'type':'ready', 'ready':True, 'busy':self.busy})

    def replay(self):
        if self.latest: self.emit(self.latest)
        if self.last_failure: self.emit(self.last_failure)

    def failure(self, code, busy):
        self.last_failure = {'schema':1, 'type':'failure', 'id':self.job['id'], 'code':code, 'busy':busy}
        self.emit(self.last_failure)

    def handle(self, value):
        value = request(value)
        if value is None: return
        identifier, command = value['id'], value['command']
        def ack(status):
            self.emit({'schema':1, 'type':'ack', 'id':identifier, 'command':command, 'status':status})
        if identifier in self.seen:
            ack('duplicate')
            if command == 'status': self.replay()
            return
        # Never forget an ID and accidentally rerun a very old duplicated start.
        # A new VM session clears this bounded session-level request history.
        # Saturated replay protection disables new starts for this VM session,
        # but health queries and Stop must remain available to the host.
        if len(self.seen) < 1024: self.seen.add(identifier)
        elif command in ('cpu', 'gpu'): ack('busy'); return
        if command == 'status':
            ack('accepted'); self.ready(); self.replay(); return
        if command == 'cancel':
            if self.job is None: ack('idle'); return
            if value['target'] != self.job['id']: ack('stale'); return
            ack('accepted')
            if self.job['cancelled'] is None:
                self.job['cancelled'] = self.clock()
                self.job['launch'].abandon()
            return
        if self.busy: ack('busy'); return
        self.report.unlink(missing_ok=True)
        self.latest = self.last_failure = None
        launch = Launch([sys.executable, '-u', str(self.runner), command, '--no-serial',
                         '--result-file', str(self.report)], self.spawn)
        self.job = {'id':identifier, 'kind':command, 'launch':launch, 'started':self.clock(),
                    'cancelled':None, 'last_bytes':None, 'failure':None}
        ack('accepted')

    def poll(self):
        job = self.job
        if job is None: return
        now, launch = self.clock(), job['launch']
        if not launch.finished.is_set():
            if now-job['started'] >= LAUNCH_TIMEOUT and not job['failure']:
                job['failure'] = 'launch-timeout'; launch.abandon()
                self.failure('launch-timeout', True)
            return
        if launch.error or launch.child is None:
            self.failure('launch-failed', False); self.job = None; return
        child = launch.child
        if job['failure'] != 'launch-timeout':
            try:
                with self.report.open('rb') as stream: data = stream.read(MAX_FRAME+1)
                if data != job['last_bytes']:
                    if len(data) > MAX_FRAME: raise ValueError('Oversize report')
                    state = state_record(json.loads(data), job['kind'])
                    if self.latest and (state['run'] != self.latest['state']['run'] or
                                        state['heartbeat_seq'] <= self.latest['state']['heartbeat_seq']):
                        raise ValueError('Diagnostic report regressed or changed run')
                    self.latest = {'schema':1, 'type':'state', 'id':job['id'], 'state':state}
                    temporary = self.evidence.with_suffix('.new')
                    temporary.write_bytes(frame(self.latest)); temporary.replace(self.evidence)
                    job['last_bytes'] = data
                    self.emit(self.latest)
            except FileNotFoundError: pass
            except (ValueError, TypeError, KeyError, OSError):
                if not job['failure']:
                    job['failure'] = 'report-invalid'; launch.abandon()
                    self.failure('report-invalid', child.poll() is None)
        if child.poll() is not None:
            terminal = self.latest and self.latest['state']['status'] != 'running'
            if job['failure']:
                self.failure(job['failure'], False)
            elif not terminal:
                self.failure('launch-cancelled' if job['cancelled'] is not None else 'runner-exited', False)
            self.job = None
        elif job['cancelled'] is not None and now-job['cancelled'] >= CANCEL_TIMEOUT and not job['failure']:
            job['failure'] = 'cancellation-timeout'
            self.failure('cancellation-timeout', True)


@contextlib.contextmanager
def control_directory():
    """CI observes the same private files independently of serial delivery."""
    if os.environ.get('MYPC_HARDWARE_CI') != '1':
        with tempfile.TemporaryDirectory(prefix='my-pc-hardware-control-') as directory:
            yield pathlib.Path(directory)
        return
    CI_DIRECTORY.mkdir(mode=0o700, exist_ok=True)
    details = CI_DIRECTORY.lstat()
    if CI_DIRECTORY.is_symlink() or not CI_DIRECTORY.is_dir() or details.st_uid != os.getuid():
        raise ValueError('Unsafe diagnostic CI directory')
    CI_DIRECTORY.chmod(0o700)
    # Only our fixed-name atomic reports are cleared on a service restart.
    for name in ('runner.json', 'runner.new', 'state.json', 'state.new'):
        (CI_DIRECTORY/name).unlink(missing_ok=True)
    yield CI_DIRECTORY


def main():
    # The directory and its atomic files are private to this desktop's steam user.
    # The runner keeps the inherited DISPLAY/XAUTHORITY for GPU work.
    with control_directory() as directory:
        writer = Writer()
        controller = Controller(directory, writer.offer)
        parser, fd, last_ready = Parser(), None, 0.0
        while True:
            controller.poll()
            now = time.monotonic()
            if now-last_ready >= 1:
                controller.ready(); controller.replay(); last_ready = now
            if fd is None:
                try: fd = os.open(PORT, os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC)
                except OSError: time.sleep(0.1); continue
            try:
                readable, _, _ = select.select([fd], [], [], 0.05)
                if readable:
                    data = os.read(fd, 4096)
                    if data:
                        for value in parser.feed(data): controller.handle(value)
                    else:
                        parser = Parser()
                        time.sleep(0.05)
                writer.flush(fd)
            except OSError:
                os.close(fd); fd = None
                parser, writer = Parser(), Writer()
                controller.emit = writer.offer


if __name__ == '__main__': main()
