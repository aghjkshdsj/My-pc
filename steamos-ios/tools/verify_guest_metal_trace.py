#!/usr/bin/env python3
"""Validate native observer consistency; fixtures and reports are not attestation."""
import math
from verify_device_report import require


def validate(trace, nonce, expected_device):
    require(isinstance(trace, dict) and trace.get('schema') == 1 and
            trace.get('scope') == 'native-moltenvk-guest-command-completion', 'Wrong native Metal scope')
    require(trace.get('abi') == 1 and trace.get('run') == nonce and
            trace.get('status') == 'passed', 'Stale or incomplete native Metal observation')
    require(isinstance(expected_device, str) and expected_device.startswith('Apple ') and
            trace.get('expected_device_name') == expected_device, 'Wrong native GPU identity')
    require(trace.get('callback_source') == 'MVKQueueCommandBufferSubmission::commitActiveMTLCommandBuffer',
            'Native completion is not scoped to guest command submissions')
    for key in ('observer_configured', 'callbacks_drained', 'guest_pixels_passed', 'metal_host_verified'):
        require(trace.get(key) is True, 'Missing native completion condition: ' + key)
    for key in ('adds_gpu_work', 'host_memory_import_verified', 'presentation_verified', 'gameplay_verified'):
        require(trace.get(key) is False, 'Unsupported native Metal scope: ' + key)
    for key in ('pending', 'failed', 'overflow', 'unknown_callbacks', 'duplicate_callbacks',
                'identity_errors', 'initial_errors', 'invalid_timing'):
        require(type(trace.get(key)) is int and trace[key] == 0, 'Incomplete/invalid native callback: ' + key)
    samples = trace.get('samples')
    require(isinstance(samples, list) and 2 <= len(samples) <= 256, 'Missing or unbounded native completions')
    for key in ('observed_commit_points', 'completed'):
        require(type(trace.get(key)) is int and trace[key] == len(samples), 'Native command counts disagree')
    registry = None
    timed = 0
    for index, entry in enumerate(samples, 1):
        require(isinstance(entry, dict) and type(entry.get('token')) is int and entry['token'] == index,
                'Duplicate, missing or reordered native token')
        require(entry.get('completion_observed') is True and type(entry.get('status')) is int and
                entry['status'] == 4 and entry.get('has_error') is False and
                type(entry.get('error_code')) is int and entry['error_code'] == 0, 'Native command did not complete successfully')
        require(type(entry.get('device_registry_id')) is int and entry['device_registry_id'] > 0 and
                entry.get('device_name') == expected_device, 'Native command device identity differs')
        if registry is None: registry = entry['device_registry_id']
        require(registry == entry['device_registry_id'], 'Mixed native GPU registry identities')
        start, end = entry.get('gpu_start_seconds'), entry.get('gpu_end_seconds')
        require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (start, end)),
                'Invalid native GPU timestamps')
        # Completed buffers may have equal positive timestamps at the reported
        # precision. Match the shipped native ledger: keep these observations,
        # but only strictly positive durations count as timed GPU work.
        require((start == end == 0) or (start > 0 and end >= start), 'Incomplete or reversed GPU timing')
        if start > 0 and end > start: timed += 1
    require(type(trace.get('timed_completions')) is int and trace['timed_completions'] == timed and timed >= 2,
            'Missing native GPU execution timing')
    return {'scope': 'guest-native-metal-completion-receipt-consistency-only',
            'native_command_completions': len(samples), 'timed_completions': timed,
            'metal_host_verified': True, 'host_memory_import_verified': False,
            'presentation_verified': False, 'gameplay_verified': False,
            'cryptographic_device_attestation': False}
