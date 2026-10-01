#!/usr/bin/env python3
"""Exercise the guest command channel without Steam, a shell or a real UART."""
import importlib.util
import json
import pathlib
import tempfile
import threading
import types
import unittest
from unittest.mock import mock_open, patch

spec = importlib.util.spec_from_file_location('control', pathlib.Path(__file__).with_name('hardware-control.py'))
control = importlib.util.module_from_spec(spec); spec.loader.exec_module(control)
runner_spec = importlib.util.spec_from_file_location('hardware', pathlib.Path(__file__).with_name('hardware-test.py'))
hardware = importlib.util.module_from_spec(runner_spec); runner_spec.loader.exec_module(hardware)


def command(number, kind='cpu', target=None):
    value = {'schema':1, 'id':f'{number:032x}', 'command':kind}
    if target is not None: value['target'] = target
    return value


def report(status='running', kind='cpu', sequence=1):
    return {'schema':1, 'run':'12345678-1234-5678-9abc-123456789abc', 'kind':kind,
            'status':status, 'stage':'sampling-idle', 'progress_percent':0,
            'heartbeat_seq':sequence, 'elapsed_s':0, 'stage_elapsed_s':0, 'results':[]}


class Child:
    def __init__(self): self.returncode, self.terminations = None, 0
    def poll(self): return self.returncode
    def terminate(self): self.terminations += 1


