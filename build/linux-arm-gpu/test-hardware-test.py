"""Check output validation, bounded failure/cancellation and load arithmetic."""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('hardware', pathlib.Path(__file__).with_name('hardware-test.py'))
hardware = importlib.util.module_from_spec(spec); spec.loader.exec_module(hardware)
key_spec = importlib.util.spec_from_file_location('hardware_keys', pathlib.Path(__file__).with_name('hardware-keys.py'))
keys = importlib.util.module_from_spec(key_spec); key_spec.loader.exec_module(keys)


class DiagnosticValidation(unittest.TestCase):
    def test_signal_cancellation_emits_a_final_result(self):
        records = []
        previous = hardware.signal.getsignal(hardware.signal.SIGTERM)
        def emit(state):
            records.append(state)
            if state['status']=='running': hardware.signal.raise_signal(hardware.signal.SIGTERM)
        with tempfile.TemporaryDirectory() as folder:
            result = hardware.run('cpu',folder,emit)
        self.assertEqual(result['status'],'cancelled')
        self.assertEqual(records[-1]['status'],'cancelled')
        self.assertEqual(records[-1]['progress_percent'],0)
        self.assertEqual(hardware.signal.getsignal(hardware.signal.SIGTERM),previous)

    def test_stop_targets_only_the_launched_test_descendant(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = pathlib.Path(temporary)
            script = str(keys.folder/'hardware-test.py').encode()
            for pid,children,argv in [(40,'41',b'xterm\0-e\0python3\0-u\0'+script+b'\0cpu\0'),(41,'',b'python3\0-u\0'+script+b'\0cpu\0'),
                                      (99,'',b'steam\0private-account\0')]:
                entry = proc/str(pid); (entry/'task'/str(pid)).mkdir(parents=True)
                (entry/'task'/str(pid)/'children').write_text(children)
                (entry/'cmdline').write_bytes(argv)
            with patch.object(keys.os,'kill') as kill:
                self.assertTrue(keys.cancel_runner(40,proc))
                kill.assert_called_once_with(41,keys.signal.SIGTERM)
            (proc/'41'/'cmdline').write_bytes(b'python3\0unrelated-test.py\0cpu\0')
            with patch.object(keys.os,'kill') as kill:
                self.assertFalse(keys.cancel_runner(40,proc)); kill.assert_not_called()

    def test_timeout_terminates_only_the_test_group(self):
        child = Mock(pid=42,returncode=None); child.poll.return_value = None
        expired = hardware.subprocess.TimeoutExpired('test',180)
        child.communicate.side_effect = [expired,expired,(b'',b'')]
        with patch.object(hardware.subprocess,'Popen',return_value=child), \
             patch.object(hardware,'PROCESS_GROUPS',True), \
             patch.object(hardware.time,'monotonic',side_effect=[0,0,0,200,200]), \
             patch.object(hardware.signal,'SIGKILL',9,create=True), \
             patch.object(hardware.os,'killpg',create=True) as kill:
            with self.assertRaises(hardware.subprocess.TimeoutExpired):
                hardware.execute(pathlib.Path('/test'),'fex','cpu',1,{})
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(42,hardware.signal.SIGTERM),(42,9)])

    def test_blocked_snapshot_is_bounded(self):
        # A real child that never returns a procfs snapshot must not stop the
        # benchmark runner. Use the platform's actual process cleanup here.
        original = subprocess.Popen
        def blocked(*args, **kwargs):
            return original([sys.executable,'-c','import time; time.sleep(10)'],
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        updates = []
        started = time.monotonic()
        with patch.object(hardware,'SNAPSHOT_TIMEOUT',0.6), patch.object(hardware.subprocess,'Popen',side_effect=blocked):
            result = hardware.collect_snapshot(updates.append)
        self.assertEqual(result,{'status':'timeout'})
        self.assertTrue(updates)
        self.assertLess(time.monotonic()-started,3)

    def test_idle_sampler_failure_does_not_prevent_cpu_work(self):
        clock = [1.0]; records = []; calls = []
        def sleep(seconds): clock[0] += seconds
        def execute(folder,mode,kind,workers,env,iterations,tick):
            calls.append((mode,workers)); tick({'done':1,'total':3,'stage':'samples'},0.5)
            return {'mode':mode,'kind':kind,'workers':workers,'status':'passed'}
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(hardware.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(hardware.time,'sleep',side_effect=sleep), \
             patch.object(hardware,'collect_snapshot',return_value={'status':'timeout'}), \
             patch.object(hardware,'environment',return_value={}), \
             patch.object(hardware,'execute',side_effect=execute), \
             patch.object(hardware.os,'cpu_count',return_value=6):
            result = hardware.run('cpu',folder,records.append)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(calls,[('arm64',1),('arm64',6),('fex',1),('fex',6)])
        self.assertEqual(result['idle_guest']['reason'],'sampling-timeout')
        self.assertEqual([r['heartbeat_seq'] for r in records],list(range(1,len(records)+1)))
        self.assertTrue(any(r['stage']=='sampling-idle' and 0<r['progress_percent']<10 for r in records))
        self.assertEqual(records[0]['progress_percent'],0)
        self.assertEqual(records[-1]['progress_percent'],100)
        self.assertTrue(all(a['progress_percent']<=b['progress_percent'] for a,b in zip(records,records[1:])))

    def test_progress_requires_actual_matching_work_counter(self):
        row = {'kind':'gpu','arch':'x86_64','done':20,'total':60,'stage':'frames'}
        def output(): return ('MYPC_BENCH_PROGRESS '+json.dumps(row)).encode()
        self.assertEqual(hardware.work_progress(output(),'fex','gpu')['done'],20)
        self.assertIsNone(hardware.work_progress(output(),'arm64','gpu'))
        row['done'] = 61
        self.assertIsNone(hardware.work_progress(output(),'fex','gpu'))
        self.assertIsNone(hardware.work_progress(b'private account text','fex','gpu'))

    def test_private_home_keeps_original_x11_auth_location(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(hardware.os.environ,{'HOME':'/home/steam'},clear=True):
            env = hardware.environment(pathlib.Path('/test'),temporary)
        self.assertEqual(env['XAUTHORITY'],str(pathlib.Path('/home/steam')/'.Xauthority'))
        self.assertNotEqual(env['HOME'],'/home/steam')

    def test_corrupt_fex_checksum_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = pathlib.Path(temporary)
            (folder/'checksums.json').write_text(json.dumps({'1:1': hardware.checksum(1,1)}))
            record = {'kind':'cpu','arch':'x86_64','workers':1,'iterations_per_worker':1,
                      'checksum':'wrong','wall_ms':1,'process_cpu_ms':1}
            child = Mock(returncode=0)
            child.communicate.return_value = (('\n'.join(['MYPC_BENCH '+json.dumps(record)]*3)).encode(),b'')
            with patch.object(hardware.subprocess,'Popen',return_value=child):
                with self.assertRaises(AssertionError): hardware.execute(folder,'fex','cpu',1,{},1)

    def test_arm_binary_cannot_be_reported_as_fex(self):
        child = Mock(returncode=0)
        child.communicate.return_value = (b'MYPC_BENCH {"kind":"gpu","arch":"aarch64"}',b'')
        with patch.object(hardware.subprocess,'Popen',return_value=child):
            with self.assertRaises(AssertionError): hardware.execute(pathlib.Path('/test'),'fex','gpu',1,{})

    def test_failed_runtime_does_not_relay_sensitive_stderr(self):
        child = Mock(returncode=139)
        child.communicate.return_value = (b'',b'account/token/private/path\nMYPC_BENCH_FAILED stage=context\n')
        with patch.object(hardware.subprocess,'Popen',return_value=child):
            result = hardware.execute(pathlib.Path('/test'),'fex','gpu',1,{})
        self.assertEqual(result['status'],'failed'); self.assertEqual(result['stage'],'context')
        self.assertNotIn('account',json.dumps(result))

    def test_busy_and_iowait_remain_separate(self):
        before = {'online_cpus':1,'uptime_s':1,'cores':{'cpu0':[0]*8},'processes':{}}
        after = {'online_cpus':1,'uptime_s':2,'cores':{'cpu0':[30,0,20,40,10,0,0,0]},'processes':{}}
        with patch.object(hardware.os,'sysconf',return_value=100,create=True): state = hardware.pressure(before,after)
        self.assertEqual(state['per_core'][0],{'core':0,'busy_percent':50.0,'iowait_percent':10.0})


if __name__ == '__main__': unittest.main()
