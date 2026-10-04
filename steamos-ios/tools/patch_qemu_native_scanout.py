#!/usr/bin/env python3
"""Extend the pinned diagnostic engine, without replacing its accepted recipe."""
import argparse
import difflib
import hashlib
import json
import pathlib

PROJECT = pathlib.Path(__file__).resolve().parents[1]


def patch(qemu, receipt_dir):
    changes, rows, staged = [], {}, {}

    def edit(name, transforms):
        path = qemu / name
        before = path.read_text(encoding='utf-8')
        after = before
        for old, new in transforms:
            assert after.count(old) == 1, (name, old[:90])
            after = after.replace(old, new)
        staged[path] = after
        rows[name] = {'original_sha256': hashlib.sha256(before.encode()).hexdigest(),
                      'patched_sha256': hashlib.sha256(after.encode()).hexdigest()}
        changes.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                           fromfile='a/' + name, tofile='b/' + name))

    abi = (PROJECT / 'Engine/NativeScanoutABI.h').read_text(encoding='utf-8')
    header = qemu / 'include/ui/mpc-native-scanout.h'
    assert not header.exists()
    staged[header] = abi + '\nvoid mpc_scanout_metadata(uint32_t resource, uint32_t width, uint32_t height,\n' + \
                          '                          uint32_t format, uint32_t stride, uint32_t offset);\n'
    bridge = '''
/* Fresh native adapter. Configuration happens before qemu_init/worker threads. */
static MPCNativeScanoutCallback mpc_scanout_callback;
static void *mpc_scanout_context;
static MPCNativeScanoutEvent mpc_scanout_pending;
static uint64_t mpc_scanout_sequence, mpc_scanout_generation;
__attribute__((visibility("default")))
int mpc_qemu_configure_native_scanout(uint32_t abi, uint32_t bytes,
                                     MPCNativeScanoutCallback callback, void *context)
{
    if (abi != MPC_SCANOUT_ABI || bytes != sizeof(MPCNativeScanoutEvent) ||
        !callback || !context || mpc_scanout_callback || mpc_scanout_sequence) {
        return 0;
    }
    mpc_scanout_callback = callback;
    mpc_scanout_context = context;
    return 1;
}
void mpc_scanout_metadata(uint32_t resource, uint32_t width, uint32_t height,
                          uint32_t format, uint32_t stride, uint32_t offset)
{
    mpc_scanout_pending = (MPCNativeScanoutEvent) {
        .abi = MPC_SCANOUT_ABI, .bytes = sizeof(MPCNativeScanoutEvent),
        .resource_id = resource, .width = width, .height = height,
        .format = format, .stride = stride, .offset = offset,
    };
}
static void mpc_scanout_emit(MPCNativeScanoutEvent *event, uint32_t kind)
{
    event->sequence = ++mpc_scanout_sequence;
    event->kind = kind;
    if (mpc_scanout_callback) {
        mpc_scanout_callback(mpc_scanout_context, event);
    }
}
'''
    native_install = '''
#ifdef CONFIG_METAL
    if (edpy->native_active) {
        mpc_scanout_emit(&edpy->native_event, MPC_SCANOUT_DISABLE);
        edpy->native_active = false;
    }
    if (native.type == SCANOUT_TEXTURE_NATIVE_TYPE_METAL) {
        edpy->native_event = mpc_scanout_pending;
        edpy->native_event.generation = ++mpc_scanout_generation;
        edpy->native_event.texture = native.handle;
        edpy->native_event.x = x;
        edpy->native_event.y = y;
        edpy->native_event.crop_width = w;
        edpy->native_event.crop_height = h;
        edpy->native_event.y_0_top = backing_y_0_top;
        edpy->native_active = true;
        /* Native scanout bypasses the old GL framebuffer/CPU-readback branch. */
        mpc_scanout_emit(&edpy->native_event, MPC_SCANOUT_INSTALL);
        return;
    }
#endif
'''
    edit('ui/egl-headless.c', [
        ('#include "ui/shader.h"', '#include "ui/shader.h"\n#include "ui/mpc-native-scanout.h"\n' + bridge),
        ('    uint32_t pos_y;\n', '    uint32_t pos_y;\n    bool native_active;\n    MPCNativeScanoutEvent native_event;\n'),
        ('    egl_fb_destroy(&edpy->guest_fb);\n    egl_fb_destroy(&edpy->blit_fb);',
         '    if (edpy->native_active) {\n        mpc_scanout_emit(&edpy->native_event, MPC_SCANOUT_DISABLE);\n'
         '        edpy->native_active = false;\n    }\n    egl_fb_destroy(&edpy->guest_fb);\n    egl_fb_destroy(&edpy->blit_fb);'),
        ('    edpy->y_0_top = backing_y_0_top;', native_install + '\n    edpy->y_0_top = backing_y_0_top;'),
        ('    if (!edpy->guest_fb.texture || !edpy->ds) {',
         '    if (edpy->native_active) {\n        mpc_scanout_emit(&edpy->native_event, MPC_SCANOUT_FLUSH);\n'
         '        return;\n    }\n    if (!edpy->guest_fb.texture || !edpy->ds) {'),
    ])
    edit('hw/display/virtio-gpu-virgl.c', [
        ('#include "qemu/osdep.h"', '#include "qemu/osdep.h"\n#include "ui/mpc-native-scanout.h"'),
        ('        dpy_gl_scanout_texture(\n            scanout->con, 0,',
         '        mpc_scanout_metadata(ss->resource_id, ss->width, ss->height,\n'
         '                             ss->format, ss->strides[0], ss->offsets[0]);\n'
         '        dpy_gl_scanout_texture(\n            scanout->con, 0,'),
    ])
    edit('system/qemu.symbols', [('mpc_qemu_register_egl_headless;',
                                'mpc_qemu_register_egl_headless;\n    mpc_qemu_configure_native_scanout;')])
    for path, content in staged.items():
        path.write_text(content, encoding='utf-8')
    (receipt_dir / 'qemu-native-scanout.patch').write_text(''.join(changes), encoding='utf-8')
    receipt = {'schema': 1, 'scope': 'native-scanout-adapter-source-only', 'abi': 1,
               'files': rows, 'abi_header_sha256': hashlib.sha256(abi.encode()).hexdigest(),
               'borrowed_texture_callback': True, 'native_flush_cpu_readback_bypassed': True,
               'phone_tested': False, 'image_import_verified': False, 'presentation_verified': False}
    (receipt_dir / 'native-scanout-source.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('qemu', type=pathlib.Path)
    parser.add_argument('receipt_dir', type=pathlib.Path)
    args = parser.parse_args()
    patch(args.qemu.resolve(), args.receipt_dir.resolve())
