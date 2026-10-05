#!/usr/bin/env python3
"""Opt-in display completion fork of exactly Linux 6.12.111 (upstream notices retained).

This joins Linux's atomic OUT_FENCE to a matching fenced RESOURCE_FLUSH response.
It does not prove that the engine response is joined to Metal; that is a separate gate.
All transformations are checked before any source is written. No old payload changes.
"""
import argparse
import difflib
import hashlib
import json
import pathlib

FILES = ('virtgpu_drv.h', 'virtgpu_fence.c', 'virtgpu_vq.c', 'virtgpu_plane.c')
UPSTREAM_FILES = dict(zip(FILES, (
    '4e75ff1c5da3a2001c2a372a2a27db86db99d6f7fd114afcb738a30afbe8f6e9',
    '83199ad3f23fab434eba62d6cc821939fac4d3967f4ebe7f6b4f0fe73da62fb3',
    '73f4ea19d59267017631621f44dd5d7cc68661112a3251abb45dfc23b23f0665',
    '81fb8aed2433252c38e98337b3da34c6c18d7793d9beca6af684b75a6c261e10')))


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unsupported/previously patched kernel anchor: ' + before[:90])
    return text.replace(before, after)


def transform(original):
    texts = dict(original)
    h = texts['virtgpu_drv.h']
    h = once(h, '\tstruct virtio_gpu_fence *fence;\n};\n#define to_virtio_gpu_plane_state',
             '\tstruct virtio_gpu_fence *fence;\n\tstruct dma_fence *mpc_producer_fence;\n};\n#define to_virtio_gpu_plane_state')
    h = once(h, '\t\t\t\t    u64 fence_id);', '\t\t\t\t    u64 fence_id, int error);')
    texts['virtgpu_drv.h'] = h
    f = texts['virtgpu_fence.c']
    f = once(f, '\t\t\t\t    u64 fence_id)\n', '\t\t\t\t    u64 fence_id, int error)\n')
    f = once(f, '\t\tdma_fence_signal_locked(&signaled->f);',
             '\t\t/* The exact response may fail; never turn it into a successful fence. */\n'
             '\t\tif (error < 0)\n\t\t\tdma_fence_set_error(&signaled->f, error);\n'
             '\t\tdma_fence_signal_locked(&signaled->f);')
    texts['virtgpu_fence.c'] = f
    v = texts['virtgpu_vq.c']
    v = once(v, '\t\t\tvirtio_gpu_fence_event_process(vgdev, fence_id);',
             '\t\t\tvirtio_gpu_fence_event_process(vgdev, fence_id,\n'
             '\t\t\t\tle32_to_cpu(resp->type) >= VIRTIO_GPU_RESP_ERR_UNSPEC ? -EIO : 0);')
    texts['virtgpu_vq.c'] = v
    p = texts['virtgpu_plane.c']
    p = once(p, '#include <drm/drm_fourcc.h>', '#include <drm/drm_fourcc.h>\n'
             '#include <drm/drm_atomic.h>\n#include <drm/drm_file.h>\n'
             '#include <drm/drm_gem_atomic_helper.h>\n#include <drm/drm_vblank.h>\n'
             '#include <linux/moduleparam.h>')
    p = once(p, '#include "virtgpu_drv.h"\n', '#include "virtgpu_drv.h"\n\n'
             '/* Fresh fork only. The shipping diagnostic payload does not enable this. */\n'
             'static bool mpc_native_display_fences;\n'
             'module_param_named(mpc_native_display_fences, mpc_native_display_fences, bool, 0400);\n'
             'MODULE_PARM_DESC(mpc_native_display_fences, "Wait for exact primary display responses; no timeout release");\n\n'
             'static void mpc_output_error(struct drm_plane *plane, struct drm_atomic_state *state, int error)\n'
             '{\n\tstruct drm_plane_state *ps = drm_atomic_get_new_plane_state(state, plane);\n'
             '\tstruct drm_crtc_state *cs;\n\tunsigned long flags;\n\n'
             '\tif (!mpc_native_display_fences || error >= 0 || !ps || !ps->crtc)\n\t\treturn;\n'
             '\tcs = drm_atomic_get_new_crtc_state(state, ps->crtc);\n'
             '\tif (!cs)\n\t\treturn;\n'
             '\t/* Mark this transaction before fake_vblank sends its event/fence. */\n'
             '\tspin_lock_irqsave(&plane->dev->event_lock, flags);\n'
             '\tif (cs->event && cs->event->base.fence)\n'
             '\t\tdma_fence_set_error(cs->event->base.fence, error);\n'
             '\tspin_unlock_irqrestore(&plane->dev->event_lock, flags);\n}\n')
    p = once(p, 'static void virtio_gpu_resource_flush(struct drm_plane *plane,',
             'static void virtio_gpu_resource_flush(struct drm_plane *plane,\n'
             '\t\t\t\t      struct drm_atomic_state *state,')
    start = p.index('static void virtio_gpu_resource_flush(')
    end = p.index('static void virtio_gpu_primary_plane_update(', start)
    flush = once(p[start:end], '\t\tif (!objs)\n\t\t\treturn;\n'
             '\t\tvirtio_gpu_array_add_obj(objs, vgfb->base.obj[0]);\n'
             '\t\tif (virtio_gpu_lock_one_resv_uninterruptible(objs)) {',
             '\t\tif (!objs) {\n\t\t\tmpc_output_error(plane, state, -ENOMEM);\n\t\t\treturn;\n\t\t}\n'
             '\t\tvirtio_gpu_array_add_obj(objs, vgfb->base.obj[0]);\n'
             '\t\tif (virtio_gpu_lock_one_resv_uninterruptible(objs)) {\n'
             '\t\t\tmpc_output_error(plane, state, -EIO);')
    p = p[:start] + flush + p[end:]
    p = once(p, '\t\tdma_fence_wait_timeout(&vgplane_st->fence->f, true,\n'
             '\t\t\t\t       msecs_to_jiffies(50));',
             '\t\tif (mpc_native_display_fences) {\n'
             '\t\t\t/* A missing response retains the buffer; deadlines do not release it. */\n'
             '\t\t\tint ret = dma_fence_wait(&vgplane_st->fence->f, false);\n'
             '\t\t\tif (!ret)\n\t\t\t\tret = dma_fence_get_status(&vgplane_st->fence->f);\n'
             '\t\t\tif (ret <= 0)\n\t\t\t\tmpc_output_error(plane, state, ret < 0 ? ret : -EIO);\n'
             '\t\t} else {\n\t\t\tdma_fence_wait_timeout(&vgplane_st->fence->f, true,\n'
             '\t\t\t\t\t       msecs_to_jiffies(50));\n\t\t}')
    p = once(p, '\tbo = gem_to_virtio_gpu_obj(plane->state->fb->obj[0]);\n\tif (bo->dumb)',
             '\tif (mpc_native_display_fences) {\n'
             '\t\tstruct virtio_gpu_plane_state *ps = to_virtio_gpu_plane_state(plane->state);\n'
             '\t\t/* Atomic helpers already waited; retain the producer status they discard. */\n'
             '\t\tif (ps->mpc_producer_fence) {\n'
             '\t\t\tint ret = dma_fence_get_status(ps->mpc_producer_fence);\n'
             '\t\t\tif (ret <= 0) {\n\t\t\t\tmpc_output_error(plane, state, ret < 0 ? ret : -EIO);\n'
             '\t\t\t\treturn;\n\t\t\t}\n\t\t}\n\t}\n'
             '\tbo = gem_to_virtio_gpu_obj(plane->state->fb->obj[0]);\n\tif (bo->dumb)')
    p = once(p, '\tvirtio_gpu_resource_flush(plane,\n', '\tvirtio_gpu_resource_flush(plane, state,\n')
    # Nonblocking state swaps can advance plane->state while an older commit is
    # waiting. Work only from this transaction's retained new state.
    start = p.index('static void virtio_gpu_resource_flush(')
    end = p.index('static int virtio_gpu_plane_prepare_fb(', start)
    display = p[start:end]
    display = once(display, '{\n\tstruct drm_device *dev = plane->dev;',
                   '{\n\tstruct drm_plane_state *new_state = drm_atomic_get_new_plane_state(state, plane);\n'
                   '\tstruct drm_device *dev = plane->dev;')
    display = once(display, '\tstruct drm_plane_state *old_state = drm_atomic_get_old_plane_state(state,',
                   '\tstruct drm_plane_state *new_state = drm_atomic_get_new_plane_state(state, plane);\n'
                   '\tstruct drm_plane_state *old_state = drm_atomic_get_old_plane_state(state,')
    display = display.replace('plane->state', 'new_state')
    display = once(display, '!output->crtc.state->active',
                   '!drm_atomic_get_new_crtc_state(state, &output->crtc)->active')
    damage = '\tif (!drm_atomic_helper_damage_merged(old_state, new_state, &rect))\n\t\treturn;\n\n'
    display = once(display, damage, '')
    display = once(display, '\tbo = gem_to_virtio_gpu_obj(new_state->fb->obj[0]);\n\tif (bo->dumb)',
                   damage + '\tbo = gem_to_virtio_gpu_obj(new_state->fb->obj[0]);\n\tif (bo->dumb)')
    p = p[:start] + display + p[end:]
    p = once(p, '\tif (!bo || (plane->type == DRM_PLANE_TYPE_PRIMARY && !bo->guest_blob))\n',
             '\tif (bo && mpc_native_display_fences && plane->type == DRM_PLANE_TYPE_PRIMARY) {\n'
             '\t\tint ret = drm_gem_plane_helper_prepare_fb(plane, new_state);\n'
             '\t\tif (ret)\n\t\t\treturn ret;\n'
             '\t\tvgplane_st->mpc_producer_fence = dma_fence_get(new_state->fence);\n'
             '\t\t/* Unique Linux context: a later unrelated response cannot release this one. */\n'
             '\t\tvgplane_st->fence = virtio_gpu_fence_alloc(vgdev, dma_fence_context_alloc(1), 0);\n'
             '\t\tif (!vgplane_st->fence) {\n'
             '\t\t\tdma_fence_put(vgplane_st->mpc_producer_fence);\n'
             '\t\t\tvgplane_st->mpc_producer_fence = NULL;\n\t\t\treturn -ENOMEM;\n\t\t}\n'
             '\t\t/* Linux context isolation must not request a nonexistent renderer ring. */\n'
             '\t\tvgplane_st->fence->emit_fence_info = false;\n\t\treturn 0;\n\t}\n'
             '\tif (!bo || (plane->type == DRM_PLANE_TYPE_PRIMARY && !bo->guest_blob))\n')
    p = once(p, '\tvgplane_st = to_virtio_gpu_plane_state(state);\n\tif (vgplane_st->fence) {',
             '\tvgplane_st = to_virtio_gpu_plane_state(state);\n'
             '\tdma_fence_put(vgplane_st->mpc_producer_fence);\n'
             '\tvgplane_st->mpc_producer_fence = NULL;\n\tif (vgplane_st->fence) {')
    texts['virtgpu_plane.c'] = p
    return texts


