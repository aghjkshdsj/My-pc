#!/usr/bin/env python3
"""Independent image-receipt consistency checks; never remote attestation."""
import json
import math
from verify_device_report import require


def validate(gate, serial, nonce, device_name, require_modifier=False):
    require(gate.get('image_import_requested') is True, 'Image import was not requested')
    receipt = gate.get('image_import')
    require(isinstance(receipt, dict) and receipt.get('schema') == 1 and
            receipt.get('scope') == 'physical-ios-linux-guest-image-import-gate' and receipt.get('run') == nonce,
            'Wrong image import receipt/nonce')
    require(receipt.get('host_memory_import_verified') is True, 'Image import did not pass')
    for key in ('presentation_verified', 'zero_copy_transport_verified', 'gameplay_verified'):
        require(receipt.get(key) is False, 'Unsupported image import claim: ' + key)
    native = receipt.get('native')
    require(isinstance(native, dict) and native.get('scope') == 'native-metal-linux-linear-image-import' and
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
    producers, exits, rejected = parsed('MPC_IMAGE_PRODUCER '), parsed('MPC_IMAGE_EXIT '), parsed('MPC_IMAGE_REJECTED ')
    require(producers == receipt.get('guest_producers') and exits == receipt.get('guest_exits') and
            rejected == receipt.get('guest_rejections') and not rejected, 'Image serial/parsed receipts disagree')
    require(len(producers) == 2 and len(exits) == 1 and serial.splitlines().count('MPC_IMAGE_GUEST_EXIT=0') == 1,
            'Missing/duplicate image producers or exit')
    expected_exit = {'schema': 1, 'run': nonce, 'status': 0, 'phases': 2,
                     'scanout_disabled': True, 'images_released': True, 'presentation_verified': False}
    require(all(type(exits[0].get(k)) is type(v) and exits[0][k] == v for k, v in expected_exit.items()),
            'Missing successful image cleanup')
    events = native.get('events')
    require(isinstance(events, list) and 6 <= len(events) <= 64, 'Missing/unbounded native ownership events')
    active, generation, resource, installs = False, 0, 0, []
    flushed = set()
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
        elif kind == 3:
            require(active and (g, r) == (generation, resource), 'Duplicate or stale image disable')
            active = False
        else:
            require(False, 'Unknown native ownership event')
    require(not active and len(installs) == 2 and len(flushed) == 2 and set(installs) == flushed,
            'Missing import/flush/release ordering')
    registry = native.get('registry_id')
    samples = gate.get('native_metal_trace', {}).get('samples', [])
    require(type(registry) is int and registry > 0 and samples and
            all(s.get('device_registry_id') == registry for s in samples), 'Guest producer/native consumer GPU differs')
    images = native.get('images')
    require(isinstance(images, list) and len(images) == 2, 'Missing native image pixels')
    resources = set()
    for index, (producer, image) in enumerate(zip(producers, images)):
        phase, checksum = (0, 615690240) if index == 0 else (41, 603566080)
        require(isinstance(image, dict), 'Wrong native image receipt kind')
        fixed = {'schema': 1, 'run': nonce, 'phase': phase, 'width': 1280, 'height': 720,
                 'producer_fence_completed': True, 'external_queue_release': True}
        if require_modifier:
            fixed.update(tiling='drm-format-modifier', drm_modifier=0, memory_plane=0)
        require(all(type(producer.get(k)) is type(v) and producer[k] == v for k, v in fixed.items()),
                'Missing fresh guest image/fence/ownership release')
        r, pitch, offset, size = (producer.get(k) for k in ('resource_id', 'row_pitch', 'offset', 'allocation_bytes'))
        require(all(type(v) is int for v in (r, pitch, offset, size)) and r > 0 and r not in resources and
                5120 <= pitch <= 1 << 24 and offset >= 0 and offset + pitch * 720 <= size, 'Invalid export allocation/layout')
        resources.add(r)
        require((image.get('generation'), r) == installs[index] and image.get('resource_id') == r and
                image.get('row_pitch') == pitch and image.get('offset') == offset, 'Native image/export identity differs')
        alignment = image.get('linear_alignment')
        require(type(alignment) is int and alignment > 0 and alignment & (alignment - 1) == 0 and
                pitch % alignment == offset % alignment == 0 and type(image.get('backing_bytes')) is int and
                offset + pitch * 720 <= image['backing_bytes'], 'Wrong native alignment/backing bounds')
        expected = {'phase': phase, 'width': 1280, 'height': 720, 'native_pixel_format': 70,
                    'native_registry_id': registry, 'native_device': device_name, 'native_buffer_alias_verified': True,
                    'pixels_checked': 921600, 'mismatches': 0, 'channel_sum': checksum,
                    'consumer_status': 4, 'consumer_error': False}
        require(all(type(image.get(k)) is type(v) and image[k] == v for k, v in expected.items()), 'Wrong native pixels/device/completion')
        start, end = image.get('gpu_start_seconds'), image.get('gpu_end_seconds')
        require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (start, end)) and
                ((start == end == 0) or (start > 0 and end >= start)), 'Invalid consumer timestamps')
    require(receipt.get('pixels_checked') == 1843200 and receipt.get('channel_sum') == 1219256320,
            'Wrong combined native image pixels')
    return {'scope': 'linux-native-image-import-receipt-consistency-only', 'host_memory_import_verified': True,
            'presentation_verified': False, 'gameplay_verified': False, 'zero_copy_transport_verified': False,
            'cryptographic_device_attestation': False}
