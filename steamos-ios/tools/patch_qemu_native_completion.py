#!/usr/bin/env python3
"""Separate ABI2 engine fork: defer the exact flush until native readers finish.

Apply only AFTER the accepted GPU and ABI1 scanout patches. Check every complete
input hash and transformation before writing. No old app/engine is modified.
QEMU changes remain GPL-2.0-or-later; fresh ABI/ledger are MIT.
"""
import argparse
import difflib
import hashlib
import json
import pathlib

PROJECT = pathlib.Path(__file__).resolve().parents[1]
PINS = {
    'hw/display/virtio-gpu.c': '669effd30d221024f40af56b842247a5a2be8c68bc471ac533415214ac48d304',
    'hw/display/virtio-gpu-gl.c': '36ae5b2763e48aa696a574ac7c50c46e59020cfa47989d1c2d0deb000ad174f4',
    'include/hw/virtio/virtio-gpu.h': '25e032f22e32d860fea74c1e598de1df0268111a1d2e7367dcbdd9e5f42a8a73',
    'ui/egl-headless.c': '53dc53535c5b4fdc7b0c366786fc178c909a6a54da75f12205bf01eceebd72c3',
    'hw/display/virtio-gpu-virgl.c': '2aa4d94f53aa5c10153a76fb9e64658d02d423427c9bd0e0001e842b5472d368',
    'system/qemu.symbols': '201f70b8fd8b95d4e08e5b1a96b93c66d6df2c50bbbab8a066d971935360f93a',
}
def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def once(text, old, new):
    if text.count(old) != 1: raise ValueError('Unsupported completion anchor: ' + old[:90])
    return text.replace(old, new)

