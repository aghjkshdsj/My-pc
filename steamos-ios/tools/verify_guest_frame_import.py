#!/usr/bin/env python3
"""Eight immutable guest aliases and two endpoint readbacks; not frame pacing."""
import json
import math
from verify_device_report import require


def validate(gate, serial, nonce, device_name, require_modifier=True, require_bgra=True):
    require(gate.get('frame_sequence_requested') is True, 'Image import was not requested')
    receipt = gate.get('frame_import')
    require(isinstance(receipt, dict) and receipt.get('schema') == 1 and
            receipt.get('scope') == 'physical-ios-linux-guest-eight-frame-import-gate' and receipt.get('run') == nonce,
            'Wrong image import receipt/nonce')
    require(receipt.get('host_memory_import_verified') is True, 'Image import did not pass')
    for key in ('presentation_verified', 'zero_copy_transport_verified', 'gameplay_verified'):
        require(receipt.get(key) is False, 'Unsupported image import claim: ' + key)
    native = receipt.get('native')
    require(isinstance(native, dict) and native.get('scope') == 'native-metal-linux-eight-frame-import' and
            native.get('run') == nonce, 'Wrong native import scope')
    for key in ('active', 'reading', 'presentation_verified', 'zero_copy_transport_verified'):
        require(native.get(key) is False, 'Pending or unsupported native image state: ' + key)
    require(type(native.get('errors')) is int and native['errors'] == 0 and
            native.get('diagnostic_full_image_readbacks') == 2, 'Missing/error native image consumers')
    def parsed(prefix):
        try:
            rows = [json.loads(line[len(prefix):]) for line in serial.splitlines() if line.startswith(prefix)]
        except ValueError as error:
            raise ValueError('Malformed image serial') from error
        require(all(isinstance(row, dict) for row in rows), 'Wrong image serial receipt type')
        return rows
    producers, exits, rejected = parsed('MPC_FRAME_PRODUCER '), parsed('MPC_FRAME_EXIT '), parsed('MPC_FRAME_REJECTED ')
    require(producers == receipt.get('guest_producers') and exits == receipt.get('guest_exits') and
            rejected == receipt.get('guest_rejections') and not rejected, 'Image serial/parsed receipts disagree')
    require(len(producers) == 8 and len(exits) == 1 and serial.splitlines().count('MPC_FRAME_GUEST_EXIT=0') == 1,
            'Missing/duplicate image producers or exit')
    expected_exit = {'schema': 1, 'run': nonce, 'status': 0, 'phases': 8,
                     'scanout_disabled': True, 'images_released': True, 'presentation_verified': False}
    require(all(type(exits[0].get(k)) is type(v) and exits[0][k] == v for k, v in expected_exit.items()),
            'Missing successful image cleanup')
    events = native.get('events')
    require(isinstance(events, list) and 24 <= len(events) <= 64, 'Missing/unbounded native ownership events')
    active, generation, resource, installs = False, 0, 0, []
    flushed, first_flushed = set(), {}
    for sequence, event in enumerate(events, 1):
        require(isinstance(event, dict) and type(event.get('sequence')) is int and event['sequence'] == sequence,
                'Reordered native image ownership')
        g, r, kind = event.get('generation'), event.get('resource_id'), event.get('kind')
        require(all(type(v) is int and v > 0 for v in (g, r, kind)), 'Invalid native resource identity')
        if kind == 1:
            require(not active and g > generation, 'Stale/overlapping native image installation')
            generation, resource, active = g, r, True
            installs.append((g, r))
        elif kind == 2:
            require(active and (g, r) == (generation, resource), 'Flush of a stale or disabled image')
            flushed.add((g, r))
            first_flushed.setdefault(r, (g, r))
        elif kind == 3:
            require(active and (g, r) == (generation, resource), 'Duplicate or stale image disable')
            active = False
        else:
            require(False, 'Unknown native ownership event')
    require(not active and len(installs) >= 8 and set(installs) == flushed and len(first_flushed) == 8,
            'Missing import/flush/release ordering')
    registry = native.get('registry_id')
    samples = gate.get('native_metal_trace', {}).get('samples', [])
    require(type(registry) is int and registry > 0 and samples and
            all(s.get('device_registry_id') == registry for s in samples), 'Guest producer/native consumer GPU differs')
    images = native.get('images')
    require(isinstance(images, list) and len(images) == 8, 'Missing native image pixels')
    resources = set()
    for index, (producer, image) in enumerate(zip(producers, images)):
        phase, checksum = index*17, 615690240 if index == 0 else 665579520 if index == 7 else 0
        endpoint = index in (0,7)
        require(isinstance(image, dict), 'Wrong native image receipt kind')
        fixed = {'schema': 1, 'run': nonce, 'phase': phase, 'width': 1280, 'height': 720,
                 'producer_fence_completed': True, 'external_queue_release': True}
        if require_modifier:
            fixed.update(tiling='drm-format-modifier', drm_modifier=0, memory_plane=0)
        if require_bgra:
            fixed.update(vulkan_format=44, drm_fourcc=875713112, virtio_format=2, channel_order='bgra')
        require(all(type(producer.get(k)) is type(v) and producer[k] == v for k, v in fixed.items()),
                'Missing fresh guest image/fence/ownership release')
        r, pitch, offset, size = (producer.get(k) for k in ('resource_id', 'row_pitch', 'offset', 'allocation_bytes'))
        require(all(type(v) is int for v in (r, pitch, offset, size)) and r > 0 and r not in resources and
                5120 <= pitch <= 1 << 24 and offset >= 0 and offset + pitch * 720 <= size, 'Invalid export allocation/layout')
        resources.add(r)
        require((image.get('generation'), r) == first_flushed.get(r) and image.get('resource_id') == r and
                image.get('row_pitch') == pitch and image.get('offset') == offset, 'Native image/export identity differs')
        alignment = image.get('linear_alignment')
        require(type(alignment) is int and alignment > 0 and alignment & (alignment - 1) == 0 and
                pitch % alignment == offset % alignment == 0 and type(image.get('backing_bytes')) is int and
                offset + pitch * 720 <= image['backing_bytes'], 'Wrong native alignment/backing bounds')
        expected = {'phase': phase, 'width': 1280, 'height': 720, 'native_pixel_format': 80 if require_bgra else 70,
                    'native_registry_id': registry, 'native_device': device_name, 'native_buffer_alias_verified': True,
                    'pixel_verification_performed': endpoint, 'pixels_checked': 921600 if endpoint else 0, 'mismatches': 0, 'channel_sum': checksum,
                    }
        if endpoint: expected.update(consumer_status=4, consumer_error=False)
        if require_bgra:
            expected.update(channel_order='bgra', virtio_format=2)
        require(all(type(image.get(k)) is type(v) and image[k] == v for k, v in expected.items()), 'Wrong native pixels/device/completion')
        start, end = (image.get('gpu_start_seconds'), image.get('gpu_end_seconds')) if endpoint else (0,0)
        require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (start, end)) and
                ((start == end == 0) or (start > 0 and end >= start)), 'Invalid consumer timestamps')
    require(receipt.get('pixels_checked') == 1843200 and receipt.get('channel_sum') == 1281269760,
            'Wrong combined native image pixels')
    renders = parsed('MPC_VK_FRAME_RENDER ')
    caps, drm = parsed('MPC_FRAME_CAPABILITIES '), parsed('MPC_FRAME_DRM_RESOURCE ')
    require(len(caps)==1 and caps[0].get('schema')==1 and caps[0].get('run')==nonce and caps[0].get('result')==0 and
            type(caps[0].get('external_features')) is int and caps[0]['external_features'] & 2 and
            type(caps[0].get('compatible_handles')) is int and caps[0]['compatible_handles'] & 512 and
            type(caps[0].get('max_width')) is int and caps[0]['max_width'] >= 1280 and
            type(caps[0].get('max_height')) is int and caps[0]['max_height'] >= 720, 'Missing frame export capabilities')
    require(len(drm)==8, 'Missing eight DRM resource identities')
    for row,producer in zip(drm,producers):
        require(row.get('schema')==1 and row.get('run')==nonce and type(row.get('gem_handle')) is int and row['gem_handle']>0 and
                type(row.get('resource_bytes')) is int and row['resource_bytes'] >= producer['offset']+producer['row_pitch']*720 and
                all(type(row.get(k)) is int and row[k]==producer[k] for k in ('phase','resource_id','row_pitch','offset')),
                'Guest DRM/export layout differs')
    require(len(renders) == 1 and renders[0] == receipt.get('guest_render'), 'Missing actual eight-phase guest renderer footer')
    expected = dict(machine='aarch64', software=False, width=1280, height=720, shader_phases=8,
        pixels_checked=7372800, mismatches=0, channel_sum=5157519360, validation_errors=0,
        metal_host_verified=False, presentation_verified=False, game_fps_verified=False)
    require(all(type(renders[0].get(k)) is type(v) and renders[0][k] == v for k,v in expected.items()), 'Wrong eight-phase pixels/scope')
    base = gate.get('guest_vulkan', {})
    for key in ('renderer','api_version','driver_version','vendor_id','device_id','device_type'):
        require(key in base and type(renders[0].get(key)) is type(base[key]) and renders[0][key] == base[key], 'Guest renderer changed: '+key)
    return {'scope': 'linux-native-image-import-receipt-consistency-only', 'host_memory_import_verified': True,
            'presentation_verified': False, 'gameplay_verified': False, 'zero_copy_transport_verified': False,
            'cryptographic_device_attestation': False}
