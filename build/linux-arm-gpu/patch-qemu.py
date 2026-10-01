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

# egl-headless normally reads a full frame for EVERY virtio RESOURCE_FLUSH,
# including small rectangles. The app consumes at most 30 frames/sec. Defer
# presentation to that cadence, so GPU stalls do not multiply inside the BQL.
path = root / 'ui/egl-headless.c'
source = path.read_text()
anchor = '    bool y_0_top;\n'
assert source.count(anchor) == 1, 'Headless display state anchor changed'
source = source.replace(anchor, '''    bool y_0_top;
    bool pending_update;
    EGLContext scanout_ctx;
    uint64_t flush_requests, readbacks, readback_us;
    gint64 stats_time;
''')
anchor = '''static void egl_refresh(DisplayChangeListener *dcl)
{
    graphic_hw_update(dcl->con);
}'''
assert source.count(anchor) == 1, 'Headless refresh anchor changed'
source = source.replace(anchor, '''static void my_pc_egl_present(egl_dpy *edpy);

static void egl_refresh(DisplayChangeListener *dcl)
{
    egl_dpy *edpy = container_of(dcl, egl_dpy, dcl);
    graphic_hw_update(dcl->con);
    if (edpy->pending_update) {
        my_pc_egl_present(edpy);
    }
}''')
anchor = '    egl_fb_destroy(&edpy->guest_fb);\n'
assert source.count(anchor) == 1, 'Headless scanout disable anchor changed'
source = source.replace(anchor, '''    edpy->pending_update = false;
    edpy->scanout_ctx = EGL_NO_CONTEXT;
    egl_fb_destroy(&edpy->guest_fb);
''')
anchor = '    edpy->y_0_top = backing_y_0_top;\n'
assert source.count(anchor) == 1, 'Headless scanout texture anchor changed'
source = source.replace(anchor, '''    edpy->y_0_top = backing_y_0_top;
    /* Upstream virgl explicitly selects context 0 before this callback.
     * FBOs are context-local; retain it rather than borrowing a guest context. */
    edpy->scanout_ctx = eglGetCurrentContext();
    edpy->pending_update = true;
''')
anchor = '''    if (!edpy->guest_fb.texture || !edpy->ds) {
        return;
    }
    assert(surface_format(edpy->ds) == PIXMAN_x8r8g8b8);'''
assert source.count(anchor) == 1, 'Headless flush anchor changed'
source = source.replace(anchor, '''    if (edpy->guest_fb.texture && edpy->ds) {
        edpy->flush_requests++;
        edpy->pending_update = true;
    }
}

static void my_pc_egl_present(egl_dpy *edpy)
{
    if (!edpy->guest_fb.texture || !edpy->ds ||
        edpy->scanout_ctx == EGL_NO_CONTEXT) {
        return;
    }
    EGLContext previous = eglGetCurrentContext();
    EGLSurface draw = eglGetCurrentSurface(EGL_DRAW);
    EGLSurface read = eglGetCurrentSurface(EGL_READ);
    if (!eglMakeCurrent(qemu_egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE,
                        edpy->scanout_ctx)) {
        return;
    }
    edpy->pending_update = false;
    gint64 started = g_get_monotonic_time();
    assert(surface_format(edpy->ds) == PIXMAN_x8r8g8b8);''')
anchor = '    dpy_gfx_update(edpy->dcl.con, x, y, w, h);\n'
assert source.count(anchor) == 1, 'Headless presentation anchor changed'
source = source.replace(anchor, '''    edpy->readbacks++;
    edpy->readback_us += g_get_monotonic_time() - started;
    /* A full readback replaces all pixels, including the final dirty rectangle.
     * Never publish only the rectangle of an earlier, coalesced flush. */
    dpy_gfx_update(edpy->dcl.con, 0, 0, surface_width(edpy->ds), surface_height(edpy->ds));
    eglMakeCurrent(qemu_egl_display, draw, read, previous);
    gint64 now = g_get_monotonic_time();
    if (now - edpy->stats_time >= 5000000) {
        fprintf(stderr, "MYPC_GPU_PRESENT flushes=%llu readbacks=%llu readback_us=%llu\\n",
                (unsigned long long)edpy->flush_requests,
                (unsigned long long)edpy->readbacks,
                (unsigned long long)edpy->readback_us);
        edpy->stats_time = now;
    }
''')
anchor = '        register_displaychangelistener(&edpy->dcl);\n'
assert source.count(anchor) == 1, 'Headless listener registration anchor changed'
source = source.replace(anchor, anchor + '        update_displaychangelistener(&edpy->dcl, 33);\n')
path.write_text(source)
