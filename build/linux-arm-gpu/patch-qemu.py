#!/usr/bin/env python3
"""Enable UTM's ANGLE initialization in its existing EGL readback backend."""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
path = root / 'ui/meson.build'
source = path.read_text()
anchor = 'egl_headless_ss.add(when: [egl, opengl, gbm, pixman],'
assert source.count(anchor) == 1, 'egl-headless Meson anchor changed'
path.write_text(source.replace(anchor, 'egl_headless_ss.add(when: [egl, opengl, pixman],'))
path = root / 'ui/egl-helpers.c'
source = path.read_text()
start = source.index('bool egl_init(')
prefix, body = source[:start], source[start:]
anchor = '#elif defined(CONFIG_GBM)'
assert body.count(anchor) == 1, 'egl_init platform anchor changed'
body = body.replace(anchor, r'''#elif defined(__APPLE__)
    if (qemu_egl_init_dpy_cocoa(DISPLAY_GL_MODE_ES) < 0) {
        error_setg(errp, "egl: ANGLE Metal display initialization failed");
        return false;
    }
    qemu_egl_rn_ctx = qemu_egl_init_ctx();
    if (qemu_egl_rn_ctx) {
        fprintf(stderr, "MYPC_HOST_GL_RENDERER=%s\n", glGetString(GL_RENDERER));
        fprintf(stderr, "MYPC_HOST_GL_VERSION=%s\n", glGetString(GL_VERSION));
    }
#elif defined(CONFIG_GBM)''')
path.write_text(prefix + body)
