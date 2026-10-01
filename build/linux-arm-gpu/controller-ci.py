#!/usr/bin/env python3
"""Observe actual kernel gamepad events as Steam's user in an account-free VM."""
import fcntl
import os
import pathlib
import struct
import subprocess
import time


def node():
    for path in pathlib.Path('/sys/class/input').glob('event*/device/name'):
        try:
            if path.read_text().strip() == 'My-pc iOS Gamepad 1':
                candidate = pathlib.Path('/dev/input', path.parents[1].name)
                if candidate.exists() and os.access(candidate,os.R_OK): return candidate
        except OSError: continue
    return None


def wait(predicate, limit=40):
    deadline = time.monotonic()+limit
    while time.monotonic() < deadline:
        value = predicate()
        if value: return value
        time.sleep(0.03)
    raise RuntimeError('Controller observation timed out')


def run():
    device = wait(node)
    assert os.access(device, os.R_OK), 'Steam user must have gamepad access'
    def classified():
        try:
            properties = subprocess.check_output(['udevadm','info','--query=property','--name',str(device)],text=True,timeout=5)
            return 'ID_INPUT_JOYSTICK=1' in properties
        except (OSError,subprocess.SubprocessError): return False
    wait(classified,10)
    fd = os.open(device, os.O_RDONLY|os.O_NONBLOCK)
    # The host keeps a connected neutral pad during boot. Only exercise
    # buttons/hotplug once this observer owns the classified event device.
    print('MYPC_CONTROLLER_OBSERVER_READY=1',flush=True)
    def state():
        keys = bytearray(128)
        fcntl.ioctl(fd, 0x80000000 | len(keys)<<16 | ord('E')<<8 | 0x18, keys, True)
        pressed = [code for code in (0x130,0x131,0x133,0x134,0x136,0x137,0x13a,0x13b,0x13c,0x13d,0x13e)
                   if keys[code//8] & 1 << (code%8)]
        values = []
        for code in (0,1,3,4,2,5,16,17):
            buffer = bytearray(24)
            fcntl.ioctl(fd, 0x80000000 | 24<<16 | ord('E')<<8 | (0x40+code), buffer, True)
            values.append(struct.unpack('<6i',buffer)[0])
        try: os.read(fd,4096)
        except BlockingIOError: pass
        return pressed,values
    try:
        expected = [-16000,14000,12000,-8000,8192,24576,1,-1]
        wait(lambda: len(state()[0])==11 and state()[1]==expected)
        wait(lambda: state()==([],[0]*8))
        wait(lambda: not device.exists())
        reopened = wait(node)
        assert os.access(reopened,os.R_OK)
    finally: os.close(fd)
    print('MYPC_CONTROLLER_EVDEV_ANALOG_BUTTONS_HOTPLUG_OK=1',flush=True)


if __name__=='__main__': run()
