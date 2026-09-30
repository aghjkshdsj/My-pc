#!/usr/bin/env python3
"""Fixed local keyboard shortcuts for diagnostics; no network listener."""
import os
import pathlib
import signal
import subprocess

folder = pathlib.Path(__file__).resolve().parent


def cancel_runner(xterm_pid, proc=pathlib.Path('/proc')):
    # Inspect only descendants of the xterm we launched, rather than walking
    # every Steam process. A fixed runner path remains required before signal.
    pending = [int(xterm_pid)]; visited = set()
    while pending and len(visited) < 24:
        pid = pending.pop()
        if pid in visited: continue
        visited.add(pid)
        try:
            with (proc/str(pid)/'cmdline').open('rb') as stream: argv = stream.read(4096).split(b'\0')
            script = str(folder/'hardware-test.py').encode()
            index = argv.index(script) if script in argv else -1
            if index >= 1 and len(argv)>index+1 and argv[index+1] in (b'cpu',b'gpu'):
                os.kill(pid,signal.SIGTERM)
                return True
            with (proc/str(pid)/'task'/str(pid)/'children').open('rb') as stream:
                pending.extend(int(value) for value in stream.read(4096).split() if value.isdigit())
        except (OSError,ValueError): pass
    return False


def main():
    from Xlib import X, XK, display
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
            if active and active.poll() is None: cancel_runner(active.pid)
            continue
        if active and active.poll() is None: continue
        active = subprocess.Popen(['xterm','-T','My-pc hardware test','-fa','DejaVu Sans Mono','-fs','11',
                                   '-geometry','110x30+20+20','-e','python3','-u',str(folder/'hardware-test.py'),kind])


if __name__ == '__main__': main()
