import copy,json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from moving_fixture import fixture,channel_sum,phase
from verify_guest_moving_output import validate,rows
from verify_guest_gpu_report import validate as validate_device
import test_guest_frames
def receipt(f):
    return dict(schema=1,scope='physical-ios-linux-three-buffer-moving-output',run=f['nonce'],
        buffer_reuse_verified=True,presentation_verified=True,native=f['native'],screen=f['screen'],
        guest_controls=rows(f['serial'],'MPC_MOVE_CTL '),guest_releases=rows(f['serial'],'MPC_MOVE_RELEASE_RECEIVED '),
        guest_exits=rows(f['serial'],'MPC_MOVE_EXIT '),guest_render=rows(f['serial'],'MPC_VK_MOVING_RENDER ')[0],
        production_kms_wsi_verified=False,compositor_verified=False,frame_pacing_verified=False,game_fps_verified=False,
        gameplay_verified=False,steady_state_full_image_readbacks=0,pixels_checked=1843200,
        channel_sum=channel_sum(0)+channel_sum(phase(119)),missing_or_nonmonotonic_display_timestamps=0)
class MovingRejectionTests(unittest.TestCase):
    def device_fixture(self):
        report=test_guest_frames.fixture();report['build']='4000026';report['executed_tests']=['linux_moving']
        gate=report['tests'].pop('linux_frames');report['tests']['linux_moving']=gate
        gate.update(scope='physical-ios-linux-three-buffer-moving-gate',engine_worker_joined=True,
            engine_init_thread_rcu_unregistered=True,moving_frames_requested=True,buffer_reuse_verified=True,
            host_memory_import_verified=True,presentation_verified=True,frame_sequence_requested=False)
        f=fixture();f=json.loads(json.dumps(f).replace(f['nonce'],gate['run']))
        move=receipt(f);base=gate['guest_vulkan'];text=[]
        for line in f['serial'].splitlines():
            if line.startswith('MPC_VK_DIAGNOSTIC '):continue
            if line.startswith('MPC_VK_MOVING_RENDER '):
                render=json.loads(line[len('MPC_VK_MOVING_RENDER '):])
                for key in ('renderer','api_version','driver_version','vendor_id','device_id','device_type'):render[key]=base[key]
                line='MPC_VK_MOVING_RENDER '+json.dumps(render);move['guest_render']=render
            text.append(line)
        moving_serial='\n'.join(text)+'\n'
        gate['serial_tail']=gate['serial_tail'].replace('MPC_LINUX_EXIT=0',moving_serial+'MPC_LINUX_EXIT=0')
        gate['moving_output']=move
        report['acceptance'].update(linux_guest_three_buffer_reuse=True,linux_guest_image_import=True,
            linux_guest_moving_display_timing=True)
        return report
    def check_device(self,report):
        g=report['tests']['linux_moving']
        return validate_device(report,'test-commit','4000026',g['payload'],g['engine_bundle'],'27.0.1',moving_output=True)
    def test_phone_package_binding_synthetic_only(self):
        result=self.check_device(self.device_fixture());self.assertTrue(result['moving_buffer_reuse_verified'])
        self.assertFalse(result['cryptographic_device_attestation']);self.assertFalse(result['steamos_verified'])
    def test_phone_os_package_and_worker_corruption(self):
        for field,value in [('engine_worker_joined',False),('engine_init_thread_rcu_unregistered',False),
            ('engine_finished',False),('engine_text_sections_verified',False),('engine_status',1),
            ('payload',{}),('engine_bundle',{}),('buffer_reuse_verified',False)]:
            r=self.device_fixture();g=r['tests']['linux_moving'];expected_payload=copy.deepcopy(g['payload']);expected_bundle=copy.deepcopy(g['engine_bundle']);g[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_device(r,'test-commit','4000026',expected_payload,expected_bundle,'27.0.1',moving_output=True)
        r=self.device_fixture();r['after']['ios_version']='wrong'
        with self.assertRaises(ValueError):self.check_device(r)
    def test_synthetic_schedule(self):
        f=fixture();self.assertTrue(validate(receipt(f),f['serial'],f['nonce'])['buffer_reuse_verified'])
    def test_reinstallation_refresh_does_not_create_a_new_content_draw(self):
        f=fixture(reinstall=True);r=receipt(f)
        self.assertTrue(validate(r,f['serial'],f['nonce'])['buffer_reuse_verified'])
        self.assertEqual(len(r['native']['images']),120)
        self.assertEqual(len(r['native']['refreshes']),120)
        self.assertEqual(len(r['native']['releases']),120)
    def test_refresh_corruption_cannot_hide_a_missing_consumer_or_release(self):
        f=fixture(reinstall=True);r=receipt(f)
        for key,value in [('serial',2),('generation',3),('resource_id',99),('incarnation',2),
                          ('native_reads_added',1),('releases_added',1),('lease_state',2),('event_sequence',2)]:
            bad=copy.deepcopy(r);bad['native']['refreshes'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(bad,f['serial'],f['nonce'])
        bad=copy.deepcopy(r);del bad['native']['images'][1]
        with self.assertRaises(ValueError):validate(bad,f['serial'],f['nonce'])
        bad=copy.deepcopy(r);bad['native']['offers'][1]['flush_sequence']=2
        with self.assertRaises(ValueError):validate(bad,f['serial'],f['nonce'])
    def test_damage_native_join(self):
        f=fixture();r=receipt(f)
        mutations=[('offers','serial',0),('offers','producer_fence_completed',False),('offers','external_queue_release',False),
            ('offers','generation',1),('offers','native_consumed',False),('images','phase',119),('images','native_registry_id',100),
            ('images','row_pitch',5121),('images','pixels_checked',921600),('images','resource_id',99),
            ('releases','release',1),('releases','actual_gpu_terminal_callback',False),('releases','wire_sent',False),
            ('releases','status',5),('reacquisitions','release',1),('reacquisitions','acquire_fence_completed',False)]
        for array,key,value in mutations:
            bad=copy.deepcopy(r);bad['native'][array][20][key]=value
            with self.subTest(array=array,key=key),self.assertRaises((ValueError,KeyError)):validate(bad,f['serial'],f['nonce'])
    def test_damage_draw_and_teardown(self):
        f=fixture();r=receipt(f)
        for key,value in [('gpu_completed',False),('gpu_submitted',False),('consumer_status',5),('consumer_error',True),
            ('phase',0),('generation',0),('drawable_presented',False),('drawable_registry_id',100),('gpu_end_seconds',0)]:
            bad=copy.deepcopy(r);bad['screen']['frames'][50][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(bad,f['serial'],f['nonce'])
        for key,value in [('reader_joined',False),('channel_eof',False),('ledger_drained',False),('ledger_faulted',True),('errors',1),('final_submission_fence',239)]:
            bad=copy.deepcopy(r);bad['native'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(bad,f['serial'],f['nonce'])
    def test_display_is_separate(self):
        f=fixture();r=receipt(f);r['screen']['frames'][0]['presented_seconds']=0;r['presentation_verified']=False;r['missing_or_nonmonotonic_display_timestamps']=1
        self.assertFalse(validate(r,f['serial'],f['nonce'])['presentation_verified'])
    def test_drawable_pool_reuse_does_not_reuse_content_ticket(self):
        f=fixture();r=receipt(f)
        for i,row in enumerate(r['screen']['frames']):row['drawable_id']=i%2
        self.assertTrue(validate(r,f['serial'],f['nonce'])['buffer_reuse_verified'])
    def test_stale_or_missing_guest(self):
        f=fixture();r=receipt(f)
        for text in [f['serial'].replace('MPC_MOVE_GUEST_EXIT=0','MPC_MOVE_GUEST_EXIT=99'),f['serial'].replace(f['nonce'],'f'*32),f['serial']+f['serial']]:
            with self.assertRaises(ValueError):validate(r,text,f['nonce'])
if __name__=='__main__':unittest.main()
