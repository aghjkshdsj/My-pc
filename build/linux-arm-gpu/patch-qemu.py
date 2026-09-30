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
source = prefix + body
anchor = '''    glTexImage2D(target, 0, GL_RGBA, width, height,
                 0, GL_BGRA, GL_UNSIGNED_BYTE, 0);'''
assert source.count(anchor) == 1, 'EGL readback texture allocation anchor changed'
source = source.replace(anchor, '''    /* GLES does not promise desktop GL's BGRA upload combinations. No data
     * is uploaded here; allocate a core RGBA texture for the Metal blit. */
    glTexImage2D(target, 0, GL_RGBA, width, height,
                0, qemu_egl_mode == DISPLAY_GL_MODE_ES ? GL_RGBA : GL_BGRA,
                GL_UNSIGNED_BYTE, 0);''')
anchor = '''    glReadPixels(0, 0, surface_width(dst), surface_height(dst),
                 GL_BGRA, GL_UNSIGNED_BYTE, surface_data(dst));'''
assert source.count(anchor) == 1, 'EGL full-frame readback anchor changed'
source = source.replace(anchor, r'''    if (qemu_egl_mode == DISPLAY_GL_MODE_ES) {
        /* RGBA/UNSIGNED_BYTE is a core GLES read format. Convert only at the
         * CPU display boundary, where the existing app requires BGRA. */
        static bool reported_ok, reported_error;
        GLenum before = glGetError();
        GLenum framebuffer = glCheckFramebufferStatus(GL_READ_FRAMEBUFFER);
        glPixelStorei(GL_PACK_ROW_LENGTH, surface_stride(dst) / 4);
        glReadPixels(0, 0, surface_width(dst), surface_height(dst),
                     GL_RGBA, GL_UNSIGNED_BYTE, surface_data(dst));
        glPixelStorei(GL_PACK_ROW_LENGTH, 0);
        GLenum after = glGetError();
        if (before || after || framebuffer != GL_FRAMEBUFFER_COMPLETE) {
            if (!reported_error) {
                fprintf(stderr, "MYPC_GPU_RGBA_READBACK_ERROR before=%u after=%u framebuffer=%u\n",
                        before, after, framebuffer);
                reported_error = true;
            }
            return;
        }
        for (int row = 0; row < surface_height(dst); row++) {
            uint8_t *pixels = surface_data(dst) + row * surface_stride(dst);
            for (int column = 0; column < surface_width(dst); column++) {
                uint8_t red = pixels[column * 4];
                pixels[column * 4] = pixels[column * 4 + 2];
                pixels[column * 4 + 2] = red;
            }
        }
        if (!reported_ok) {
            fprintf(stderr, "MYPC_GPU_RGBA_READBACK_OK\n");
            reported_ok = true;
        }
    } else {
        glReadPixels(0, 0, surface_width(dst), surface_height(dst),
                     GL_BGRA, GL_UNSIGNED_BYTE, surface_data(dst));
    }''')
path.write_text(source)