def transform(original):
    for name, pin in PINS.items():
        if sha(original[name]) != pin: raise ValueError('Unsupported engine input: ' + name)
    changed = dict(original)
    e = changed['ui/egl-headless.c']
    e = once(e, '#include "ui/mpc-native-scanout.h"',
             '#include "ui/mpc-native-scanout.h"\n#include "ui/mpc-native-completion.h"')
    e = once(e, '!callback || !context || mpc_scanout_callback || mpc_scanout_sequence)',
             '!callback || !context || mpc_scanout_callback || mpc_native_completion_enabled() || mpc_scanout_sequence)')
    e = once(e, 'static void mpc_scanout_emit(',
             (PROJECT / 'Engine/QEMUNativeCompletion.inc').read_text(encoding='utf-8') + '\nstatic void mpc_scanout_emit(')
    e = once(e, '    if (mpc_scanout_callback) {\n        mpc_scanout_callback',
             '    if (mpc_completion_callback) {\n        mpc_completion_emit(event, kind);\n    }\n'
             '    if (mpc_scanout_callback) {\n        mpc_scanout_callback')
    changed['ui/egl-headless.c'] = e
    h = changed['include/hw/virtio/virtio-gpu.h']
    h = once(h, '    bool deferred;\n', '    bool deferred;\n    bool mpc_native_issued;\n')
    changed['include/hw/virtio/virtio-gpu.h'] = h
    c = changed['hw/display/virtio-gpu.c']
    c = once(c, '#include "qemu/error-report.h"', '#include "qemu/error-report.h"\n#include "ui/mpc-native-completion.h"')
    c = once(c, '        cmd->deferred = false;', '        cmd->deferred = false;\n        cmd->mpc_native_issued = false;')
    c = once(c, '    g_clear_pointer(&g->ctrl_bh, qemu_bh_delete);',
             '    mpc_native_completion_drain(g);\n    g_clear_pointer(&g->ctrl_bh, qemu_bh_delete);')
    c = once(c, '    QTAILQ_FOREACH_SAFE(res, &g->reslist, next, tmp) {\n        resource_id = res->resource_id;',
             '    mpc_native_completion_drain(g);\n\n'
             '    QTAILQ_FOREACH_SAFE(res, &g->reslist, next, tmp) {\n        resource_id = res->resource_id;')
    # Cursor queue is independent: do not let it mutate a retained reader's source.
    c = once(c, '    virtio_gpu_handle_cursor(&g->parent_obj.parent_obj, g->cursor_vq);',
             '    if (mpc_native_completion_busy(g)) return;\n'
             '    virtio_gpu_handle_cursor(&g->parent_obj.parent_obj, g->cursor_vq);')
    changed['hw/display/virtio-gpu.c'] = c
    gl = changed['hw/display/virtio-gpu-gl.c']
    gl = once(gl, '#include "qemu/osdep.h"', '#include "qemu/osdep.h"\n#include "ui/mpc-native-completion.h"')
    gl = once(gl, '        cmd->suspended = false;',
              '        cmd->suspended = false;\n        cmd->deferred = false;\n        cmd->mpc_native_issued = false;')
    gl = once(gl, '    if (gl->renderer_state >= RS_INITED) {',
              '    mpc_native_completion_drain(g);\n    if (gl->renderer_state >= RS_INITED) {')
    changed['hw/display/virtio-gpu-gl.c'] = gl
    v = changed['hw/display/virtio-gpu-virgl.c']
    v = once(v, '#include "ui/mpc-native-scanout.h"',
             '#include "ui/mpc-native-scanout.h"\n#include "ui/mpc-native-completion.h"')
    v = once(v, 'static void virgl_cmd_resource_flush(', 'static uint32_t virgl_cmd_resource_flush(')
    v = once(v, '    VIRTIO_GPU_FILL_CMD(rf);',
             '    uint32_t outputs = 0;\n'
             '    if (iov_to_buf(cmd->elem.out_sg, cmd->elem.out_num, 0, &rf, sizeof(rf)) != sizeof(rf)) {\n'
             '        cmd->error = VIRTIO_GPU_RESP_ERR_INVALID_PARAMETER;\n        return UINT32_MAX;\n    }')
    v = once(v, '        virtio_gpu_rect_update(g, i, rf.r.x, rf.r.y, rf.r.width, rf.r.height);\n    }\n}',
             '        if (g->parent_obj.scanout[i].con) outputs++;\n'
             '        virtio_gpu_rect_update(g, i, rf.r.x, rf.r.y, rf.r.width, rf.r.height);\n    }\n'
             '    return outputs;\n}')
    v = once(v, '        virgl_cmd_resource_flush(g, cmd);',
             '        if (mpc_native_completion_enabled()) {\n'
             '            if (!cmd->mpc_native_issued) {\n'
             '                if (!mpc_native_completion_begin(g)) {\n'
             '                    cmd->error = VIRTIO_GPU_RESP_ERR_UNSPEC;\n                    break;\n                }\n'
             '                cmd->mpc_native_issued = true;\n'
             '                mpc_native_completion_seal(virgl_cmd_resource_flush(g, cmd));\n            }\n'
             '            bool failed = false;\n'
             '            if (!mpc_native_completion_finish(g, &failed)) cmd_suspended = true;\n'
             '            else if (failed) cmd->error = VIRTIO_GPU_RESP_ERR_UNSPEC;\n'
             '        } else {\n            virgl_cmd_resource_flush(g, cmd);\n        }')
    # A failed renderer fence is an error, including the old dead-context fallback.
    anchor = '                    (uint64_t)cmd->cmd_hdr.fence_id);\n            virtio_gpu_ctrl_response_nodata(g, cmd, VIRTIO_GPU_RESP_OK_NODATA);'
    v = once(v, anchor, anchor.replace('VIRTIO_GPU_RESP_OK_NODATA', 'VIRTIO_GPU_RESP_ERR_UNSPEC'))
    v = once(v, '    virgl_renderer_create_fence(cmd->cmd_hdr.fence_id, cmd->cmd_hdr.type);',
             '    if (virgl_renderer_create_fence(cmd->cmd_hdr.fence_id, cmd->cmd_hdr.type)) {\n'
             '        virtio_gpu_ctrl_response_nodata(g, cmd, VIRTIO_GPU_RESP_ERR_UNSPEC);\n    }')
    v = once(v, '    virgl_renderer_reset();',
             '    mpc_native_completion_drain(g);\n    virgl_renderer_reset();')
    v = once(v, 'void virtio_gpu_virgl_reset_scanout(VirtIOGPU *g)\n{\n    int i;\n',
             'void virtio_gpu_virgl_reset_scanout(VirtIOGPU *g)\n{\n    int i;\n\n    mpc_native_completion_drain(g);\n')
    changed['hw/display/virtio-gpu-virgl.c'] = v
    s = changed['system/qemu.symbols']
    s = once(s, 'mpc_qemu_configure_native_scanout;',
             'mpc_qemu_configure_native_scanout;\n    mpc_qemu_configure_native_completion;\n    mpc_qemu_complete_native_read;')
    changed['system/qemu.symbols'] = s
    return changed

