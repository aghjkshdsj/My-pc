#!/usr/bin/env python3
"""Validate real delayed/error/missing Linux response controls, never native proof."""
import json
import re
from run_kernel_gate import validate as validate_abi


def validate(text, nonce, case, engine_exit):
    if re.fullmatch('[0-9a-f]{32}', nonce) is None or case not in ('delayed', 'error', 'producer-error', 'missing'):
        raise ValueError('Invalid control identity')
    missing = case == 'missing'
    # The missing-response VM is deliberately terminated while retaining objects.
    # Require its completed ABI self-test, but do not fabricate an init/engine exit.
    if missing:
        if 'MPC_LINUX_EXIT=' in text or 'MPC_COMPLETION_EXIT=' in text:
            raise ValueError('Pending control unexpectedly exited')
        rows = [json.loads(line.removeprefix('MPC_LINUX_ABI ')) for line in text.splitlines()
                if line.startswith('MPC_LINUX_ABI ')]
        if len(rows) != 1:
            raise ValueError('Missing/duplicate completed ABI self-test')
        abi = rows[0]
        expected_abi = dict(schema=1, run=nonce, failures=0, machine='aarch64', elf_arch='aarch64',
                            page_bytes=4096, signals=True, mmap_protection=True,
                            pthread_tls_futex=True, fork_exec=True, checksum='1d250c45a7bbc87e')
        if any(abi.get(k) != v or type(abi.get(k)) is not type(v) for k, v in expected_abi.items()):
            raise ValueError('Incomplete ABI self-test before retained pending control')
        if any(type(abi.get(k)) not in (int, float) or abi[k] < 0 for k in ('wall_ms', 'cpu_ms')):
            raise ValueError('Invalid ABI timings')
    else:
        abi = validate_abi(text, nonce)
    rows = [json.loads(line.removeprefix('MPC_COMPLETION_RESULT ')) for line in text.splitlines()
            if line.startswith('MPC_COMPLETION_RESULT ')]
    if len(rows) != 1:
        raise ValueError('Missing/duplicate completion receipt')
    row = rows[0]
    expected = dict(schema=1, run=nonce, case=case, initial_status=1,
                    stage='missing-response-held' if missing else 'complete',
                    early_pending=2 if case == 'delayed' else 1,
                    events=0 if missing else (2 if case in ('delayed', 'producer-error') else 1),
                    positive_fences=2 if case == 'delayed' else 0,
                    error_fences=2 if case == 'producer-error' else (1 if case == 'error' else 0),
                    last_status=0 if missing else (-5 if case in ('error', 'producer-error') else 1),
                    buffers_retained=missing, cleaned=not missing, cpu_dumb_control=True,
                    metal_verified=False, physical_iphone=False)
    if set(row) != set(expected) or any(row[k] != v or type(row[k]) is not type(v) for k, v in expected.items()):
        raise ValueError('Incomplete/unsafe completion control')
    flushes = [json.loads(line.removeprefix('MPC_CONTROL_FLUSH ')) for line in text.splitlines()
               if line.startswith('MPC_CONTROL_FLUSH ')]
    if len(flushes) != (3 if case == 'delayed' else 2):
        raise ValueError('Wrong actual host flush count (failed producer must not flush)')
    identifiers = set()
    for index, flush in enumerate(flushes, 1):
        if set(flush) != {'index', 'fence_id'} or type(flush['index']) is not int or flush['index'] != index or \
           type(flush['fence_id']) is not int or not 0 < flush['fence_id'] < 2**64 or flush['fence_id'] in identifiers:
            raise ValueError('Invalid/duplicate host command response identity')
        identifiers.add(flush['fence_id'])
    if engine_exit != (-9 if missing else 0) or type(engine_exit) is not int:
        raise ValueError('Wrong normal/intentional termination boundary')
    if not missing and text.splitlines().count('MPC_COMPLETION_EXIT=0') != 1:
        raise ValueError('Missing successful Linux control exit')
    return dict(case=case, abi=abi, result=row, engine_exit=engine_exit,
                intentional_host_termination=missing, actual_linux_response_control=True,
                native_reader_dependency_verified=False, metal_verified=False, phone_verified=False)
