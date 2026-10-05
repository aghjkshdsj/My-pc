"""Synthetic independent phone-report rejection tests, never phone evidence."""
import copy
import json
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from native_kms_fixture import fixture,mutations,without_validation
from verify_native_kms_report import audit
from bundle_native_kms import ENGINE_RUN,ENGINE_SOURCE,GUEST_RUN,GUEST_SOURCE,FILES,ENGINE_CODE
SOURCE='bff919948ae41240b4e479bf7f826675149c2b3e'
def private_fixture():
    f=fixture();f['serial']=f['serial'].replace('"schema": 1','"kernel": "6.12.111", "schema": 1',1)
    f['serial']='MPC_GPU_GUEST_RUN='+f['nonce']+'\n'+f['serial']
    trace=dict(scope='native-moltenvk-guest-command-completion',run=f['nonce'],observer_configured=True,callbacks_drained=True,
        metal_host_verified=True,adds_gpu_work=False,completed=2,observed_commit_points=2,timed_completions=2,expected_device_name='Apple A17 Pro',
        samples=[dict(token=i,device_registry_id=7,device_name='Apple A17 Pro',completion_observed=True,status=4,has_error=False,
            error_code=0,gpu_start_seconds=1.0,gpu_end_seconds=1.01) for i in [1,2]])
    trace.update({k:0 for k in ['pending','failed','overflow','unknown_callbacks','duplicate_callbacks','identity_errors','initial_errors','invalid_timing']})
    engine=dict(audit=dict(abi=2,exported_definitions_verified=True,actual_patched_sources_verified=True,physical_ios_compiled=True,
        metal_join_runtime_verified=False,phone_tested=False),base_engine=dict(files={
        'sysroot-iOS-arm64/Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu':dict(sha256=ENGINE_CODE)}))
    run=dict(scope='standard-linux-kms-native-metal-completion-join',source_commit=SOURCE,status='passed',
        standard_kms_native_completion_verified=True,hardware_virtualization=False,engine_finished=True,engine_worker_joined=True,
        engine_init_thread_rcu_unregistered=True,linux_execution=True,engine_status=0,run=f['nonce'],native=f['native'],serial_output=f['serial'],
        device=dict(device_machine='iPhone16,2',ios_version='27.0.1',os_build='24A446',metal_device='Apple A17 Pro'),
        payload=dict(files=FILES,source_commit=GUEST_SOURCE,workflow_run=GUEST_RUN),
        engine_bundle=dict(scope='bundled-ios-standard-kms-native-completion',completion_abi=2,engine_run=ENGINE_RUN,engine_source=ENGINE_SOURCE,
            guest_run=GUEST_RUN,guest_source=GUEST_SOURCE,engine_receipt=engine),guest_metal_trace=trace)
    return dict(scope='private-native-kms-device-test',build='4000028',source_commit=SOURCE,test=run)
class NativeKMSReportTests(unittest.TestCase):
    def test_independent_valid_fixture_and_callback_reordering(self):
        report=private_fixture();r=audit(report,SOURCE)
        self.assertTrue(r['eight_linux_kms_native_completion_joins_verified']);self.assertFalse(r['game_fps_verified'])
        report['test']['native']['recent_terminals'].reverse();self.assertTrue(audit(report,SOURCE)['eight_linux_kms_native_completion_joins_verified'])
    def test_actual_boundary_mutations_fail(self):
        for bad in mutations(fixture()):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                report=private_fixture();report['test']['native']=bad['native']
                serial=bad['serial'].replace('"schema": 1','"kernel": "6.12.111", "schema": 1',1)
                report['test']['serial_output']='MPC_GPU_GUEST_RUN='+bad['nonce']+'\n'+serial
                audit(report,SOURCE)
    def test_runtime_identity_retirement_observer_mutations_fail(self):
        edits=[(['source_commit'],'0'*40),(['test','device','os_build'],'wrong'),(['test','engine_worker_joined'],False),
            (['test','engine_init_thread_rcu_unregistered'],False),(['test','guest_metal_trace','pending'],1),
            (['test','guest_metal_trace','samples',0,'device_registry_id'],8),
            (['test','guest_metal_trace','samples',1,'token'],1),
            (['test','guest_metal_trace','samples',0,'gpu_end_seconds'],float('nan')),
            (['test','engine_bundle','engine_run'],1),(['test','native','completion_callbacks_in_progress'],True),
            (['test','native','actual_gpu_completed'],True)]
        for path,value in edits:
            report=private_fixture();target=report
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises(ValueError):audit(report,SOURCE)
    def test_unavailable_validation_is_separate_from_completion(self):
        report=private_fixture()
        report['test']['serial_output']=without_validation(dict(serial=report['test']['serial_output']))['serial']
        result=audit(report,SOURCE)
        self.assertTrue(result['eight_linux_kms_native_completion_joins_verified'])
        self.assertFalse(result['validation_layer_verified'])
        self.assertEqual(result['validation_status'],'unavailable')
    def test_old_failed_label_is_preserved_and_requires_explicit_audit(self):
        report=private_fixture();run=report['test']
        run['serial_output']=without_validation(dict(serial=run['serial_output']))['serial']
        run['status']='failed';run['standard_kms_native_completion_verified']=False
        run['guest_metal_trace']['metal_host_verified']=False
        with self.assertRaises(ValueError):audit(report,SOURCE)
        result=audit(report,SOURCE,observations_only=True)
        self.assertTrue(result['eight_linux_kms_native_completion_joins_verified'])
        self.assertFalse(result['reported_app_verified']);self.assertFalse(result['app_and_independent_verdict_agree'])
        self.assertEqual(result['reported_app_status'],'failed')
        run['native']['pending_readers']=1
        with self.assertRaises(ValueError):audit(report,SOURCE,observations_only=True)
if __name__=='__main__':unittest.main()
