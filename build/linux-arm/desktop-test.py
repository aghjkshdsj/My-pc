#!/usr/bin/env python3
"""Guest-side X11 test: require actual QMP mouse AND keyboard events."""
from Xlib import X, XK, display

console = open('/dev/ttyAMA0', 'w', buffering=1)
connection = display.Display()
screen = connection.screen()
window = screen.root.create_window(0, 0, screen.width_in_pixels, screen.height_in_pixels,
                                  0, screen.root_depth, X.InputOutput, X.CopyFromParent,
                                  background_pixel=screen.white_pixel, override_redirect=True,
                                  event_mask=X.ExposureMask | X.ButtonPressMask | X.KeyPressMask)
window.map()
window.set_input_focus(X.RevertToParent, X.CurrentTime)
connection.sync()
print('MYPC_DESKTOP_READY', file=console)
mouse = keyboard = False
typed = ''
while not (mouse and keyboard):
    event = connection.next_event()
    if event.type == X.ButtonPress:
        mouse = True
        print('MYPC_DESKTOP_MOUSE_OK', file=console)
    elif event.type == X.KeyPress:
        symbol = connection.keycode_to_keysym(event.detail, 1 if event.state & X.ShiftMask else 0)
        if symbol == XK.XK_Return:
            if typed != 'Steam 123!':
                raise RuntimeError(f'Guest received unexpected keyboard text: {typed!r}')
            keyboard = True
            print('MYPC_DESKTOP_KEYBOARD_OK', file=console)
        elif 32 <= symbol < 127:
            typed += chr(symbol)
print('MYPC_DESKTOP_INPUT_OK', file=console)
# Keep X alive until the system service completes the boot checks and powers off.
while True:
    connection.next_event()
