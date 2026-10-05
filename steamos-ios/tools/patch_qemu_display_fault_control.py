#!/usr/bin/env python3
"""Test-only CPU 2D deferred/error/missing flush responses. Never package in an IPA.

Fresh QEMU 10.0.12 UTM source archive; upstream GPL notices remain in changed files.
The timer is an injected test response, never a release deadline in the real engine.
"""
import argparse
import difflib
import hashlib
import json
import pathlib
from patch_linux_display_completion import once

UPSTREAM_FILES = {
    'include/hw/virtio/virtio-gpu.h': '7e804deaf4ad4f477aa61300221686982a9c69e8d1c5bd0ef891d0b3739991a2',
    'hw/display/virtio-gpu.c': 'c60e4a331567d2d9c2bf9effa74716532771383ba2bc3f086131de558e10df0f',
}


def transform(original):
    texts = dict(original)
    h = texts['include/hw/virtio/virtio-gpu.h']
    h = once(h, '    bool suspended;\n', '    bool suspended;\n'
             '    bool mpc_control_issued, mpc_control_ready;\n')
    h = once(h, '    uint64_t conf_max_hostmem;\n', '    uint64_t conf_max_hostmem;\n'
             '    uint32_t mpc_control_delay_ms, mpc_control_fail_at, mpc_control_missing_at;\n'
             '    uint32_t mpc_control_flushes;\n'
             '    QEMUTimer *mpc_control_timer;\n'
             '    struct virtio_gpu_ctrl_command *mpc_control_pending;\n')
    texts['include/hw/virtio/virtio-gpu.h'] = h
    c = texts['hw/display/virtio-gpu.c']
    c = once(c, '#include "qemu/error-report.h"', '#include "qemu/error-report.h"\n#include "qemu/timer.h"')
    c = once(c, '        cmd->suspended = false;\n',
             '        cmd->suspended = false;\n'
             '        cmd->mpc_control_issued = false;\n        cmd->mpc_control_ready = false;\n')
    c = once(c, 'static void virtio_gpu_reset_bh(void *opaque);',
             'static void virtio_gpu_reset_bh(void *opaque);\n\n'
             '/* Hosted CPU control only; this is not a Metal completion callback. */\n'
             'static void mpc_control_response(void *opaque)\n'
             '{\n    VirtIOGPU *g = opaque;\n'
             '    struct virtio_gpu_ctrl_command *cmd = g->mpc_control_pending;\n'
             '    assert(cmd && QTAILQ_FIRST(&g->cmdq) == cmd && cmd->suspended);\n'
             '    cmd->mpc_control_ready = true;\n'
             '    cmd->suspended = false;\n'
             '    g->mpc_control_pending = NULL;\n'
             '    virtio_gpu_process_cmdq(g);\n}\n')
    c = once(c, '    case VIRTIO_GPU_CMD_RESOURCE_FLUSH:\n        virtio_gpu_resource_flush(g, cmd);\n        break;',
             '    case VIRTIO_GPU_CMD_RESOURCE_FLUSH:\n'
             '        if (cmd->mpc_control_issued) {\n'
             '            if (!cmd->mpc_control_ready) {\n'
             '                cmd->suspended = true;\n                return;\n            }\n'
             '            if (g->mpc_control_flushes == g->mpc_control_fail_at) {\n'
             '                cmd->error = VIRTIO_GPU_RESP_ERR_UNSPEC;\n            }\n'
             '            break;\n        }\n'
             '        virtio_gpu_resource_flush(g, cmd);\n'
             '        if (!cmd->error && g->mpc_control_delay_ms &&\n'
             '            (cmd->cmd_hdr.flags & VIRTIO_GPU_FLAG_FENCE)) {\n'
             '            assert(!g->mpc_control_pending);\n'
             '            g->mpc_control_flushes++;\n'
             '            fprintf(stderr, "MPC_CONTROL_FLUSH {\\\"index\\\":%u,\\\"fence_id\\\":%" PRIu64 "}\\n",\n'
             '                    g->mpc_control_flushes, (uint64_t)cmd->cmd_hdr.fence_id);\n'
             '            cmd->mpc_control_issued = true;\n'
             '            cmd->suspended = true;\n'
             '            g->mpc_control_pending = cmd;\n'
             '            if (!g->mpc_control_timer) {\n'
             '                g->mpc_control_timer = timer_new_ms(QEMU_CLOCK_VIRTUAL, mpc_control_response, g);\n'
             '            }\n'
             '            if (g->mpc_control_flushes != g->mpc_control_missing_at) {\n'
             '                timer_mod(g->mpc_control_timer, qemu_clock_get_ms(QEMU_CLOCK_VIRTUAL) + g->mpc_control_delay_ms);\n'
             '            }\n            return;\n        }\n        break;')
    c = once(c, '    g_clear_pointer(&g->ctrl_bh, qemu_bh_delete);',
             '    g_clear_pointer(&g->mpc_control_timer, timer_free);\n'
             '    g->mpc_control_pending = NULL;\n    g_clear_pointer(&g->ctrl_bh, qemu_bh_delete);')
    c = once(c, '    if (qemu_in_vcpu_thread()) {\n',
             '    if (g->mpc_control_timer) {\n        timer_del(g->mpc_control_timer);\n    }\n'
             '    g->mpc_control_pending = NULL;\n    g->mpc_control_flushes = 0;\n'
             '    if (qemu_in_vcpu_thread()) {\n')
    c = once(c, '    DEFINE_PROP_SIZE("max_hostmem", VirtIOGPU, conf_max_hostmem,',
             '    DEFINE_PROP_UINT32("x-mpc-control-delay-ms", VirtIOGPU, mpc_control_delay_ms, 0),\n'
             '    DEFINE_PROP_UINT32("x-mpc-control-fail-at", VirtIOGPU, mpc_control_fail_at, 0),\n'
             '    DEFINE_PROP_UINT32("x-mpc-control-missing-at", VirtIOGPU, mpc_control_missing_at, 0),\n'
             '    DEFINE_PROP_SIZE("max_hostmem", VirtIOGPU, conf_max_hostmem,')
    texts['hw/display/virtio-gpu.c'] = c
    return texts


def patch(root, output):
    names = ('include/hw/virtio/virtio-gpu.h', 'hw/display/virtio-gpu.c')
    original = {name: (root / name).read_text(encoding='utf-8') for name in names}
    for name in names:
        if hashlib.sha256(original[name].encode()).hexdigest() != UPSTREAM_FILES[name]:
            raise ValueError('Unexpected upstream bytes: ' + name)
    changed = transform(original)
    output.mkdir(parents=True, exist_ok=False)
    diff = ''.join(''.join(difflib.unified_diff(original[n].splitlines(True), changed[n].splitlines(True),
                  fromfile='a/' + n, tofile='b/' + n)) for n in names)
    (output / 'qemu-display-fault-control.patch').write_text(diff, encoding='utf-8', newline='\n')
    receipt = dict(schema=1, scope='hosted-cpu-2d-injected-response-control-only',
                   physical_iphone=False, metal_verified=False, package_in_ipa=False,
                   files={n: dict(before_sha256=hashlib.sha256(original[n].encode()).hexdigest(),
                                  after_sha256=hashlib.sha256(changed[n].encode()).hexdigest()) for n in names})
    for name in names:
        (root / name).write_text(changed[name], encoding='utf-8', newline='\n')
    (output / 'patch-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('qemu', type=pathlib.Path)
    parser.add_argument('receipt', type=pathlib.Path)
    args = parser.parse_args()
    patch(args.qemu, args.receipt)
