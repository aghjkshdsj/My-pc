import copy,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from moving_fixture import fixture,channel_sum,phase
from verify_guest_moving_output import validate,rows
def receipt(f):
    return dict(schema=1,scope='physical-ios-linux-three-buffer-moving-output',run=f['nonce'],
        buffer_reuse_verified=True,presentation_verified=True,native=f['native'],screen=f['screen'],
        guest_controls=rows(f['serial'],'MPC_MOVE_CTL '),guest_releases=rows(f['serial'],'MPC_MOVE_RELEASE_RECEIVED '),
        guest_exits=rows(f['serial'],'MPC_MOVE_EXIT '),guest_render=rows(f['serial'],'MPC_VK_MOVING_RENDER ')[0],
        production_kms_wsi_verified=False,compositor_verified=False,frame_pacing_verified=False,game_fps_verified=False,
        gameplay_verified=False,steady_state_full_image_readbacks=0,pixels_checked=1843200,
        channel_sum=channel_sum(0)+channel_sum(phase(119)),missing_or_nonmonotonic_display_timestamps=0)
class MovingRejectionTests(unittest.TestCase):
    def test_synthetic_schedule(self):
        f=fixture();self.assertTrue(validate(receipt(f),f['serial'],f['nonce'])['buffer_reuse_verified'])
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
        for i,row in enumerate(r['screen']['frames']):row['drawable_id']=1+i%2
        self.assertTrue(validate(r,f['serial'],f['nonce'])['buffer_reuse_verified'])
    def test_stale_or_missing_guest(self):
        f=fixture();r=receipt(f)
        for text in [f['serial'].replace('MPC_MOVE_GUEST_EXIT=0','MPC_MOVE_GUEST_EXIT=99'),f['serial'].replace(f['nonce'],'f'*32),f['serial']+f['serial']]:
            with self.assertRaises(ValueError):validate(r,text,f['nonce'])
if __name__=='__main__':unittest.main()
