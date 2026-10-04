#!/usr/bin/env python3
"""Check eight GPU draws separately from actual display timing; never game FPS."""
import math
from verify_device_report import require


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate(gate, nonce):
    receipt = gate.get('frame_screen', {})
    require(gate.get('frame_sequence_requested') is True and gate.get('gpu_sequence_verified') is True,
            'Screen presentation was not requested/passed')
    require(receipt.get('schema') == 1 and receipt.get('scope') == 'physical-ios-linux-eight-frame-screen-gate'
            and receipt.get('run') == nonce and receipt.get('gpu_sequence_verified') is True,
            'Wrong screen receipt/nonce')
    native = receipt.get('native', {})
    imported = gate.get('frame_import', {})
    require(imported.get('host_memory_import_verified') is True and imported.get('run') == nonce,
            'No matched Linux import before screen presentation')
    registry = imported.get('native', {}).get('registry_id')
    schema = native.get('schema')
    require(type(schema) is int and schema == 2, 'Wrong screen schema')
    fixed = dict(schema=schema, scope='native-metal-eight-linux-frame-screen', run=nonce, registry_id=registry,
                 errors=0, pending=0, interrupted=False, surface_visible=True, maximum_inflight=1,
                 drawable_limit=2, diagnostic_source_readbacks=2, drawable_cpu_readbacks=0)
    require(type(registry) is int and registry > 0 and
            all(type(native.get(k)) is type(v) and native[k] == v for k, v in fixed.items()),
            'Wrong screen state/device/budget')
    for row in (receipt, native):
        for key in ('continuous_animation_verified', 'frame_pacing_verified', 'zero_copy_transport_verified', 'gameplay_verified'):
            require(row.get(key) is False, 'Unsupported screen claim: ' + key)
    if schema == 2:
        events = native.get('lifecycle_events')
        require(native.get('presentation_route') == 'scheduled-main-thread-core-animation-transaction' and
                isinstance(events, list) and len(events) <= 32, 'Wrong transaction route/lifecycle capture')
        previous = 0
        for event in events:
            require(isinstance(event, dict) and isinstance(event.get('reason'), str) and event['reason'] and
                    event.get('interrupts_acceptance') is False and positive(event.get('host_seconds')) and
                    event['host_seconds'] >= previous, 'Interrupted or malformed lifecycle observation')
            previous = event['host_seconds']
    geometry = native.get('surface_geometry')
    require(type(geometry) is int and geometry > 0, 'No actual surface geometry')
    frames, images = native.get('frames'), imported.get('native', {}).get('images')
    require(isinstance(frames, list) and isinstance(images, list) and len(frames) == len(images) == 8,
            'Need both distinct imported images on the screen')
    previous_presented = 0
    timing = True
    resources = set()
    for i, (frame, image) in enumerate(zip(frames, images)):
        require(isinstance(frame, dict) and isinstance(image, dict), 'Wrong screen frame type')
        for key in ('resource_id', 'generation', 'phase'):
            require(type(frame.get(key)) is int and frame[key] == image.get(key), 'Screen/import identity differs')
        resource = frame['resource_id']
        require(resource > 0 and resource not in resources and frame['generation'] > 0, 'Repeated/stale guest image')
        resources.add(resource)
        expected = dict(frame_index=i+1, phase=i*17, source_registry_id=registry,
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
        require(all(positive(t) for t in times[:3]) and times[:3] == sorted(times[:3]) and
                type(times[-1]) in (int,float) and math.isfinite(times[-1]) and times[-1] >= 0,
                'Missing/nonfinite/out-of-order actual GPU/display timestamps')
        timing = timing and positive(times[-1]) and times[-1] >= times[2] and times[-1] > previous_presented
        previous_presented = times[-1]
        if schema == 2:
            expected = dict(presents_with_transaction=True, presentation_on_main_thread=True,
                            presentation_application_state=0, presentation_call_completed=True, completion_join_retired=True)
            require(all(type(frame.get(k)) is type(v) and frame[k] == v for k, v in expected.items()) and
                    frame.get('presentation_aborted', False) is False and type(frame.get('scheduled_status')) is int and
                    frame['scheduled_status'] in (3, 4), 'Missing actual scheduled/main-thread transaction presentation')
            scheduled, enqueued, callback = (frame.get(k) for k in ('scheduled_callback_seconds',
                                            'presentation_enqueued_seconds', 'presented_callback_seconds'))
            require(all(positive(t) for t in (scheduled, enqueued, callback)) and
                    times[0] <= scheduled <= enqueued <= callback and times[2] <= callback,
                    'Wrong scheduling/enqueue/display callback ordering')
            timing = timing and enqueued <= times[-1] <= callback
        scale = min(w/1280, h/720)
        expected_viewport = [(w-1280*scale)/2, (h-720*scale)/2, 1280*scale, 720*scale]
        viewport = frame.get('viewport')
        require(isinstance(viewport, list) and len(viewport) == 4 and
                all(type(v) in (int, float) and math.isfinite(v) and abs(v-e) < 0.01
                    for v, e in zip(viewport, expected_viewport)), 'Wrong aspect-preserving viewport')
    require(type(receipt.get('presentation_verified')) is bool and receipt['presentation_verified'] is timing and
            gate.get('presentation_verified') is timing, 'Actual display timing acceptance disagrees')
    return dict(scope='eight-linux-frame-gpu-receipt-consistency-only', gpu_sequence_verified=True, presentation_verified=timing,
                continuous_animation_verified=False, frame_pacing_verified=False,
                gameplay_verified=False, zero_copy_transport_verified=False,
                cryptographic_device_attestation=False)
