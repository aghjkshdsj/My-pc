#!/usr/bin/env python3
"""Run inside the isolated Linux GPU test guest; never sign in to Steam."""
import ctypes as c
import json
import os
import subprocess
import time

os.environ.pop('LIBGL_ALWAYS_SOFTWARE', None)
os.environ.pop('GALLIUM_DRIVER', None)
egl = c.CDLL('libEGL.so.1')
gl = c.CDLL('libGLESv2.so.2')


def bind(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


pointer = c.c_void_p
integer = c.c_int
uint = c.c_uint
ints = c.POINTER(integer)
get_display = bind(egl, 'eglGetDisplay', pointer, pointer)
initialize = bind(egl, 'eglInitialize', uint, pointer, ints, ints)
bind_api = bind(egl, 'eglBindAPI', uint, uint)
choose_config = bind(egl, 'eglChooseConfig', uint, pointer, ints, c.POINTER(pointer), integer, ints)
create_surface = bind(egl, 'eglCreatePbufferSurface', pointer, pointer, pointer, ints)
create_context = bind(egl, 'eglCreateContext', pointer, pointer, pointer, pointer, ints)
make_current = bind(egl, 'eglMakeCurrent', uint, pointer, pointer, pointer, pointer)
destroy_surface = bind(egl, 'eglDestroySurface', uint, pointer, pointer)
destroy_context = bind(egl, 'eglDestroyContext', uint, pointer, pointer)
terminate = bind(egl, 'eglTerminate', uint, pointer)
get_string = bind(gl, 'glGetString', c.c_char_p, uint)
create_shader = bind(gl, 'glCreateShader', uint, uint)
shader_source = bind(gl, 'glShaderSource', None, uint, integer, c.POINTER(c.c_char_p), ints)
compile_shader = bind(gl, 'glCompileShader', None, uint)
shader_iv = bind(gl, 'glGetShaderiv', None, uint, uint, ints)
delete_shader = bind(gl, 'glDeleteShader', None, uint)
create_program = bind(gl, 'glCreateProgram', uint)
attach_shader = bind(gl, 'glAttachShader', None, uint, uint)
link_program = bind(gl, 'glLinkProgram', None, uint)
program_iv = bind(gl, 'glGetProgramiv', None, uint, uint, ints)
use_program = bind(gl, 'glUseProgram', None, uint)
delete_program = bind(gl, 'glDeleteProgram', None, uint)
viewport = bind(gl, 'glViewport', None, integer, integer, integer, integer)
clear_color = bind(gl, 'glClearColor', None, c.c_float, c.c_float, c.c_float, c.c_float)
clear = bind(gl, 'glClear', None, uint)
draw = bind(gl, 'glDrawArrays', None, uint, integer, integer)
read_pixels = bind(gl, 'glReadPixels', None, integer, integer, integer, integer, uint, uint, pointer)
get_error = bind(gl, 'glGetError', uint)


def shader(kind, text):
    handle = create_shader(kind)
    source = c.c_char_p(text)
    shader_source(handle, 1, c.byref(source), None)
    compile_shader(handle)
    okay = integer()
    shader_iv(handle, 0x8B81, c.byref(okay))  # GL_COMPILE_STATUS
    assert okay.value, 'GPU shader compilation failed'
    return handle


display = get_display(None)
assert display, 'Guest has no EGL display'
assert initialize(display, None, None), 'Guest EGL initialization failed'
surface = context = None
try:
    assert bind_api(0x30A0), 'Guest GLES API unavailable'
    # EGL_PBUFFER_BIT, EGL_OPENGL_ES3_BIT, RGBA8.
    attributes = (integer * 13)(0x3033, 1, 0x3040, 0x40, 0x3024, 8,
                               0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038)
    config, count = pointer(), integer()
    assert choose_config(display, attributes, c.byref(config), 1, c.byref(count)) and count.value == 1
    surface = create_surface(display, config, (integer * 5)(0x3057, 16, 0x3056, 16, 0x3038))
    context = create_context(display, config, None, (integer * 3)(0x3098, 3, 0x3038))
    assert surface and context, 'Guest GLES 3 context unavailable'
    assert make_current(display, surface, surface, context), 'Guest GLES context activation failed'
    renderer = (get_string(0x1F01) or b'').decode('utf-8', errors='replace')[:256]
    version = (get_string(0x1F02) or b'').decode('utf-8', errors='replace')[:128]
    print('MYPC_GUEST_GPU_INFO ' + json.dumps({'renderer': renderer, 'version': version}), flush=True)
    assert 'virgl' in renderer.lower(), 'Guest renderer is not virgl'
    assert not any(word in renderer.lower() for word in ('llvmpipe', 'softpipe', 'swiftshader', 'software'))
    vertex = shader(0x8B31, b'''#version 300 es
    void main() {
        vec2 positions[3] = vec2[3](vec2(-1.0,-1.0), vec2(3.0,-1.0), vec2(-1.0,3.0));
        gl_Position = vec4(positions[gl_VertexID], 0.0, 1.0);
    }''')
    fragment = shader(0x8B30, b'''#version 300 es
    precision highp float;
    out vec4 color;
    void main() { color = vec4(1.0, 0.0, 0.0, 1.0); }''')
    program = create_program()
    attach_shader(program, vertex); attach_shader(program, fragment)
    link_program(program)
    okay = integer()
    program_iv(program, 0x8B82, c.byref(okay))  # GL_LINK_STATUS
    assert okay.value, 'GPU program linking failed'
    viewport(0, 0, 16, 16)
    clear_color(0, 0, 1, 1); clear(0x4000)
    pixel = (c.c_ubyte * 4)()
    read_pixels(8, 8, 1, 1, 0x1908, 0x1401, pixel)
    assert list(pixel) == [0, 0, 255, 255], 'GPU clear/readback mismatch'
    use_program(program); draw(0x0004, 0, 3)
    read_pixels(8, 8, 1, 1, 0x1908, 0x1401, pixel)
    assert get_error() == 0 and list(pixel) == [255, 0, 0, 255], 'GPU shader/readback mismatch'
    delete_program(program); delete_shader(vertex); delete_shader(fragment)
    print('MYPC_GUEST_GPU_SHADER_OK', flush=True)
    # The host exposes GLES through ANGLE. A legacy GLX compatibility demo can
    # fail even when the GLES shader passed; exercise an actual GLES window.
    animation = subprocess.Popen(['es2gears_x11'])
    print('MYPC_GUEST_GPU_ANIMATION_STARTED', flush=True)
    # Keep X11 alive so the host can capture the desktop through its existing
    # readback listener, then power down through the app's QMP power button.
    while True:
        assert animation.poll() is None, 'Guest GLES animation exited before host readback'
        time.sleep(1)
finally:
    make_current(display, None, None, None)
    if context: destroy_context(display, context)
    if surface: destroy_surface(display, surface)
    terminate(display)
