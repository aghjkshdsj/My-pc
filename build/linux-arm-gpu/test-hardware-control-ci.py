"""Check the private host gate, independent evidence and safe metric export."""
import copy
import importlib.util
import json
import pathlib
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('control_ci', pathlib.Path(__file__).with_name('hardware-control-ci.py'))
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
guest_spec = importlib.util.spec_from_file_location('guest_ci', pathlib.Path(__file__).with_name('hardware-test-ci.py'))
guest = importlib.util.module_from_spec(guest_spec); guest_spec.loader.exec_module(guest)


def pressure():
    return {'status': 'measured', 'online_cpus': 6, 'sample_seconds': 3.2,
            'per_core': [{'core': core, 'busy_percent': 3.5, 'iowait_percent': 0} for core in range(6)],
            'process_cpu_percent': {'test': 80}, 'mem_available_mib': 900, 'swap_used_mib': 0}


def state(kind='cpu', status='running', sequence=1, progress=0):
    value = {'schema': 1, 'run': '00000000-0000-0000-0000-000000000001', 'kind': kind,
             'status': status, 'stage': 'finished' if status == 'complete' else 'sampling-idle',
             'heartbeat_seq': sequence, 'progress_percent': progress, 'elapsed_s': sequence,
             'stage_elapsed_s': sequence, 'idle_guest': pressure(), 'results': []}
    if status == 'complete':
        for mode in ('arm64', 'fex'):
            for workers in ((1, 6) if kind == 'cpu' else (None,)):
                row = {'kind': kind, 'mode': mode, 'status': 'passed', 'guest_load': pressure(), 'launch_total_ms': 150}
                if kind == 'cpu':
                    row.update(workers=workers, iterations_per_worker=1000000, samples=3,
                               checksum='0123456789abcdef', wall_median_ms=25, process_cpu_median_ms=40, million_iterations_s=40)
                else:
                    row.update(arch='aarch64' if mode == 'arm64' else 'x86_64', renderer='virgl (ANGLE Metal Renderer)',
                               readback_ok=True, accelerated=True, frames=60, width=800, height=500,
                               draws_per_frame=16, wall_ms=800, render_fps=75, submit_median_ms=0.2,
                               submit_p95_ms=0.3, finish_median_ms=2, finish_p95_ms=3, swap_median_ms=1, swap_p95_ms=2)
                value['results'].append(row)
    return value


class ScriptedTransport:
    """Protocol fixture; real VM workloads are checked separately by release CI."""
    def __init__(self, evidence=True, cancel_work=True):
        self.pending, self.requests, self.markers = bytearray(), [], ['MYPC_HARDWARE_GUEST_OBSERVER_READY=1']
        self.evidence, self.cancel_work, self.latest = evidence, cancel_work, None
        self.timeout = 0.1
        self.offer({'schema': 1, 'type': 'ready', 'ready': True, 'busy': False})

    def offer(self, value): self.pending.extend((json.dumps(value) + '\n').encode())

    def publish(self, identifier, value):
        self.latest = {'schema': 1, 'type': 'state', 'id': identifier, 'state': value}
        self.offer(self.latest)

    def sendall(self, encoded):
        value = json.loads(encoded); self.requests.append(value)
        identifier, command = value['id'], value['command']
        self.offer({'schema': 1, 'type': 'ack', 'id': identifier, 'command': command, 'status': 'accepted'})
        if command == 'status':
            self.offer({'schema': 1, 'type': 'ready', 'ready': True, 'busy': False})
            self.offer(self.latest)
        elif command == 'cancel':
            assert value['target'] == ci.CANCEL_GPU_ID
            result = state('gpu', 'cancelled', 3, 25)
            self.publish(ci.CANCEL_GPU_ID, result)
            if self.evidence: self.markers.append(ci.MARKERS[ci.CANCEL_GPU_ID])
        elif identifier == ci.CANCEL_GPU_ID:
            self.publish(identifier, state('gpu'))
            if self.cancel_work:
                result = state('gpu', sequence=2, progress=25)
                result.update(stage='arm64-gpu-1', work_stage='frames', work_done=8, work_total=ci.CANCEL_GPU_FRAMES)
                self.publish(identifier, result)
                if self.evidence: self.markers.append('MYPC_HARDWARE_GUEST_GPU_WORK_OBSERVED=1')
            else: self.publish(identifier, state('gpu', 'complete', 3, 100))
        else:
            self.publish(identifier, state(command))
            self.publish(identifier, state(command, 'complete', 4, 100))
            if self.evidence: self.markers.append(ci.MARKERS[identifier])

    def recv(self, count):
        if not self.pending: raise socket.timeout()
        # Exercise actual fragmentation and coalesced queued records.
        chunk = bytes(self.pending[:min(count, 97)]); del self.pending[:len(chunk)]
        return chunk

    def gettimeout(self): return self.timeout
    def setblocking(self, value): self.timeout = None if value else 0
    def settimeout(self, value): self.timeout = value


