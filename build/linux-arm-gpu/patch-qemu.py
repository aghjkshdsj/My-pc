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
anchor = '''int qemu_egl_init_dpy_cocoa(DisplayGLMode mode)
{
    EGLDisplay dpy = eglGetDisplay(EGL_DEFAULT_DISPLAY);'''
assert source.count(anchor) == 1, 'Cocoa EGL display anchor changed'
source = source.replace(anchor, '''int qemu_egl_init_dpy_cocoa(DisplayGLMode mode)
{
#ifdef __APPLE__
    /* EGL_DEFAULT_DISPLAY can silently select Apple's software OpenGL backend.
     * This experiment requires ANGLE's explicit Metal platform extension. */
    const EGLint attributes[] = {
        EGL_PLATFORM_ANGLE_TYPE_ANGLE, EGL_PLATFORM_ANGLE_TYPE_METAL_ANGLE,
        EGL_NONE
    };
    if (!epoxy_has_egl_extension(EGL_NO_DISPLAY, "EGL_EXT_platform_base") ||
        !epoxy_has_egl_extension(EGL_NO_DISPLAY, "EGL_ANGLE_platform_angle_metal")) {
        error_report("egl: ANGLE Metal platform extension unavailable");
        return -1;
    }
    EGLDisplay dpy = eglGetPlatformDisplayEXT(EGL_PLATFORM_ANGLE_ANGLE,
                                              EGL_DEFAULT_DISPLAY, attributes);
#else
    EGLDisplay dpy = eglGetDisplay(EGL_DEFAULT_DISPLAY);
#endif''')
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
