"""Check preserved GPU work in build21's failed display-timing gate.

This never accepts screen presentation, animation or games. The original failed
report is checked directly; neither its status nor its timestamps are rewritten.
"""
import math
from verify_device_report import require


def validate(gate, nonce, transaction=False):
    receipt = gate.get('screen_presentation', {})
    imported = gate.get('image_import', {})
    require(gate.get('status') == 'failed' and gate.get('screen_presentation_requested') is True and
            gate.get('presentation_verified') is False and imported.get('host_memory_import_verified') is True,
            'Need failed screen acceptance with separately verified image import')
    require(receipt.get('schema') == 1 and receipt.get('scope') == 'physical-ios-linux-two-image-screen-gate' and
            receipt.get('run') == nonce and receipt.get('presentation_verified') is False and
            receipt.get('reason') == 'screen-presentation-acceptance-incomplete', 'Wrong failed screen receipt')
    native = receipt.get('native', {})
    registry = imported.get('native', {}).get('registry_id')
    fixed = dict(schema=2 if transaction else 1, scope='native-metal-two-linux-image-screen', run=nonce, registry_id=registry,
                 pending=0, interrupted=not transaction, surface_visible=True, maximum_inflight=1,
                 drawable_limit=2, diagnostic_source_readbacks=2, drawable_cpu_readbacks=0)
    require(type(registry) is int and registry > 0 and imported.get('run') == nonce and
            all(type(native.get(k)) is type(v) and native[k] == v for k, v in fixed.items()),
            'Not the known completed but interrupted screen diagnostic')
    for row in (receipt, native):
        for key in ('continuous_animation_verified', 'frame_pacing_verified', 'zero_copy_transport_verified', 'gameplay_verified'):
            require(row.get(key) is False, 'Unsupported failed-screen claim: ' + key)
    frames, images = native.get('frames'), imported.get('native', {}).get('images')
    require(isinstance(frames, list) and len(frames) in ((2,) if transaction else (1, 2)) and isinstance(images, list) and len(images) == 2 and
            type(native.get('errors')) is int and native['errors'] == 2-len(frames),
            'Wrong partial frame count/rejection count')
    if transaction:
        require(native.get('presentation_route') == 'scheduled-main-thread-core-animation-transaction' and
                native.get('lifecycle_events') == [], 'Not the known uninterrupted transaction attempt')
    geometry = native.get('surface_geometry')
    require(type(geometry) is int and geometry > 0, 'No observed screen geometry')
    resources, generations, durations = set(), set(), []
    for i, (frame, image) in enumerate(zip(frames, images)):
        require(isinstance(frame, dict) and isinstance(image, dict), 'Wrong screen row type')
        for key in ('resource_id', 'generation', 'phase'):
            require(type(frame.get(key)) is int and frame[key] == image.get(key), 'Screen/import identity differs')
        require(frame['resource_id'] > 0 and frame['resource_id'] not in resources and
                frame['generation'] > 0 and frame['generation'] not in generations, 'Repeated screen source')
        resources.add(frame['resource_id']); generations.add(frame['generation'])
        expected = dict(frame_index=i+1, phase=41 if i else 0, source_registry_id=registry,
            drawable_registry_id=registry, source_is_imported_guest_texture=True,
            source_width=1280, source_height=720, source_pixel_format=80, drawable_pixel_format=80,
            geometry=geometry, gpu_completed=True, drawable_presented=True, consumer_status=4, consumer_error=False)
        require(all(type(frame.get(k)) is type(v) and frame[k] == v for k, v in expected.items()) and
                'error' not in frame, 'Wrong source/device/GPU completion')
        require(type(frame.get('drawable_id')) is int and frame['drawable_id'] >= 0 and
                type(frame.get('presented_seconds')) in (int, float) and frame['presented_seconds'] == 0,
                'Need the original zero display timestamp; callbacks alone do not certify presentation')
        times = [frame.get(k) for k in ('submit_seconds', 'gpu_start_seconds', 'gpu_end_seconds')]
        require(all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in times) and times == sorted(times),
                'Missing/out-of-order actual GPU timing')
        w, h = frame.get('drawable_width'), frame.get('drawable_height')
        require(type(w) is int and type(h) is int and 0 < w <= 16384 and 0 < h <= 16384, 'Wrong drawable size')
        scale = min(w/1280, h/720)
        expected_viewport = [(w-1280*scale)/2, (h-720*scale)/2, 1280*scale, 720*scale]
        viewport = frame.get('viewport')
        require(isinstance(viewport, list) and len(viewport) == 4 and
            all(type(v) in (int, float) and math.isfinite(v) and abs(v-e) < .01
                for v, e in zip(viewport, expected_viewport)), 'Wrong screen viewport')
        durations.append((times[2]-times[1])*1000)
        if transaction:
            route = dict(presents_with_transaction=True, presentation_on_main_thread=True, presentation_application_state=0,
                         presentation_call_completed=True, completion_join_retired=True, presented_seconds_later_query=0)
            require(all(type(frame.get(k)) is type(v) and frame[k] == v for k,v in route.items()) and
                    frame.get('presentation_aborted', False) is False and type(frame.get('scheduled_status')) is int and
                    frame['scheduled_status'] in (3, 4), 'Wrong transaction/late-query evidence')
            scheduled,enqueued,callback,completed,later=(frame.get(k) for k in ('scheduled_callback_seconds',
                'presentation_enqueued_seconds','presented_callback_seconds','gpu_completed_callback_seconds','later_query_host_seconds'))
            require(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (scheduled,enqueued,callback,completed,later)) and
                    times[0] <= scheduled <= enqueued <= callback <= later and times[-1] <= callback and times[-1] <= completed,
                    'Wrong scheduling/GPU/callback/late-query ordering')
    return dict(scope='failed-screen-gate-preserved-gpu-progress-only',
        failure='zero-callback-and-late-display-timestamps-without-interruption' if transaction else 'zero-actual-display-timestamps-and-sticky-interruption',
        completed_screen_gpu_consumers=len(frames),
        imported_resources=list(sorted(resources)), screen_consumer_gpu_durations_ms=durations,
        drawable_callbacks_with_zero_display_time=len(frames), presentation_verified=False,
        continuous_animation_verified=False, frame_pacing_verified=False, gameplay_verified=False,
        zero_copy_transport_verified=False, cryptographic_device_attestation=False)