class GuestControl(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.events, self.children, self.launches = [], [], []
        self.now = 0
        def spawn(argv, **options):
            self.launches.append((argv, options))
            child = Child(); self.children.append(child); return child
        self.service = control.Controller(self.temporary.name, self.events.append, spawn, lambda:self.now)

    def start(self, number=1, kind='cpu'):
        self.service.handle(command(number, kind))
        self.assertTrue(self.service.job['launch'].finished.wait(1))
        return self.children[-1]

    def write(self, value):
        # The real runner atomically replaces exactly this private path.
        temporary = self.service.report.with_suffix('.new')
        temporary.write_text(json.dumps(value))
        temporary.replace(self.service.report)

    def ack(self):
        return [event for event in self.events if event['type']=='ack'][-1]

    def test_fragmented_requests_and_fixed_command_schema(self):
        parser = control.Parser(); encoded = control.frame(command(1))
        self.assertEqual(parser.feed(encoded[:10]), [])
        self.assertEqual(parser.feed(encoded[10:]), [command(1)])
        invalid = [command(2,'shell'), dict(command(2), path='/home/steam'),
                   dict(command(2), id='A'*32), dict(command(2), schema=True),
                   command(2,'cancel'), command(2,'cancel', target='not-a-run'),
                   dict(command(2), command=['cpu']), []]
        for value in invalid:
            self.assertEqual(parser.feed(control.frame(value)), [])
        self.assertEqual(parser.feed(b'\xff\n{bad}\n'+encoded), [command(1)])

    def test_oversize_unterminated_input_keeps_bounded_memory_and_recovers(self):
        parser = control.Parser()
        for _ in range(100): self.assertEqual(parser.feed(b'x'*4096), [])
        self.assertLess(len(parser.pending), control.MAX_REQUEST)
        self.assertTrue(parser.discarding)
        self.assertEqual(parser.feed(b'\n'+control.frame(command(1))), [command(1)])

    def test_newline_is_included_in_request_limit(self):
        parser = control.Parser(); encoded = control.frame(command(1))
        largest = encoded[:-1]+b' '*(control.MAX_REQUEST-len(encoded))+b'\n'
        self.assertEqual(len(largest), control.MAX_REQUEST)
        self.assertEqual(parser.feed(largest), [command(1)])
        self.assertEqual(parser.feed(largest[:-1]+b' \n'), [])

    def test_only_fixed_runner_arguments_are_spawned_without_a_shell(self):
        self.start()
        argv, options = self.launches[0]
        self.assertEqual(argv, [control.sys.executable,'-u',str(self.service.runner),'cpu',
                                '--no-serial','--result-file',str(self.service.report)])
        self.assertEqual(options, {'stdin':control.subprocess.DEVNULL,'stdout':control.subprocess.DEVNULL,
                                   'stderr':control.subprocess.DEVNULL,'start_new_session':True})
        self.service.handle(dict(command(2), arguments=['steam']))
        self.assertEqual(len(self.launches),1)

    def test_duplicate_and_busy_starts_never_spawn_another_runner(self):
        self.start()
        self.service.handle(command(1)); self.assertEqual(self.ack()['status'],'duplicate')
        self.service.handle(command(2,'gpu')); self.assertEqual(self.ack()['status'],'busy')
        self.assertEqual(len(self.children),1)

    def test_cancel_targets_only_current_direct_child_and_stale_cancel_is_rejected(self):
        child = self.start()
        self.service.handle(command(2,'cancel',command(99)['id']))
        self.assertEqual(self.ack()['status'],'stale'); self.assertEqual(child.terminations,0)
        self.service.handle(command(3,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'accepted'); self.assertEqual(child.terminations,1)
        self.service.handle(command(3,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'duplicate'); self.assertEqual(child.terminations,1)
        self.service.handle(command(4,'cancel',command(1)['id']))
        self.assertEqual(child.terminations,1)

    def test_cancel_reads_completed_report_before_accepting_or_signalling(self):
        child = self.start(); self.write(report('complete'))
        self.service.handle(command(2,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'idle')
        self.assertEqual(child.terminations,0)
        self.assertIsNone(self.service.job['cancelled'])
        self.assertEqual(self.service.latest['state']['status'],'complete')
        self.assertEqual(self.events[-2],{'schema':1,'type':'ready','ready':True,'busy':True})
        self.assertEqual(self.events[-1],self.service.latest)

    def test_cancel_reaps_already_exited_child_and_replays_truthful_completion(self):
        child = self.start(); self.write(report('complete')); child.returncode=0
        self.service.handle(command(2,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'idle')
        self.assertEqual(child.terminations,0); self.assertFalse(self.service.busy)
        self.assertEqual(self.service.latest['state']['status'],'complete')
        self.assertEqual(self.events[-2],{'schema':1,'type':'ready','ready':True,'busy':False})
        self.assertEqual(self.events[-1],self.service.latest)

    def test_exit_racing_with_terminate_is_not_acknowledged_as_delivered_stop(self):
        child = self.start(); self.write(report())
        launch = self.service.job['launch']
        def exited_before_signal():
            # Match Popen.send_signal's early return after its internal poll
            # notices normal exit; no process actually receives SIGTERM.
            self.write(report('complete',sequence=2)); child.returncode=0
        child.terminate = exited_before_signal
        self.service.handle(command(2,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'idle'); self.assertFalse(launch.signalled)
        self.assertFalse(self.service.busy)
        self.assertEqual(self.service.latest['state']['status'],'complete')

    def test_accepted_cancel_is_emitted_only_after_direct_child_is_signalled(self):
        child = self.start()
        def terminate():
            self.assertFalse(any(value['type']=='ack' and value['id']==command(2)['id'] for value in self.events))
            child.terminations += 1
        child.terminate = terminate
        self.service.handle(command(2,'cancel',command(1)['id']))
        self.assertEqual(child.terminations,1); self.assertEqual(self.ack()['status'],'accepted')
        self.assertTrue(self.service.job['launch'].signalled)

    def test_only_fixed_ci_cancel_run_gets_a_long_real_gpu_workload(self):
        cancel_start = {'schema':1,'id':'2'*32,'command':'gpu'}
        with patch.dict(control.os.environ,{'MYPC_HARDWARE_CI':'1'}):
            self.service.handle(cancel_start)
            self.assertTrue(self.service.job['launch'].finished.wait(1))
        self.assertEqual(self.launches[-1][0][-2:],['--gpu-frames','6000'])
        child = self.children[-1]; self.write(report('complete',kind='gpu'))
        child.returncode=0; self.service.poll()
        with patch.dict(control.os.environ,{'MYPC_HARDWARE_CI':'1'}): self.start(3,'gpu')
        self.assertNotIn('--gpu-frames',self.launches[-1][0])

    def test_phone_request_cannot_enable_ci_gpu_frames_or_supply_arguments(self):
        cancel_start = {'schema':1,'id':'2'*32,'command':'gpu'}
        with patch.dict(control.os.environ,{'MYPC_HARDWARE_CI':'0'}):
            self.service.handle(cancel_start)
            self.assertTrue(self.service.job['launch'].finished.wait(1))
        self.assertNotIn('--gpu-frames',self.launches[-1][0])
        self.service.handle(dict(command(2,'gpu'),gpu_frames=6000))
        self.assertEqual(len(self.launches),1)

    def test_terminal_state_is_correlated_atomic_and_replayed_without_spawning(self):
        child = self.start(); state = report('complete'); self.write(state)
        child.returncode = 0; self.service.poll()
        self.assertFalse(self.service.busy)
        expected = {'schema':1,'type':'state','id':command(1)['id'],'state':state}
        self.assertEqual(self.service.latest, expected)
        self.assertEqual(json.loads(self.service.evidence.read_bytes()),expected)
        self.assertFalse(self.service.evidence.with_suffix('.new').exists())
        self.service.handle(command(2,'status'))
        self.assertEqual(self.events[-1],expected)
        self.assertEqual(len(self.launches),1)
        self.service.handle(command(2,'status'))
        self.assertEqual(self.ack()['status'],'duplicate'); self.assertEqual(self.events[-1],expected)

    def test_old_start_and_old_cancel_cannot_relaunch_or_cancel_a_new_run(self):
        first = self.start(); self.write(report('complete')); first.returncode=0; self.service.poll()
        second = self.start(2,'gpu')
        self.service.handle(command(1)); self.assertEqual(self.ack()['status'],'duplicate')
        self.service.handle(command(3,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'stale'); self.assertEqual(second.terminations,0)
        self.assertEqual(len(self.launches),2)

    def test_status_and_cancel_remain_available_when_request_history_is_full(self):
        child = self.start()
        self.service.seen.update(f'{number:032x}' for number in range(1024))
        self.service.handle(command(2000,'status'))
        self.assertEqual(self.ack()['status'],'accepted')
        self.service.handle(command(2001,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'accepted'); self.assertEqual(child.terminations,1)
        self.service.handle(command(2002))
        self.assertEqual(self.ack()['status'],'busy'); self.assertEqual(len(self.service.seen),1024)

    def test_launch_failure_has_fixed_account_free_error_and_allows_retry(self):
        def broken(*_, **__): raise OSError('/home/private-account/executable')
        self.service.spawn = broken; self.service.handle(command(1))
        self.assertTrue(self.service.job['launch'].finished.wait(1)); self.service.poll()
        self.assertEqual(self.events[-1],{'schema':1,'type':'failure','id':command(1)['id'],
                                         'code':'launch-failed','busy':False})
        self.assertFalse(self.service.busy)
        self.assertNotIn('private-account',json.dumps(self.events))

    def test_blocked_launch_does_not_block_stop_health_or_spawn_a_second_child(self):
        gate, launched = threading.Event(), threading.Event(); child = Child()
        self.addCleanup(gate.set)
        def delayed(*_, **__):
            gate.wait(2); launched.set(); return child
        self.service.spawn = delayed
        self.service.handle(command(1)); self.assertEqual(self.ack()['status'],'accepted')
        self.now = control.LAUNCH_TIMEOUT; self.service.poll()
        self.assertEqual(self.events[-1]['code'],'launch-timeout')
        self.assertTrue(self.events[-1]['busy'])
        self.service.handle(command(2,'status')); self.assertEqual(self.ack()['status'],'accepted')
        self.service.handle(command(3,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'accepted')
        self.service.handle(command(4,'gpu')); self.assertEqual(self.ack()['status'],'busy')
        gate.set(); self.assertTrue(launched.wait(1))
        self.assertTrue(self.service.job['launch'].finished.wait(1))
        self.assertEqual(child.terminations,1)
        child.returncode = -15; self.service.poll()
        self.assertFalse(self.service.busy); self.assertFalse(self.events[-1]['busy'])

    def test_cancel_timeout_stays_busy_until_direct_child_exits(self):
        child = self.start(); self.service.handle(command(2,'cancel',command(1)['id']))
        self.now = control.CANCEL_TIMEOUT; self.service.poll()
        self.assertEqual(self.events[-1]['code'],'cancellation-timeout')
        self.assertTrue(self.events[-1]['busy']); self.assertTrue(self.service.busy)
        child.returncode = -15; self.service.poll()
        self.assertFalse(self.events[-1]['busy']); self.assertFalse(self.service.busy)

    def test_cancelled_terminal_result_does_not_become_a_failure(self):
        child = self.start(); self.service.handle(command(2,'cancel',command(1)['id']))
        self.write(report('cancelled')); child.returncode=0; self.service.poll()
        self.assertEqual(self.events[-1]['type'],'state')
        self.assertEqual(self.events[-1]['state']['status'],'cancelled')
        self.assertIsNone(self.service.last_failure)
        self.service.handle(command(3,'cancel',command(1)['id']))
        self.assertEqual(self.ack()['status'],'idle')

    def test_exited_runner_cannot_leave_ui_waiting_forever(self):
        child = self.start(); child.returncode=1; self.service.poll()
        self.assertEqual(self.events[-1]['code'],'runner-exited'); self.assertFalse(self.service.busy)

    def test_malformed_report_cancels_our_child_and_emits_only_fixed_failure(self):
        child = self.start(); self.service.report.write_text('/home/private-account')
        self.service.poll()
        self.assertEqual(child.terminations,1)
        self.assertEqual(self.events[-1]['code'],'report-invalid')
        self.assertNotIn('private-account',json.dumps(self.events))
        self.assertFalse(self.service.evidence.exists())
        self.service.handle(command(2,'cancel',command(1)['id']))
        self.assertEqual(child.terminations,1)

    def test_oversize_wrong_kind_or_regressed_report_cannot_replace_evidence(self):
        for bad in (report(kind='gpu'), 'x'*(control.MAX_FRAME+1)):
            child = self.start(1 if not self.launches else 2)
            if isinstance(bad,dict): self.write(bad)
            else: self.service.report.write_text(bad)
            self.service.poll(); self.assertEqual(self.events[-1]['code'],'report-invalid')
            self.assertEqual(child.terminations,1); child.returncode=1; self.service.poll()
        child = self.start(3); self.write(report(sequence=2)); self.service.poll()
        original = self.service.evidence.read_bytes()
        self.write(report(sequence=1)); self.service.poll()
        self.assertEqual(self.events[-1]['code'],'report-invalid')
        self.assertEqual(self.service.evidence.read_bytes(),original)
        self.assertEqual(child.terminations,1)

    def test_changed_runner_identity_cannot_be_replayed_as_the_active_request(self):
        child = self.start(); self.write(report()); self.service.poll()
        original = self.service.evidence.read_bytes()
        changed = dict(report(sequence=2),run='87654321-4321-8765-9abc-123456789abc')
        self.write(changed); self.service.poll()
        self.assertEqual(self.events[-1]['code'],'report-invalid')
        self.assertEqual(self.service.evidence.read_bytes(),original)
        self.assertEqual(child.terminations,1)

    def test_ready_reports_actual_busy_state(self):
        self.service.ready(); self.assertFalse(self.events[-1]['busy'])
        child = self.start(); self.service.ready(); self.assertTrue(self.events[-1]['busy'])
        child.returncode=1; self.service.poll(); self.service.ready()
        self.assertFalse(self.events[-1]['busy'])

    def test_bounded_writer_preserves_partial_records_during_backpressure(self):
        writer = control.Writer(); sink = bytearray()
        first = {'schema':1,'type':'ready','ready':True,'busy':False}
        writer.offer(first)
        def partial(_fd, data):
            count = min(7,len(data)); sink.extend(data[:count]); return count
        with patch.object(control.os,'write',side_effect=partial): writer.flush(1)
        pending = writer.pending
        with patch.object(control.os,'write',side_effect=BlockingIOError): writer.flush(1)
        self.assertEqual(writer.pending,pending)
        for index in range(200):
            writer.offer({'schema':1,'type':'state','id':f'{index:032x}','state':report(sequence=index+1)})
            writer.offer({'schema':1,'type':'ack','id':f'{index:032x}','command':'status','status':'accepted'})
        self.assertLessEqual(len(writer.queue),32)
        self.assertLessEqual(sum(len(data) for _,data in writer.queue)+len(writer.pending),33*control.MAX_FRAME)
        with patch.object(control.os,'write',side_effect=partial):
            while writer.pending or writer.queue: writer.flush(1)
        frames = [json.loads(line) for line in sink.splitlines()]
        self.assertEqual(frames[0],first)
        self.assertEqual(len([value for value in frames if value['type']=='state']),1)

    def test_fixed_frame_limit_rejects_oversize_and_nonfinite_data(self):
        for value in ({'data':'x'*control.MAX_FRAME},{'data':float('nan')}):
            with self.assertRaises(ValueError): control.frame(value)

    def test_corrupt_report_types_are_rejected_without_crashing_the_controller(self):
        for change in ({'schema':True},{'run':123},{'run':{}},{'heartbeat_seq':True},{'results':{}},
                       {'stage':[]},{'elapsed_s':float('nan')}):
            with self.assertRaises(ValueError): control.state_record(dict(report(),**change),'cpu')

    def test_ci_directory_is_private_and_clears_only_fixed_reports(self):
        folder = pathlib.Path(self.temporary.name)/'ci'
        folder.mkdir(); (folder/'runner.json').write_text('stale'); (folder/'unrelated').write_text('keep')
        with patch.object(control,'CI_DIRECTORY',folder), patch.dict(control.os.environ,{'MYPC_HARDWARE_CI':'1'}), \
             patch.object(control.os,'getuid',return_value=folder.stat().st_uid,create=True):
            with control.control_directory() as directory:
                self.assertEqual(directory,folder); self.assertFalse((folder/'runner.json').exists())
                self.assertEqual((folder/'unrelated').read_text(),'keep')

    def test_ci_directory_refuses_another_users_directory(self):
        folder = pathlib.Path(self.temporary.name)/'ci'; folder.mkdir()
        with patch.object(control,'CI_DIRECTORY',folder), patch.dict(control.os.environ,{'MYPC_HARDWARE_CI':'1'}), \
             patch.object(control.os,'getuid',return_value=folder.stat().st_uid+1,create=True):
            with self.assertRaises(ValueError), control.control_directory(): pass

    def test_no_serial_cli_writes_atomic_result_without_opening_the_uart(self):
        destination = pathlib.Path(self.temporary.name)/'result.json'
        fcntl = types.SimpleNamespace(flock=lambda *_:None,LOCK_EX=1,LOCK_NB=2)
        states = [report(),report('cancelled',sequence=2)]
        def run(kind, emit):
            self.assertEqual(kind,'cpu')
            for state in states: emit(state)
            return states[-1]
        with patch.dict(control.sys.modules,{'fcntl':fcntl}), \
             patch.object(control.sys,'argv',['hardware-test.py','cpu','--no-serial','--result-file',str(destination)]), \
             patch('builtins.open',mock_open()), patch.object(hardware,'run',side_effect=run), \
             patch.object(hardware.os,'open') as open_uart:
            hardware.main(); open_uart.assert_not_called()
        self.assertEqual(json.loads(destination.read_text()),states[-1])
        self.assertFalse(destination.with_suffix('.new').exists())

    def test_fast_first_real_gpu_work_is_reported_inside_heartbeat_interval(self):
        now, states = [1.0], []
        def execute(_folder,mode,kind,_workers,_env,_iterations,tick):
            tick({'done':1,'total':60,'stage':'frames'},0.01)
            return {'mode':mode,'kind':kind,'status':'passed'}
        with patch.object(hardware.time,'monotonic',side_effect=lambda:now[0]), \
             patch.object(hardware.time,'sleep',side_effect=lambda seconds:now.__setitem__(0,now[0]+seconds)), \
             patch.object(hardware,'collect_snapshot',return_value={'status':'timeout'}), \
             patch.object(hardware,'environment',return_value={}), patch.object(hardware,'execute',side_effect=execute):
            state = hardware.run('gpu',self.temporary.name,states.append)
        self.assertEqual(state['status'],'complete')
        observed = [row for row in states if row.get('work_stage')=='frames' and row.get('work_done')==1]
        self.assertTrue(observed)
        self.assertTrue(any(row['status']=='running' and row['stage']=='arm64-gpu-1' for row in observed))
        self.assertTrue(any(row['status']=='running' and row['stage']=='fex-gpu-1' for row in observed))


if __name__ == '__main__': unittest.main()
