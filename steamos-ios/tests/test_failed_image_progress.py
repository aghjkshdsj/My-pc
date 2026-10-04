"""Known failed duplicate-consumer fixtures, never phone acceptance."""
import copy
import json
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from verify_failed_image_progress import validate
from verify_guest_gpu_report import validate as validate_report
import test_failed_image_controls as control_fixtures
import test_guest_image_import as image_fixtures


def fixture():
    report=control_fixtures.fixture();report['build']='4000019';gate=report['tests']['linux_image'];nonce=gate['run']
    image_gate,_=image_fixtures.fixture();receipt=image_gate['image_import'];receipt['run']=nonce
    native=receipt['native'];native['run']=nonce;native['errors']=2;native['skipped_repeat_flushes']=0
    native['images']=[dict(native['images'][0],native_pixel_format=80,channel_order='bgra',virtio_format=2),
                      dict(native['images'][0],generation=2,native_pixel_format=80,channel_order='bgra',virtio_format=2)]
    native['events']=[]
    for generation,resource,kinds in [(1,12,(1,2,3)),(2,12,(1,2,3)),(3,13,(1,2,2,3))]:
        for kind in kinds:native['events'].append(dict(kind=kind,sequence=len(native['events'])+1,
                                                     generation=generation,resource_id=resource))
    for producer in receipt['guest_producers']:
        producer.update(run=nonce,vulkan_format=44,drm_fourcc=875713112,virtio_format=2,channel_order='bgra')
    receipt['guest_exits'][0]['run']=nonce
    receipt.update(host_memory_import_verified=False,pixels_checked=0,channel_sum=0)
    gate['image_import']=receipt
    for sample in gate['native_metal_trace']['samples']:sample['device_registry_id']=77
    gate['serial_tail']=gate['serial_tail'].split('MPC_IMAGE_CAPABILITIES ')[0]
    gate['serial_tail']+='MPC_IMAGE_CAPABILITIES '+json.dumps(dict(schema=1,run=nonce,result=0,
        tiling='drm-format-modifier',drm_modifier=0))+'\n'+image_fixtures.serial(gate)
    gate['serial_tail']+='MPC_VK_IMAGE_RENDER '+json.dumps(dict(machine='aarch64',software=False,
        width=1280,height=720,pixels_checked=1843200,shader_phases=2,mismatches=0,channel_sum=1219256320,
        validation_errors=0,metal_host_verified=False,presentation_verified=False,game_fps_verified=False))+'\n'
    return report


def check(report):
    return validate_report(report,'test-commit','4000019',{'synthetic':True},
        {'engine_text_sections':{'fixture':{'sha256':'not-a-device-result'}}},'27.0.1',image_control_only=True)


class FailedImageProgressTests(unittest.TestCase):
    def test_known_failure_records_only_one_unique_native_phase(self):
        report=fixture();result=check(report);partial=result['partial_image_progress']
        self.assertEqual(partial['partial_native_phase0_pixels_checked'],921600)
        self.assertEqual(partial['native_consumer_resources'],[12,12])
        for key in ('host_memory_import_verified','presentation_verified','gameplay_verified','steamos_verified'):
            self.assertFalse(result[key])
        with self.assertRaises(ValueError):
            validate_report(report,'test-commit','4000019',{'synthetic':True},
                {'engine_text_sections':{'fixture':{'sha256':'not-a-device-result'}}},'27.0.1',image_import=True)

    def test_phase0_pixel_alias_device_and_completion_must_match(self):
        for key,value in [('mismatches',1),('native_pixel_format',70),('phase',41),('resource_id',13),
                          ('generation',3),('native_registry_id',88),('channel_sum',0),('consumer_status',3),
                          ('consumer_error',True),('backing_bytes',1),('linear_alignment',3),('gpu_end_seconds',0)]:
            report=fixture();report['tests']['linux_image']['image_import']['native']['images'][1][key]=value
            with self.assertRaises(ValueError):check(report)

    def test_lifecycle_budget_and_failed_combined_acceptance_are_exact(self):
        for key,value in [('errors',0),('active',True),('reading',True),('skipped_repeat_flushes',1),
                          ('diagnostic_full_image_readbacks',3)]:
            report=fixture();report['tests']['linux_image']['image_import']['native'][key]=value
            with self.assertRaises(ValueError):check(report)
        report=fixture();report['tests']['linux_image']['image_import']['native']['events'][3]['resource_id']=99
        with self.assertRaises(ValueError):check(report)
        report=fixture();report['tests']['linux_image']['image_import']['pixels_checked']=1843200
        with self.assertRaises(ValueError):check(report)

    def test_guest_render_export_cleanup_and_nonce_cannot_be_inferred(self):
        for old,new in [('"mismatches": 0','"mismatches": 1'),('"run": "','"run": "stale'),
                        ('MPC_IMAGE_GUEST_EXIT=0','MPC_IMAGE_GUEST_EXIT=21'),
                        ('"images_released": true','"images_released": false')]:
            report=fixture();gate=report['tests']['linux_image'];gate['serial_tail']=gate['serial_tail'].replace(old,new)
            with self.assertRaises(ValueError):check(report)
        report=fixture();report['build']='4000020'
        with self.assertRaises(ValueError):check(report)

if __name__=='__main__':unittest.main()
