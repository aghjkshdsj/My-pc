#!/usr/bin/env python3
"""Compile the actual patched presentation functions against deterministic GL.

No GPU claim comes from these stubs: the separate Apple guest gate proves that.
This test verifies coalescing, final-frame delivery and GL context restoration.
"""
import pathlib
import re
import subprocess
import sys
import tempfile


def function(source, name):
    match = re.search(r'static void ' + name + r'\([^;]*?\)\n\{', source)
    assert match, name
    start, end, depth = match.start(), match.end(), 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


source = pathlib.Path(sys.argv[1], 'ui/egl-headless.c').read_text()
state = source[source.index('typedef struct egl_dpy {'):source.index('} egl_dpy;') + len('} egl_dpy;')]
code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
typedef int EGLContext;
typedef int EGLSurface;
typedef long long gint64;
typedef struct { int *con; } DisplayChangeListener;
typedef struct { int width, height; } DisplaySurface;
typedef void QemuGLShader;
typedef struct { int texture; } egl_fb;
#define EGL_NO_CONTEXT 0
#define EGL_NO_SURFACE 0
#define EGL_DRAW 1
#define EGL_READ 2
#define PIXMAN_x8r8g8b8 1
#define container_of(p, type, field) ((type *)((char *)(p) - offsetof(type, field)))
static int qemu_egl_display, current = 2, reads, updates, fail_current;
static gint64 clock_us;
static int eglGetCurrentContext(void) { return current; }
static int eglGetCurrentSurface(int which) { return 10 + which; }
static bool eglMakeCurrent(int d, int draw, int read, int ctx) {
    if (fail_current) return false;
    current = ctx; return true;
}
static void graphic_hw_update(int *con) {}
static int surface_format(DisplaySurface *s) { return PIXMAN_x8r8g8b8; }
static int surface_width(DisplaySurface *s) { return s->width; }
static int surface_height(DisplaySurface *s) { return s->height; }
static void egl_fb_destroy(egl_fb *f) { f->texture = 0; }
static void egl_fb_blit(egl_fb *d, egl_fb *s, bool flip) { assert(current == 1); }
static void egl_texture_blit(QemuGLShader *g, egl_fb *d, egl_fb *s, bool flip) {}
static void egl_texture_blend(QemuGLShader *g, egl_fb *d, egl_fb *s,
                              bool flip, int x, int y, double a, double b) {}
static void egl_fb_read(DisplaySurface *s, egl_fb *f) { reads++; assert(current == 1); }
static void dpy_gfx_update(int *con, int x, int y, int w, int h) {
    updates++; assert(x == 0 && y == 0 && w == 1280 && h == 800);
}
static gint64 g_get_monotonic_time(void) { return ++clock_us; }
'''
code += state + '\nstatic void my_pc_egl_present(egl_dpy *edpy);\n'
for name in ('egl_refresh', 'egl_scanout_disable', 'egl_scanout_flush', 'my_pc_egl_present'):
    code += function(source, name) + '\n'
code += r'''
int main(void) {
    DisplaySurface surface = {1280, 800};
    egl_dpy display = { .ds = &surface, .guest_fb = {1}, .scanout_ctx = 1 };
    for (int i = 0; i < 1000; i++) egl_scanout_flush(&display.dcl, i, 2, 1, 1);
    assert(reads == 0 && updates == 0 && display.pending_update);
    egl_refresh(&display.dcl);
    assert(reads == 1 && updates == 1 && current == 2 && !display.pending_update);
    egl_refresh(&display.dcl);
    assert(reads == 1 && updates == 1);
    /* The final update is delivered even when no later guest flush arrives. */
    egl_scanout_flush(&display.dcl, 4, 5, 2, 2);
    fail_current = 1; egl_refresh(&display.dcl);
    assert(reads == 1 && display.pending_update);
    fail_current = 0; egl_refresh(&display.dcl);
    assert(reads == 2 && updates == 2 && current == 2 && !display.pending_update);
    egl_scanout_flush(&display.dcl, 0, 0, 1, 1);
    egl_scanout_disable(&display.dcl); egl_refresh(&display.dcl);
    assert(reads == 2 && !display.pending_update && !display.scanout_ctx);
    assert(display.flush_requests == 1002 && display.readbacks == 2);
    puts("PASS: 1,000 flushes become one readback; final frame, retry and context restoration");
}
'''
with tempfile.TemporaryDirectory() as temporary:
    file = pathlib.Path(temporary, 'presentation.c'); file.write_text(code)
    binary = pathlib.Path(temporary, 'presentation')
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', str(file), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
