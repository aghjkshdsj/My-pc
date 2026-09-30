"""Check output validation, bounded failure/cancellation and load arithmetic."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('hardware', pathlib.Path(__file__).with_name('hardware-test.py'))
hardware = importlib.util.module_from_spec(spec); spec.loader.exec_module(hardware)


class DiagnosticValidation(unittest.TestCase):
    def test_timeout_terminates_only_the_test_group(self):
        child = Mock(pid=42,returncode=None); child.poll.return_value = None
        expired = hardware.subprocess.TimeoutExpired('test',180)
        child.communicate.side_effect = [expired,expired,(b'',b'')]
        with patch.object(hardware.subprocess,'Popen',return_value=child), \
             patch.object(hardware.signal,'SIGKILL',9,create=True), \
             patch.object(hardware.os,'killpg',create=True) as kill:
            with self.assertRaises(hardware.subprocess.TimeoutExpired):
                hardware.execute(pathlib.Path('/test'),'fex','cpu',1,{})
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(42,hardware.signal.SIGTERM),(42,9)])

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
