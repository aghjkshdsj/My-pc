"""Production receipt controls; synthetic fixtures are never phone evidence."""
import copy,json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from verify_guest_gpu_report import validate
PATH=pathlib.Path(__file__).with_name('frame_sequence_fixture.json')
def fixture():
    data=json.loads(PATH.read_text());assert data['phone_tested'] is False
    return data['report']
def check(r):
    g=r['tests']['linux_frames']
    return validate(r,'test-commit','4000023',g['payload'],g['engine_bundle'],'27.0.1',frame_sequence=True)
class FrameSequenceTests(unittest.TestCase):
    def test_build24_requires_retired_joined_engine_worker(self):
        r=fixture();r['build']='4000024';g=r['tests']['linux_frames']
        def check24():
            return validate(r,'test-commit','4000024',g['payload'],g['engine_bundle'],'27.0.1',frame_sequence=True)
        for bad in (None,False,1):
            g['engine_worker_joined']=bad
            with self.subTest(value=bad),self.assertRaises(ValueError):check24()
        g['engine_worker_joined']=True
        self.assertTrue(check24()['eight_frame_gpu_sequence_verified'])
        self.assertFalse(check24()['presentation_verified'])
    def test_zero_display_time_allows_only_explicit_gpu_sequence(self):
        result=check(fixture());self.assertTrue(result['eight_frame_gpu_sequence_verified'])
        for key in ('presentation_verified','gameplay_verified','steamos_verified','hollow_knight_target_verified','cryptographic_device_attestation'):
            self.assertFalse(result[key])
    def test_every_distinct_guest_source_and_endpoint_control_required(self):
        for i in range(8):
            for key,bad in dict(resource_id=0,phase=41,row_pitch=1,native_pixel_format=70,native_registry_id=999,
                                backing_bytes=1,native_buffer_alias_verified=False,pixel_verification_performed=True if i not in (0,7) else False).items():
                r=fixture();r['tests']['linux_frames']['frame_import']['native']['images'][i][key]=bad
                with self.subTest(i=i,key=key),self.assertRaises(ValueError):check(r)
        for index in (0,7):
            r=fixture();r['tests']['linux_frames']['frame_import']['native']['images'][index]['channel_sum']=0
            with self.assertRaises(ValueError):check(r)
    def test_every_screen_gpu_join_and_geometry_required(self):
        for i in range(8):
            for key,bad in dict(resource_id=0,gpu_completed=False,consumer_error=True,completion_join_retired=False,
                                presentation_on_main_thread=False,presentation_application_state=1,source_registry_id=999,
                                geometry=2,gpu_end_seconds=0,viewport=[1,1,1,1],presented_seconds=float('nan')).items():
                r=fixture();r['tests']['linux_frames']['frame_screen']['native']['frames'][i][key]=bad
                with self.subTest(i=i,key=key),self.assertRaises(ValueError):check(r)
    def test_cpu_callback_and_later_query_cannot_supply_display_time(self):
        r=fixture();g=r['tests']['linux_frames']
        for f in g['frame_screen']['native']['frames']:f['presented_seconds_later_query']=f['submit_seconds']+.016
        self.assertFalse(check(r)['presentation_verified'])
        g['presentation_verified']=True;g['frame_screen']['presentation_verified']=True
        r['acceptance']['linux_guest_eight_frame_display_timing']=True
        with self.assertRaises(ValueError):check(r)
    def test_actual_positive_ordered_display_times_are_separate(self):
        r=fixture();g=r['tests']['linux_frames']
        for f in g['frame_screen']['native']['frames']:f['presented_seconds']=f['submit_seconds']+.016
        g['presentation_verified']=True;g['frame_screen']['presentation_verified']=True
        r['acceptance']['linux_guest_eight_frame_display_timing']=True
        self.assertTrue(check(r)['presentation_verified'])
        r['acceptance']['linux_guest_frame_pacing']=True
        with self.assertRaises(ValueError):check(r)
    def test_missing_guest_frames_old_images_and_mutated_renderer_rejected(self):
        for prefix in ('MPC_FRAME_PRODUCER ','MPC_FRAME_EXIT ','MPC_VK_FRAME_RENDER ','MPC_FRAME_GUEST_EXIT='):
            r=fixture();g=r['tests']['linux_frames'];g['serial_tail']='\n'.join(l for l in g['serial_tail'].splitlines() if not l.startswith(prefix))
            with self.assertRaises(ValueError):check(r)
        r=fixture();r['tests']['linux_frames']['frame_screen']['native']['frames']=r['tests']['linux_frames']['frame_screen']['native']['frames'][:2]
        with self.assertRaises(ValueError):check(r)
if __name__=='__main__':unittest.main()
