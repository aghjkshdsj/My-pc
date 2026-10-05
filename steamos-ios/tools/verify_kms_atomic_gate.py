#!/usr/bin/env python3
"""Join actual Linux atomic-control receipts; never infer native reader completion."""
import json
import re
from run_kernel_gate import validate as validate_abi


def validate(text, nonce, device_present):
    if not isinstance(nonce, str) or re.fullmatch('[0-9a-f]{32}', nonce) is None:
        raise ValueError('Invalid KMS session')
    abi = validate_abi(text, nonce)
    prefixes = ('MPC_KMS_CAPS ', 'MPC_KMS_FLIP ', 'MPC_KMS_RESULT ')
    receipts = {prefix: [] for prefix in prefixes}
    ordered = []
    for line in text.splitlines():
        for prefix in prefixes:
            if line.startswith(prefix):
                row = json.loads(line[len(prefix):])
                if not isinstance(row, dict) or type(row.get('schema')) is not int or row.get('schema') != 1 or row.get('run') != nonce:
                    raise ValueError('Wrong/unsupported KMS receipt session')
                receipts[prefix].append(row)
                ordered.append(prefix)
    caps, flips, results = (receipts[prefix] for prefix in prefixes)
    if len(results) != 1:
        raise ValueError('Missing/duplicate KMS result')
    result = results[0]
    for name in ('native_reader_dependency_verified', 'metal_verified', 'desktop_verified', 'game_fps_verified'):
        if result.get(name) is not False:
            raise ValueError('Linux control cannot certify native display or product')
    if result.get('cpu_dumb_control') is not True or result.get('cleaned') is not True:
        raise ValueError('Missing control/cleanup boundary')
    if device_present:
        if ordered != ['MPC_KMS_CAPS '] + ['MPC_KMS_FLIP '] * 6 + ['MPC_KMS_RESULT ']:
            raise ValueError('Missing, duplicate or reordered atomic-control receipts')
        cap = caps[0]
        for name in ('connector', 'crtc', 'plane'):
            if type(cap.get(name)) is not int or not 0 < cap[name] < 2**32:
                raise ValueError('Invalid KMS object identity')
        if len({cap['connector'], cap['crtc'], cap['plane']}) != 3:
            raise ValueError('KMS objects alias')
        if (cap.get('width'), cap.get('height'), cap.get('format')) != (1280, 720, 'XRGB8888'):
            raise ValueError('Wrong output mode or format')
        if cap.get('native_reader_dependency_verified') is not False:
            raise ValueError('Property presence is not native-reader proof')
        if any(type(cap.get(name)) is not bool for name in ('in_fence_fd', 'out_fence_ptr')):
            raise ValueError('Unknown fence property presence')
        for index, flip in enumerate(flips, 1):
            if any(type(flip.get(name)) is not int for name in
                   ('index', 'slot', 'crtc', 'event_sequence', 'event_sec', 'event_usec')):
                raise ValueError('Malformed atomic event')
            if (flip['index'], flip['slot'], flip['crtc']) != (index, index % 3, cap['crtc']):
                raise ValueError('Wrong flip, framebuffer slot or CRTC')
            if not 0 <= flip['event_sequence'] < 2**32 or not 0 <= flip['event_sec'] < 2**32 or not 0 <= flip['event_usec'] < 1000000:
                raise ValueError('Invalid virtual event timestamp')
            if flip.get('out_fence_signaled') is not cap['out_fence_ptr']:
                raise ValueError('Missing actual sync-file signal')
            if flip.get('native_display_timestamp') is not False or flip.get('metal_completion_verified') is not False:
                raise ValueError('Virtual atomic event cannot certify Metal/display timing')
        expected = dict(stage='complete', exit_code=0, errno=0, buffers=3, flips=6,
                        signaled_out_fences=6 if cap['out_fence_ptr'] else 0,
                        invalid_geometry_rejected=True, invalid_input_fence_rejected=cap['in_fence_fd'])
        for name, value in expected.items():
            if result.get(name) != value or type(result.get(name)) is not type(value):
                raise ValueError('Incomplete control result: ' + name)
        if type(result.get('invalid_geometry_errno')) is not int or result['invalid_geometry_errno'] not in (22, 34):
            raise ValueError('Invalid geometry did not fail validation')
        input_errno = result.get('invalid_input_fence_errno')
        if type(input_errno) is not int or (input_errno not in (9, 22) if cap['in_fence_fd'] else input_errno != 0):
            raise ValueError('Invalid input fence did not fail descriptor validation')
        if text.splitlines().count('MPC_KMS_EXIT=0') != 1:
            raise ValueError('Missing/duplicate successful guest exit')
    else:
        if caps or flips or result.get('stage') != 'open-drm' or result.get('exit_code') != 1 or result.get('errno') != 2:
            raise ValueError('Missing device did not reject at device boundary')
        if any(result.get(name) != 0 for name in ('buffers', 'flips', 'signaled_out_fences')):
            raise ValueError('Missing device claimed display work')
        if result.get('invalid_geometry_rejected') is not False or result.get('invalid_input_fence_rejected') is not False:
            raise ValueError('Missing device claimed validation work')
        if result.get('invalid_geometry_errno') != 0 or result.get('invalid_input_fence_errno') != 0:
            raise ValueError('Missing device claimed property validation')
        if text.splitlines().count('MPC_KMS_EXIT=1') != 1:
            raise ValueError('Missing/duplicate rejection exit')
    return dict(scope='hosted-linux-standard-atomic-api-cpu-control', abi=abi,
                capabilities=caps[0] if caps else None, flips=flips, result=result,
                phone_verified=False, native_reader_dependency_verified=False,
                metal_verified=False, desktop_verified=False, game_fps_verified=False)