def patch(qemu, receipt_dir):
    originals = {n: (qemu / n).read_text(encoding='utf-8') for n in PINS}
    changed = transform(originals)
    abi = (PROJECT / 'Engine/NativeCompletionABI.h').read_text(encoding='utf-8')
    abi = abi.replace('"NativeScanoutABI.h"', '"ui/mpc-native-scanout.h"')
    abi += '''
struct VirtIOGPU;
int mpc_qemu_configure_native_completion(uint32_t, uint32_t, MPCNativeCompletionCallback, void *);
int mpc_qemu_complete_native_read(const MPCNativeReadToken *, uint32_t);
bool mpc_native_completion_enabled(void);
bool mpc_native_completion_busy(struct VirtIOGPU *);
bool mpc_native_completion_begin(struct VirtIOGPU *);
void mpc_native_completion_seal(uint32_t);
bool mpc_native_completion_finish(struct VirtIOGPU *, bool *);
void mpc_native_completion_drain(struct VirtIOGPU *);
'''
    ledger = (PROJECT / 'Engine/NativeCompletionLedger.h').read_text(encoding='utf-8')
    ledger = ledger.replace('"NativeCompletionABI.h"', '"ui/mpc-native-completion.h"')
    added = {'include/ui/mpc-native-completion.h': abi, 'include/ui/mpc-native-completion-ledger.h': ledger}
    if any((qemu / n).exists() for n in added): raise ValueError('Fresh completion headers required')
    diff = ''.join(''.join(difflib.unified_diff(originals[n].splitlines(True), changed[n].splitlines(True),
        fromfile='a/' + n, tofile='b/' + n)) for n in PINS)
    rows = {n: {'original_sha256': sha(originals[n]), 'patched_sha256': sha(changed[n])} for n in PINS}
    rows.update({n: {'original_sha256': None, 'patched_sha256': sha(s)} for n, s in added.items()})
    for n, text in {**changed, **added}.items():
        f=qemu / n; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text, encoding='utf-8', newline='\n')
    (receipt_dir / 'qemu-native-completion.patch').write_text(diff, encoding='utf-8', newline='\n')
    receipt={'schema': 1, 'scope': 'native-completion-adapter-source-only', 'abi': 2, 'files': rows,
        'exact_flush_waits_for_all_native_readers': True, 'max_readers': 16,
        'renderer_fence_failure_is_error': True, 'reset_teardown_waits_for_gpu_terminals': True,
        'physical_ios_compiled': False, 'metal_join_runtime_verified': False, 'phone_tested': False}
    (receipt_dir / 'native-completion-source.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('qemu', type=pathlib.Path); parser.add_argument('receipt_dir', type=pathlib.Path)
    args=parser.parse_args(); patch(args.qemu.resolve(), args.receipt_dir.resolve())
