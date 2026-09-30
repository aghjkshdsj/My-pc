#!/usr/bin/env python3
"""Fixed local keyboard shortcuts for diagnostics; no network listener."""
import json
import os
import pathlib
import signal
import subprocess
from Xlib import X, XK, display

folder = pathlib.Path(__file__).resolve().parent
connection = display.Display()
root = connection.screen().root
codes = {connection.keysym_to_keycode(XK.string_to_keysym(name)): kind
         for name,kind in [('F8','cpu'),('F9','gpu'),('F10','cancel')]}
modifiers = X.ControlMask | X.ShiftMask
for code in codes:
    for extra in (0, X.LockMask, X.Mod2Mask, X.LockMask|X.Mod2Mask):
        root.grab_key(code, modifiers|extra, False, X.GrabModeAsync, X.GrabModeAsync)
connection.sync()
print('MYPC_HARDWARE_TEST_READY=1', flush=True)
active = None
while True:
    event = connection.next_event()
    if event.type != X.KeyPress or event.detail not in codes: continue
    kind = codes[event.detail]
    if kind == 'cancel':
        if active and active.poll() is None:
            # xterm's foreground child has its own process group. Signal only
            # our named test runner, never Steam or other users' processes.
            for pid in pathlib.Path('/proc').iterdir():
                if not pid.name.isdecimal(): continue
                try:
                    argv = (pid/'cmdline').read_bytes().split(b'\0')
                    script = str(folder/'hardware-test.py').encode()
                    index = argv.index(script) if script in argv else -1
                    if index >= 1 and len(argv)>index+1 and argv[index+1] in (b'cpu',b'gpu'):
                        os.kill(int(pid.name), signal.SIGTERM)
                except (OSError,ValueError): pass
        continue
    if active and active.poll() is None: continue
    active = subprocess.Popen(['xterm','-T','My-pc hardware test','-fa','DejaVu Sans Mono','-fs','11',
                               '-geometry','110x30+20+20','-e','python3','-u',str(folder/'hardware-test.py'),kind])
