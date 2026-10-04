"""Strict consistency checks for the known build19 duplicate-consumer failure.

Never accepts two-image import, presentation or games. No report is rewritten.
"""
import json
import math
from verify_device_report import require


def validate(gate, serial, nonce, device_name):
    receipt = gate.get('image_import', {})
    def parsed(prefix):
        rows = [json.loads(line[len(prefix):]) for line in serial.splitlines() if line.startswith(prefix)]
        require(all(isinstance(x, dict) for x in rows), 'Malformed image progress marker')
        return rows
    producers, exits, rejected = parsed('MPC_IMAGE_PRODUCER '), parsed('MPC_IMAGE_EXIT '), parsed('MPC_IMAGE_REJECTED ')
    require(len(producers) == 2 and len(exits) == 1 and not rejected and
            producers == receipt.get('guest_producers') and exits == receipt.get('guest_exits') and
            rejected == receipt.get('guest_rejections'), 'Incomplete/mixed guest image progress')
    expected_exit = dict(schema=1, run=nonce, status=0, phases=2, scanout_disabled=True,
                         images_released=True, presentation_verified=False)
    require(exits[0] == expected_exit and serial.splitlines().count('MPC_IMAGE_GUEST_EXIT=0') == 1,
            'Guest images did not exit and clean up')
    capabilities = parsed('MPC_IMAGE_CAPABILITIES ')
    require(len(capabilities) == 1 and capabilities[0].get('schema') == 1 and
            capabilities[0].get('run') == nonce and capabilities[0].get('result') == 0 and
            capabilities[0].get('tiling') == 'drm-format-modifier' and capabilities[0].get('drm_modifier') == 0,
            'Missing successful image export query')
    rendered = parsed('MPC_VK_IMAGE_RENDER ')
    draw = dict(machine='aarch64', software=False, width=1280, height=720, pixels_checked=1843200,
                shader_phases=2, mismatches=0, channel_sum=1219256320, validation_errors=0,
                metal_host_verified=False, presentation_verified=False, game_fps_verified=False)
    require(len(rendered) == 1 and all(type(rendered[0].get(k)) is type(v) and rendered[0][k] == v
                                     for k,v in draw.items()), 'Both actual guest image phases must match')
    ids=[]
    for producer, phase in zip(producers,(0,41)):
        expected=dict(schema=1,run=nonce,phase=phase,width=1280,height=720,tiling='drm-format-modifier',
            drm_modifier=0,memory_plane=0,vulkan_format=44,drm_fourcc=875713112,virtio_format=2,
            channel_order='bgra',producer_fence_completed=True,external_queue_release=True)
        require(all(type(producer.get(k)) is type(v) and producer[k] == v for k,v in expected.items()),
                'Wrong guest export format/fence/phase')
        resource,pitch,offset,size=(producer.get(k) for k in ('resource_id','row_pitch','offset','allocation_bytes'))
        require(all(type(v) is int for v in (resource,pitch,offset,size)) and resource>0 and resource not in ids and
                5120<=pitch<=1<<24 and offset>=0 and offset+pitch*720<=size, 'Wrong/distinct export resource layout')
        ids.append(resource)
    native=receipt.get('native',{})
    require(native.get('scope')=='native-metal-linux-linear-image-import' and native.get('run')==nonce and
        native.get('errors')==2 and native.get('active') is False and native.get('reading') is False and
        native.get('skipped_repeat_flushes')==0 and native.get('diagnostic_full_image_readbacks')==2 and
        native.get('presentation_verified') is False and native.get('zero_copy_transport_verified') is False,
        'Not the known bounded duplicate-consumer failure')
    expected_events=[]
    for generation,resource,kinds in [(1,ids[0],(1,2,3)),(2,ids[0],(1,2,3)),(3,ids[1],(1,2,2,3))]:
        for kind in kinds:
            expected_events.append(dict(generation=generation,resource_id=resource,kind=kind,sequence=len(expected_events)+1))
    require(native.get('events')==expected_events,'Wrong reinstallation/ownership sequence')
    images=native.get('images',[]);registry=native.get('registry_id')
    samples=gate.get('native_metal_trace',{}).get('samples',[])
    require(type(registry) is int and registry>0 and samples and
            all(s.get('device_registry_id')==registry for s in samples) and len(images)==2,
            'Wrong/missing native device or consumers')
    producer=producers[0]
    for generation,image in enumerate(images,1):
        expected=dict(resource_id=ids[0],generation=generation,phase=0,width=1280,height=720,
            row_pitch=producer['row_pitch'],offset=producer['offset'],native_pixel_format=80,
            native_registry_id=registry,native_device=device_name,channel_order='bgra',virtio_format=2,
            native_buffer_alias_verified=True,pixels_checked=921600,mismatches=0,channel_sum=615690240,
            consumer_status=4,consumer_error=False)
        require(all(type(image.get(k)) is type(v) and image[k]==v for k,v in expected.items()),
                'Wrong phase0 alias/pixels/device/completion')
        alignment=image.get('linear_alignment');backing=image.get('backing_bytes')
        require(type(alignment) is int and alignment>0 and alignment & (alignment-1)==0 and
            producer['offset']%alignment==producer['row_pitch']%alignment==0 and type(backing) is int and
            backing>=producer['offset']+producer['row_pitch']*720,'Wrong native alias layout/bounds')
        start,end=image.get('gpu_start_seconds'),image.get('gpu_end_seconds')
        require(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (start,end)) and end>=start,
                'Missing real completed consumer timing')
    require(receipt.get('pixels_checked')==0 and receipt.get('channel_sum')==0,
            'Failed combined acceptance was inflated')
    return dict(scope='failed-two-image-gate-duplicate-consumer-consistency-only',
        failure='first-immutable-resource-consumed-twice-before-second-resource',
        partial_native_phase0_pixels_checked=921600,partial_native_phase0_resource=ids[0],
        guest_export_resources=ids,native_consumer_resources=[ids[0],ids[0]],
        host_memory_import_verified=False,presentation_verified=False,gameplay_verified=False,
        zero_copy_transport_verified=False,cryptographic_device_attestation=False)
