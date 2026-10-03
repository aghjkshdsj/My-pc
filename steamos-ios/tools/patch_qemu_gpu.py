#!/usr/bin/env python3
"""Narrow Darwin ANGLE Metal headless diagnostic adapter; no app source reuse."""
import argparse
import difflib
import hashlib
import json
import pathlib


def replace(text, old, new):
    assert text.count(old) == 1, 'Pinned QEMU graphics source changed'
    return text.replace(old, new)


def transform(name, text):
    if name == 'ui/meson.build':
        return replace(text, '  egl_headless_ss.add(when: [egl, opengl, gbm, pixman],',
                       "  headless_deps = host_os == 'darwin' ? [egl, opengl, pixman] : [egl, opengl, gbm, pixman]\n"
                       '  egl_headless_ss.add(when: headless_deps,')
    if name == 'ui/egl-helpers.c':
        # Request an ES3 root context for our virgl GLES diagnostics. Preserve
        # the upstream ES2 default on other hosts; require ES3 for this path.
        text = replace(text, '        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,',
                       '#ifdef __APPLE__\n'
                       '        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT_KHR,\n'
                       '#else\n'
                       '        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,\n'
                       '#endif')
        text = replace(text, '        EGL_CONTEXT_CLIENT_VERSION, 2,',
                       '#ifdef __APPLE__\n'
                       '        EGL_CONTEXT_CLIENT_VERSION, 3,\n'
                       '#else\n'
                       '        EGL_CONTEXT_CLIENT_VERSION, 2,\n'
                       '#endif')
        text = replace(text, 'int qemu_egl_init_dpy_cocoa(DisplayGLMode mode)\n{\n'
                            '    EGLDisplay dpy = eglGetDisplay(EGL_DEFAULT_DISPLAY);',
                       'int qemu_egl_init_dpy_cocoa(DisplayGLMode mode)\n{\n'
                       '    const EGLint attributes[] = {\n'
                       '        EGL_PLATFORM_ANGLE_TYPE_ANGLE, EGL_PLATFORM_ANGLE_TYPE_METAL_ANGLE,\n'
                       '        EGL_NONE\n'
                       '    };\n'
                       '    if (mode == DISPLAY_GL_MODE_ON) {\n'
                       '        mode = DISPLAY_GL_MODE_ES;\n'
                       '    }\n'
                       '    if (mode != DISPLAY_GL_MODE_ES) {\n'
                       '        error_report("MPC ANGLE Metal diagnostic requires GLES mode");\n'
                       '        return -1;\n'
                       '    }\n'
                       '    EGLDisplay dpy = eglGetPlatformDisplayEXT(EGL_PLATFORM_ANGLE_ANGLE,\n'
                       '                                               EGL_DEFAULT_DISPLAY, attributes);')
        text = replace(text, '#elif defined(CONFIG_GBM)\n    if (egl_rendernode_init(rendernode, mode) < 0)',
                       '#elif defined(__APPLE__)\n'
                       '    if (qemu_egl_init_dpy_cocoa(mode) < 0) {\n'
                       '        error_setg(errp, "MPC ANGLE Metal context initialization failed");\n'
                       '        return false;\n'
                       '    }\n'
                       '    qemu_egl_rn_ctx = qemu_egl_init_ctx();\n'
                       '    if (!qemu_egl_rn_ctx) {\n'
                       '        error_setg(errp, "MPC ANGLE Metal root context creation failed");\n'
                       '        return false;\n'
                       '    }\n'
                       '#elif defined(CONFIG_GBM)\n    if (egl_rendernode_init(rendernode, mode) < 0)')
        return text
    if name == 'hw/display/virtio-gpu-virgl.c':
        assert 'MPC: keep ANGLE renderer contexts in GLES mode' not in text
        return replace(text, '    uint32_t flags = 0;\n    VirtIOGPUGL *gl = VIRTIO_GPU_GL(g);',
                       '    uint32_t flags = 0;\n    VirtIOGPUGL *gl = VIRTIO_GPU_GL(g);\n'
                       '    /* MPC: keep ANGLE renderer contexts in GLES mode. */\n'
                       '    if (qemu_egl_mode == DISPLAY_GL_MODE_ES) {\n'
                       '        flags |= VIRGL_RENDERER_USE_GLES;\n'
                       '    }')
    if name == 'ui/egl-headless.c':
        # Native preflight calls the real built-in backend registration before
        # qemu_init can take its process-fatal unavailable-display path. The
        # normal upstream QOM initializer remains; repeating pointer registration
        # is idempotent. This does not initialize EGL/Metal or claim a draw.
        return replace(text, 'type_init(register_egl);',
                       'int mpc_qemu_register_egl_headless(void)\n'
                       '{\n'
                       '    register_egl();\n'
                       '    return 1;\n'
                       '}\n\n'
                       'type_init(register_egl);')
    raise AssertionError(name)


def patch(source, output):
    patches = []
    files = {}
    for name in ['ui/meson.build', 'ui/egl-helpers.c', 'hw/display/virtio-gpu-virgl.c', 'ui/egl-headless.c']:
        path = source / name
        original = path.read_text(encoding='utf-8')
        changed = transform(name, original)
        path.write_text(changed, encoding='utf-8')
        files[name] = {'original_sha256': hashlib.sha256(original.encode()).hexdigest(),
                       'patched_sha256': hashlib.sha256(changed.encode()).hexdigest()}
        patches.extend(difflib.unified_diff(original.splitlines(keepends=True), changed.splitlines(keepends=True),
                                           fromfile='a/' + name, tofile='b/' + name))
    (output / 'qemu-angle-metal-diagnostic.patch').write_text(''.join(patches), encoding='utf-8')
    receipt = {'schema': 1, 'scope': 'darwin-qemu-angle-metal-headless-diagnostic-adapter-source',
               'files': files, 'metal_backend_explicitly_requested': True,
               'root_gles_version_requested': 3,
               'builtin_headless_registration_preflight': True,
               'steady_state_presenter': False, 'phone_tested': False,
               'guest_graphics_verified': False, 'presentation_verified': False}
    (output / 'gpu-adapter-source.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    patch(args.source, args.output)