class ControlGate(unittest.TestCase):
    def host(self, transport):
        return ci.Host(transport, lambda: '\n'.join(transport.markers), threading.Event(), timeout=0.25)

    def test_cpu_gpu_cancel_during_work_and_retry_use_private_commands(self):
        transport = ScriptedTransport(); result = self.host(transport).run()
        starts = [(row['command'], row['id']) for row in transport.requests if row['command'] in ('cpu', 'gpu')]
        self.assertEqual(starts, [('cpu', ci.CPU_ID), ('gpu', ci.CANCEL_GPU_ID), ('gpu', ci.RETRY_GPU_ID)])
        self.assertTrue(result['gpu_cancelled_during_work'])
        self.assertEqual([row['workers'] for row in result['cpu']['results']], [1, 6, 1, 6])
        self.assertTrue(all(row['readback_ok'] and row['accelerated'] for row in result['gpu']['results']))

    def test_serial_completion_cannot_pass_without_guest_report(self):
        transport = ScriptedTransport(evidence=False); host = self.host(transport)
        host.send('cpu', ci.CPU_ID); host.acknowledge(ci.CPU_ID)
        host.wait(lambda: ci.CPU_ID in host.states and host.states[ci.CPU_ID]['status'] == 'complete')
        with self.assertRaisesRegex(ValueError, 'deadline'):
            host.wait(lambda: ci.MARKERS[ci.CPU_ID] in host.observation(), 0.001)

    def test_completed_gpu_cannot_pass_as_cancel_during_work(self):
        transport = ScriptedTransport(cancel_work=False); host = self.host(transport)
        host.send('gpu', ci.CANCEL_GPU_ID); host.acknowledge(ci.CANCEL_GPU_ID)
        with self.assertRaisesRegex(ValueError, 'deadline'):
            host.wait(lambda: ci.gpu_work(host.states.get(ci.CANCEL_GPU_ID, {})), 0.001)

    def test_ack_and_state_must_match_request_id_and_kind(self):
        for frame in ({'schema': 1, 'type': 'ack', 'id': ci.RETRY_GPU_ID, 'command': 'cpu', 'status': 'accepted'},
                      {'schema': 1, 'type': 'state', 'id': ci.CPU_ID, 'state': state('gpu')}):
            transport = ScriptedTransport(); transport.pending.clear(); transport.offer(frame)
            host = self.host(transport); host.commands[ci.CPU_ID] = 'cpu'
            with self.assertRaisesRegex(ValueError, 'correlation'):
                host.wait(lambda: False, 0.25)

    def test_heartbeat_replay_must_be_identical_and_cannot_regress(self):
        transport = ScriptedTransport(); transport.pending.clear()
        host = self.host(transport); host.commands[ci.CPU_ID] = 'cpu'
        for value in (state(sequence=3, progress=20), state(sequence=2, progress=10)):
            transport.offer({'schema': 1, 'type': 'state', 'id': ci.CPU_ID, 'state': value})
        with self.assertRaisesRegex(ValueError, 'regressed'): host.wait(lambda: False, 0.25)

    def test_gpu_shader_pixels_and_fex_are_required(self):
        for transform in (lambda value: value['results'].pop(),
                          lambda value: value['results'][0].update(readback_ok=False),
                          lambda value: value['results'][1].update(renderer='llvmpipe software'),
                          lambda value: value['results'][0].update(render_fps=float('nan'))):
            value = state('gpu', 'complete', 4, 100); transform(value)
            with self.assertRaises(ValueError): ci.state(value)

    def test_cpu_six_core_idle_native_fex_and_checksum_shapes_required(self):
        for transform in (lambda value: value['idle_guest']['per_core'].pop(),
                          lambda value: value['results'][1].update(workers=2),
                          lambda value: value['results'][0].update(checksum='private-account'),
                          lambda value: value['results'][0].update(wall_median_ms=float('inf'))):
            value = state('cpu', 'complete', 4, 100); transform(value)
            with self.assertRaises(ValueError): ci.state(value)

    def test_output_redacts_nested_unknown_fields_and_free_text(self):
        value = state('gpu', 'complete', 4, 100)
        value.update(account='private-account', stage='private-account')
        value['idle_guest']['account'] = 'private-account'
        value['idle_guest']['per_core'][0]['account'] = 'private-account'
        for row in value['results']:
            row.update(account='private-account', version='private-account', workers='private-account')
            row['guest_load']['account'] = 'private-account'
        result = ci.metrics(value)
        self.assertNotIn('private-account', json.dumps(result))
        self.assertEqual(ci.validated_metrics(result), result)
        polluted = copy.deepcopy(result); polluted['results'][0]['account'] = 'private-account'
        with self.assertRaises(ValueError): ci.validated_metrics(polluted)

    def test_fragmentation_and_oversized_frames_are_bounded(self):
        parser = ci.Frames(); encoded = b'{"schema":1,"type":"ready"}\n'
        self.assertEqual(parser.feed(encoded[:8]), [])
        self.assertEqual(len(parser.feed(encoded[8:] + encoded)), 2)
        with self.assertRaises(ValueError): ci.Frames().feed(b'x' * ci.MAX_FRAME)
        with self.assertRaises(ValueError): ci.Frames().feed(b'x' * ci.MAX_FRAME + b'\n')

    def test_stop_interrupts_bounded_host_wait(self):
        host = self.host(ScriptedTransport()); host.stop.set()
        with self.assertRaisesRegex(ValueError, 'stopped'): host.wait(lambda: False)

    def test_snapshot_timeout_is_reported_honestly_without_hiding_real_work(self):
        value = state('cpu', 'complete', 4, 100)
        value['idle_guest'] = {'status': 'unavailable', 'reason': 'sampling-timeout'}
        value['results'][0]['guest_load'] = {'status': 'unavailable', 'reason': 'sampling-timeout'}
        value['results'][1]['guest_load'].update(sample_seconds=0, per_core=[])
        value['results'][2]['guest_load']['process_cpu_percent'] = {'test': 615.3}
        result = ci.metrics(value)
        self.assertEqual(result['idle_guest'], {'status': 'unavailable', 'reason': 'sampling-timeout'})
        self.assertEqual([row['workers'] for row in result['results']], [1, 6, 1, 6])
        self.assertEqual(ci.validated_metrics(result), result)
        value['idle_guest'] = pressure(); value['idle_guest']['per_core'].pop()
        with self.assertRaisesRegex(ci.GateError, 'Six-core'): ci.metrics(value)

    def test_unavailable_load_does_not_accept_arbitrary_error_strings(self):
        value = state('gpu', 'complete', 4, 100)
        value['idle_guest'] = {'status': 'unavailable', 'reason': 'private-account'}
        with self.assertRaises(ci.GateError): ci.metrics(value)

    def test_fixed_failure_evidence_never_contains_arbitrary_exception_text(self):
        value = state('gpu', 'failed', 7, 25)
        value.update(stage='workload-failed', work_stage='frames')
        value['results'] = [{'mode': 'fex', 'status': 'failed', 'stage': 'libraries', 'account': 'private-account'}]
        error = ci.GateError('Diagnostic control failure', 'report-invalid')
        result = ci.failure(error, {'phase': 'gpu-retry-work', 'state': value},
                            'MYPC_CONTROLLER_READY=1 MYPC_CONTROLLER_OBSERVER_READY=1')
        self.assertEqual(result['code'], 'control-service-failure')
        self.assertEqual(result['service_code'], 'report-invalid')
        self.assertEqual((result['kind'], result['status'], result['heartbeat_seq']), ('gpu', 'failed', 7))
        self.assertEqual(result['last_result_stage'], 'libraries')
        self.assertEqual(ci.validated_failure(result), result)
        self.assertNotIn('private-account', json.dumps(result))
        generic = ci.failure(ValueError('private-account'), {'phase': 'private-account', 'state': {'kind': 'private-account'}})
        self.assertEqual(generic['code'], 'invalid-value'); self.assertEqual(generic['phase'], 'unknown')
        self.assertNotIn('private-account', json.dumps(generic))
        polluted = copy.deepcopy(result); polluted['code'] = 'private-account'
        with self.assertRaises(ci.GateError): ci.validated_failure(polluted)

    def test_validation_failure_captures_correlated_state_before_rejecting_it(self):
        transport = ScriptedTransport(); transport.pending.clear()
        value = state('gpu', 'complete', 4, 100); value['results'][1]['readback_ok'] = False
        transport.offer({'schema': 1, 'type': 'state', 'id': ci.RETRY_GPU_ID, 'state': value})
        host = self.host(transport); host.commands[ci.RETRY_GPU_ID] = 'gpu'; host.context['phase'] = 'gpu-retry-work'
        with self.assertRaises(ci.GateError) as caught: host.wait(lambda: False, 0.25)
        result = ci.failure(caught.exception, host.context)
        self.assertEqual(result['code'], 'gpu-pixels-invalid')
        self.assertEqual(result['heartbeat_seq'], 4); self.assertEqual(result['last_result_mode'], 'fex')

    def test_guest_reads_matching_private_files_and_independent_checksums(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary); markers = []
            checksums = directory/'checksums.json'
            checksums.write_text(json.dumps({'1:1000000': '0123456789abcdef', '6:1000000': '0123456789abcdef'}))
            def write(identifier, value):
                (directory/'runner.json').write_text(json.dumps(value))
                (directory/'state.json').write_text(json.dumps({'schema': 1, 'type': 'state', 'id': identifier, 'state': value}))
            def emitted(value, **_):
                markers.append(value)
                if value == 'MYPC_HARDWARE_GUEST_OBSERVER_READY=1':
                    write(ci.CPU_ID, state('cpu', 'complete', 4, 100))
                elif value == ci.MARKERS[ci.CPU_ID]:
                    working = state('gpu', sequence=2, progress=25)
                    working.update(stage='arm64-gpu-1', work_stage='frames', work_done=8, work_total=ci.CANCEL_GPU_FRAMES)
                    write(ci.CANCEL_GPU_ID, working)
                elif value == 'MYPC_HARDWARE_GUEST_GPU_WORK_OBSERVED=1':
                    write(ci.CANCEL_GPU_ID, state('gpu', 'cancelled', 3, 25))
                elif value == ci.MARKERS[ci.CANCEL_GPU_ID]:
                    write(ci.RETRY_GPU_ID, state('gpu', 'complete', 4, 100))
            with patch('builtins.print', side_effect=emitted), patch.object(guest.time, 'sleep'):
                guest.observe(directory, checksums, timeout=1)
            self.assertTrue(set(ci.MARKERS.values()) <= set(markers))
            self.assertIn('MYPC_HARDWARE_GUEST_GPU_WORK_OBSERVED=1', markers)

    def test_guest_cannot_accept_serial_evidence_without_matching_runner(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            checksums = directory/'checksums.json'; checksums.write_text('{}')
            (directory/'runner.json').write_text(json.dumps(state('cpu')))
            (directory/'state.json').write_text(json.dumps({'schema': 1, 'type': 'state', 'id': ci.CPU_ID,
                                                         'state': state('cpu', 'complete', 4, 100)}))
            with patch('builtins.print') as printed, patch.object(guest.time, 'sleep'), \
                 patch.object(guest.time, 'monotonic', side_effect=[0, 0, 2]):
                with self.assertRaisesRegex(ValueError, 'deadline'): guest.observe(directory, checksums, timeout=1)
            self.assertEqual([call.args[0] for call in printed.call_args_list], ['MYPC_HARDWARE_GUEST_OBSERVER_READY=1'])

    def test_drain_replaces_stale_gpu_work_before_stop(self):
        transport = ScriptedTransport(); transport.pending.clear()
        host = self.host(transport); host.commands[ci.CANCEL_GPU_ID] = 'gpu'
        working = state('gpu', sequence=2, progress=25)
        working.update(stage='arm64-gpu-1', work_stage='frames', work_done=8, work_total=ci.CANCEL_GPU_FRAMES)
        host.states[ci.CANCEL_GPU_ID] = working
        transport.publish(ci.CANCEL_GPU_ID, state('gpu', 'complete', 4, 100))
        self.assertTrue(ci.gpu_work(host.states[ci.CANCEL_GPU_ID], ci.CANCEL_GPU_FRAMES))
        host.drain()
        self.assertFalse(ci.gpu_work(host.states[ci.CANCEL_GPU_ID], ci.CANCEL_GPU_FRAMES))
        self.assertEqual(transport.gettimeout(), 0.1)
        self.assertFalse(any(row['command'] == 'cancel' for row in transport.requests))

    def test_cancel_probe_requires_requested_real_frame_total(self):
        value = state('gpu', sequence=2, progress=25)
        value.update(stage='arm64-gpu-1', work_stage='frames', work_done=8, work_total=60)
        self.assertFalse(ci.gpu_work(value, ci.CANCEL_GPU_FRAMES))
        value['work_total'] = ci.CANCEL_GPU_FRAMES
        self.assertTrue(ci.gpu_work(value, ci.CANCEL_GPU_FRAMES))
        value['work_done'] = ci.CANCEL_GPU_FRAMES
        self.assertFalse(ci.gpu_work(value, ci.CANCEL_GPU_FRAMES))
        value['work_done'] = True
        self.assertFalse(ci.gpu_work(value, ci.CANCEL_GPU_FRAMES))
        value.update(work_done=8, work_total=6001)
        self.assertFalse(ci.gpu_work(value, 6001))
        value.update(work_total=ci.CANCEL_GPU_FRAMES, stage='sampling-idle')
        self.assertFalse(ci.gpu_work(value, ci.CANCEL_GPU_FRAMES))

    def test_drain_is_bounded_and_restores_socket_mode(self):
        transport = ScriptedTransport(); transport.pending.clear()
        host = self.host(transport)
        with patch.object(host, 'poll', return_value=True) as polled:
            with self.assertRaisesRegex(ci.GateError, 'drain'): host.drain()
        self.assertEqual(polled.call_count, 256)
        self.assertEqual(transport.gettimeout(), 0.1)


if __name__ == '__main__': unittest.main()
