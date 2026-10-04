#!/usr/bin/env python3
"""Observe real upstream Metal queue submissions; never replace rendering."""
import difflib
import hashlib
import json
import pathlib
import shutil
import sys


def patch(source, output, project):
    relative = 'MoltenVK/MoltenVK/GPUObjects/MVKQueue.mm'
    path = source / relative
    original = path.read_text(encoding='utf-8')
    assert 'mpcObserveGuestMetalCommit' not in original
    anchor = '#include "MVKGPUCapture.h"\n'
    assert original.count(anchor) == 1
    # Instrument command submissions, excluding waitIdle and surface-present
    # marker buffers. The existing commit/release/error flow is unchanged.
    commit = '\tVkResult rslt = mtlCmdBuff ? getConfigurationResult() : VK_ERROR_OUT_OF_POOL_MEMORY;\n\t[mtlCmdBuff commit];'
    assert original.count(commit) == 1
    changed = original.replace(anchor, anchor + '#include "MoltenVKGuestTrace.h"\n')
    changed = changed.replace(commit, commit.replace('\t[mtlCmdBuff commit];',
        '\tmpcObserveGuestMetalCommit(mtlCmdBuff);\n\t[mtlCmdBuff commit];'))
    path.write_text(changed, encoding='utf-8')
    copied = {}
    for name in ['MetalGuestTraceABI.h', 'MoltenVKGuestTrace.h']:
        data = (project / 'Engine' / name).read_bytes()
        (path.parent / name).write_bytes(data)
        (output / name).write_bytes(data)
        copied[name] = hashlib.sha256(data).hexdigest()
    shutil.copyfile(project / 'tests/MoltenTraceAdapterTests.mm', output / 'MoltenTraceAdapterTests.mm')
    diff = ''.join(difflib.unified_diff(original.splitlines(keepends=True), changed.splitlines(keepends=True),
        fromfile='a/' + relative, tofile='b/' + relative))
    (output / 'guest-metal-completion-observer.patch').write_text(diff, encoding='utf-8')
    receipt = {'schema': 1, 'scope': 'moltenvk-real-command-completion-observer-source-only',
        'abi': 1, 'source_before_sha256': hashlib.sha256(original.encode()).hexdigest(),
        'source_after_sha256': hashlib.sha256(changed.encode()).hexdigest(),
        'headers': copied, 'actual_command_submission_site': True,
        'wait_idle_marker_excluded': True, 'surface_present_marker_excluded': True,
        'adds_gpu_work': False, 'changes_submission_result': False,
        'success_override': False, 'native_adapter_fixtures_passed': False,
        'phone_tested': False, 'metal_execution_verified': False,
        'host_memory_import_verified': False, 'presentation_verified': False}
    (output / 'metal-trace-source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    source, output = map(pathlib.Path, sys.argv[1:])
    patch(source.resolve(), output.resolve(), pathlib.Path(__file__).resolve().parents[1])
