#!/bin/sh
set -eu
export XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=Openbox
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
echo MYPC_DESKTOP_STARTUP=session >/dev/ttyAMA0
if [ -d /sys/block/vda/mq ]; then
    set -- /sys/block/vda/mq/*
    echo "MYPC_GUEST_DISK_QUEUES=$#" >/dev/ttyAMA0
fi
xset s off -dpms
echo MYPC_DESKTOP_STARTUP=screen-settings >/dev/ttyAMA0
xsetroot -solid '#162334'
openbox &
echo MYPC_DESKTOP_STARTUP=window-manager >/dev/ttyAMA0
if grep -qw my_pc_hardware_ci=1 /proc/cmdline; then export MYPC_HARDWARE_CI=1; fi
if [ -f /usr/local/lib/my-pc/hardware-tests/hardware-control.py ]; then
    # Same unprivileged user and X11 environment as Steam. The private port
    # carries fixed diagnostic commands; it never interprets a shell command.
    python3 -u /usr/local/lib/my-pc/hardware-tests/hardware-control.py </dev/null >/dev/null 2>&1 &
fi
if [ -f /usr/local/lib/my-pc/hardware-tests/hardware-keys.py ]; then
    python3 -u /usr/local/lib/my-pc/hardware-tests/hardware-keys.py >/dev/ttyAMA0 2>&1 &
fi
# Query the actual guest GL driver and render/read back one pixel. Report
# only hardware diagnostics: no Steam account, URLs, or process arguments.
echo MYPC_DESKTOP_STARTUP=graphics-probe >/dev/ttyAMA0
timeout 20s python3 -u - <<'PY' >/dev/ttyAMA0 2>&1 || echo MYPC_GUEST_GRAPHICS_UNAVAILABLE >/dev/ttyAMA0
import ctypes as c
import json
state = {'schema': 1, 'renderer': '', 'readback_ok': False, 'accelerated': False}
display = surface = context = None
stage = 'libraries'
try:
    egl, gl = c.CDLL('libEGL.so.1'), c.CDLL('libGL.so.1')
    pointer, integer, uint = c.c_void_p, c.c_int, c.c_uint
    ints = c.POINTER(integer)
    def bind(lib, name, result, *arguments):
        function = getattr(lib, name); function.restype = result; function.argtypes = arguments
        return function
    get_display = bind(egl, 'eglGetDisplay', pointer, pointer)
    initialize = bind(egl, 'eglInitialize', uint, pointer, ints, ints)
    bind_api = bind(egl, 'eglBindAPI', uint, uint)
    choose = bind(egl, 'eglChooseConfig', uint, pointer, ints, c.POINTER(pointer), integer, ints)
    create_surface = bind(egl, 'eglCreatePbufferSurface', pointer, pointer, pointer, ints)
    create_context = bind(egl, 'eglCreateContext', pointer, pointer, pointer, pointer, ints)
    make_current = bind(egl, 'eglMakeCurrent', uint, pointer, pointer, pointer, pointer)
    get_string = bind(gl, 'glGetString', c.c_char_p, uint)
    clear_color = bind(gl, 'glClearColor', None, c.c_float, c.c_float, c.c_float, c.c_float)
    clear = bind(gl, 'glClear', None, uint)
    read_pixel = bind(gl, 'glReadPixels', None, integer, integer, integer, integer, uint, uint, pointer)
    get_error = bind(gl, 'glGetError', uint)
    stage = 'display'; display = get_display(None)
    assert display and initialize(display, None, None)
    stage = 'config'; assert bind_api(0x30A2)  # EGL_OPENGL_API
    attributes = (integer * 11)(0x3033, 1, 0x3040, 8, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3038)
    config, count = pointer(), integer()
    assert choose(display, attributes, c.byref(config), 1, c.byref(count)) and count.value == 1
    stage = 'context'
    surface = create_surface(display, config, (integer * 5)(0x3057, 1, 0x3056, 1, 0x3038))
    context = create_context(display, config, None, (integer * 1)(0x3038))
    assert surface and context and make_current(display, surface, surface, context)
    state['renderer'] = (get_string(0x1F01) or b'').decode('utf-8', errors='replace')[:256]
    stage = 'readback'
    clear_color(1, 0, 0, 1); clear(0x4000)
    pixel = (c.c_ubyte * 4)()
    read_pixel(0, 0, 1, 1, 0x1908, 0x1401, pixel)
    state['readback_ok'] = get_error() == 0 and list(pixel) == [255, 0, 0, 255]
    renderer = state['renderer'].lower()
    state['accelerated'] = state['readback_ok'] and 'virgl' in renderer and not any(word in renderer for word in ('llvmpipe', 'softpipe', 'swiftshader', 'software'))
except Exception:
    state['error'] = stage
finally:
    if display:
        try:
            make_current(display, None, None, None)
            if context: bind(egl, 'eglDestroyContext', uint, pointer, pointer)(display, context)
            if surface: bind(egl, 'eglDestroySurface', uint, pointer, pointer)(display, surface)
            bind(egl, 'eglTerminate', uint, pointer)(display)
        except Exception: pass
print('MYPC_GUEST_GRAPHICS ' + json.dumps(state), flush=True)
PY
echo MYPC_DESKTOP_STARTUP=graphics-finished >/dev/ttyAMA0
if grep -qw my_pc_hardware_ci=1 /proc/cmdline; then
    echo MYPC_DESKTOP_STARTUP=hardware-ci >/dev/ttyAMA0
    exec python3 -u /usr/local/lib/my-pc/hardware-tests/hardware-test-ci.py >/dev/ttyAMA0 2>&1
fi
if grep -qw my_pc_desktop_test=1 /proc/cmdline; then
    exec python3 /usr/local/lib/my-pc/desktop-test.py
fi
pulseaudio --start --exit-idle-time=-1 || true
if grep -qw my_pc_steam_test=1 /proc/cmdline; then
    exec python3 -u /usr/local/lib/my-pc/probe-steam.py "$HOME/steam-probe" --guest --install-timeout 1800 --timeout 600 >/dev/ttyAMA0 2>&1
fi
while :; do
    xterm -T 'Steam ARM64' -fa 'DejaVu Sans Mono' -fs 11 -geometry 100x28+20+20 \
        -e sh -c '/usr/local/bin/my-pc-steam; echo "Steam closed. Press Enter to reopen."; read answer'
    sleep 1
done