def patch(root, receipt_dir):
    directory = root / 'drivers/gpu/drm/virtio'
    original = {name: (directory / name).read_text(encoding='utf-8') for name in FILES}
    for name in FILES:
        if hashlib.sha256(original[name].encode()).hexdigest() != UPSTREAM_FILES[name]:
            raise ValueError('Unexpected upstream bytes: ' + name)
    changed = transform(original)
    receipt_dir.mkdir(parents=True, exist_ok=False)
    diff = ''.join(''.join(difflib.unified_diff(original[n].splitlines(True), changed[n].splitlines(True),
                   fromfile='a/drivers/gpu/drm/virtio/' + n, tofile='b/drivers/gpu/drm/virtio/' + n)) for n in FILES)
    (receipt_dir / 'linux-display-completion.patch').write_text(diff, encoding='utf-8', newline='\n')
    receipt = dict(schema=1, scope='linux-exact-display-response-completion-source',
                   upstream='Linux 6.12.111', opt_in='virtio_gpu.mpc_native_display_fences=1',
                   metal_dependency_verified=False, files={n: dict(
                       before_sha256=hashlib.sha256(original[n].encode()).hexdigest(),
                       after_sha256=hashlib.sha256(changed[n].encode()).hexdigest()) for n in FILES})
    for name in FILES:
        (directory / name).write_text(changed[name], encoding='utf-8', newline='\n')
    (receipt_dir / 'patch-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=pathlib.Path)
    parser.add_argument('receipt', type=pathlib.Path)
    args = parser.parse_args()
    patch(args.kernel, args.receipt)
