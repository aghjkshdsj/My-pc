#!/usr/bin/env python3
"""Check two actual drawable receipts; no animation, FPS or remote attestation."""
import math
from verify_device_report import require


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate(gate, nonce):
    receipt = gate.get('screen_presentation', {})
    require(gate.get('screen_presentation_requested') is True and gate.get('presentation_verified') is True,
            'Screen presentation was not requested/passed')
    require(receipt.get('schema') == 1 and receipt.get('scope') == 'physical-ios-linux-two-image-screen-gate'
            and receipt.get('run') == nonce and receipt.get('presentation_verified') is True,
            'Wrong screen receipt/nonce')
    native = receipt.get('native', {})
    imported = gate.get('image_import', {})
    require(imported.get('host_memory_import_verified') is True and imported.get('run') == nonce,
            'No matched Linux import before screen presentation')
    registry = imported.get('native', {}).get('registry_id')
    fixed = dict(schema=1, scope='native-metal-two-linux-image-screen', run=nonce, registry_id=registry,
                 errors=0, pending=0, interrupted=False, surface_visible=True, maximum_inflight=1,
                 drawable_limit=2, diagnostic_source_readbacks=2, drawable_cpu_readbacks=0)
    require(type(registry) is int and registry > 0 and
            all(type(native.get(k)) is type(v) and native[k] == v for k, v in fixed.items()),
            'Wrong screen state/device/budget')
    for row in (receipt, native):
        for key in ('continuous_animation_verified', 'frame_pacing_verified', 'zero_copy_transport_verified', 'gameplay_verified'):
            require(row.get(key) is False, 'Unsupported screen claim: ' + key)
    geometry = native.get('surface_geometry')
    require(type(geometry) is int and geometry > 0, 'No actual surface geometry')
    frames, images = native.get('frames'), imported.get('native', {}).get('images')
    require(isinstance(frames, list) and isinstance(images, list) and len(frames) == len(images) == 2,
            'Need both distinct imported images on the screen')
    previous_presented = 0
    resources = set()
    for i, (frame, image) in enumerate(zip(frames, images)):
        require(isinstance(frame, dict) and isinstance(image, dict), 'Wrong screen frame type')
        for key in ('resource_id', 'generation', 'phase'):
            require(type(frame.get(key)) is int and frame[key] == image.get(key), 'Screen/import identity differs')
        resource = frame['resource_id']
        require(resource > 0 and resource not in resources and frame['generation'] > 0, 'Repeated/stale guest image')
        resources.add(resource)
        expected = dict(frame_index=i+1, phase=41 if i else 0, source_registry_id=registry,
                        drawable_registry_id=registry, source_is_imported_guest_texture=True,
                        source_width=1280, source_height=720, source_pixel_format=80, drawable_pixel_format=80,
                        geometry=geometry, gpu_completed=True, drawable_presented=True,
                        consumer_status=4, consumer_error=False)
        require(all(type(frame.get(k)) is type(v) and frame[k] == v for k, v in expected.items()) and
                'error' not in frame, 'Wrong screen source/device/completion')
        require(type(frame.get('drawable_id')) is int and frame['drawable_id'] >= 0,
                'Missing actual drawable identity')
        w, h = frame.get('drawable_width'), frame.get('drawable_height')
        require(type(w) is int and type(h) is int and 0 < w <= 16384 and 0 < h <= 16384,
                'Invalid drawable dimensions')
        times = [frame.get(k) for k in ('submit_seconds', 'gpu_start_seconds', 'gpu_end_seconds', 'presented_seconds')]
        require(all(positive(t) for t in times) and times == sorted(times) and times[-1] > previous_presented,
                'Missing/nonfinite/out-of-order actual GPU/display timestamps')
        previous_presented = times[-1]
        scale = min(w/1280, h/720)
        expected_viewport = [(w-1280*scale)/2, (h-720*scale)/2, 1280*scale, 720*scale]
        viewport = frame.get('viewport')
        require(isinstance(viewport, list) and len(viewport) == 4 and
                all(type(v) in (int, float) and math.isfinite(v) and abs(v-e) < 0.01
                    for v, e in zip(viewport, expected_viewport)), 'Wrong aspect-preserving viewport')
    return dict(scope='two-linux-image-screen-receipt-consistency-only', presentation_verified=True,
                continuous_animation_verified=False, frame_pacing_verified=False,
                gameplay_verified=False, zero_copy_transport_verified=False,
                cryptographic_device_attestation=False)
