#!/usr/bin/env python3
"""Local virtio-serial -> Linux uinput gamepads; never listens on a network.

The only accepted input is a fixed 32-byte MPG1 state with known buttons/axes.
The root service owns uinput; Steam receives only its normal event/js devices.
"""
import errno
import os
import pathlib
import select
import struct
import time

PACKET = struct.Struct('<4sBBHII6hI')
ACK = struct.Struct('<4sIII')
BUTTONS = {0x1000: 0x130, 0x2000: 0x131, 0x4000: 0x133, 0x8000: 0x134,
           0x100: 0x136, 0x200: 0x137, 0x20: 0x13a, 0x10: 0x13b,
           0x400: 0x13c, 0x40: 0x13d, 0x80: 0x13e}
AXES = (0, 1, 3, 4, 2, 5, 16, 17)


def decode(data):
    if len(data) != PACKET.size:
        return None
    magic, slot, connected, reserved, sequence, buttons, *tail = PACKET.unpack(data)
    axes, padding = tail[:6], tail[6]
    if (magic != b'MPG1' or slot > 3 or connected > 1 or reserved or padding
            or buttons & ~0xf7ff or any(v == -32768 for v in axes) or min(axes[4:]) < 0):
        return None
    if not connected and (buttons or any(axes)):
        return None
    return slot, bool(connected), sequence, buttons, axes


class Parser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        # Read chunks are bounded, and retain at most one incomplete packet.
        self.buffer.extend(data[:4096])
        states = []
        while len(self.buffer) >= PACKET.size:
            start = self.buffer.find(b'MPG1')
            if start < 0:
                del self.buffer[:-3]
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < PACKET.size:
                break
            state = decode(self.buffer[:PACKET.size])
            del self.buffer[:PACKET.size if state else 1]
            if state:
                states.append(state)
        return states


def events(buttons, axes):
    keys = [(1, code, int(bool(buttons & mask))) for mask, code in BUTTONS.items()]
    values = list(axes) + [int(bool(buttons & 8))-int(bool(buttons & 4)),
                           int(bool(buttons & 2))-int(bool(buttons & 1))]
    return keys + [(3, code, value) for code, value in zip(AXES, values)]


class UInput:
    def __init__(self, slot):
        import fcntl
        import pwd
        self.fcntl = fcntl
        self.fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        self.previous = {}
        try:
            def write_ioctl(number, size=4):
                return 0x40000000 | size << 16 | ord('U') << 8 | number
            for kind in (1, 3): fcntl.ioctl(self.fd, write_ioctl(100), kind)
            for code in BUTTONS.values(): fcntl.ioctl(self.fd, write_ioctl(101), code)
            for code in AXES:
                fcntl.ioctl(self.fd, write_ioctl(103), code)
                low, high = (-1, 1) if code >= 16 else (0, 32767) if code in (2, 5) else (-32767, 32767)
                setup = struct.pack('<H2x6i', code, 0, low, high, 0, 0, 0)
                fcntl.ioctl(self.fd, write_ioctl(4, len(setup)), setup)
            name = f'My-pc iOS Gamepad {slot+1}'.encode()
            setup = struct.pack('<HHHH80sI', 3, 0x045e, 0x028e, 1, name, 0)
            fcntl.ioctl(self.fd, write_ioctl(3, len(setup)), setup)
            fcntl.ioctl(self.fd, 0x5501)
            # Query this device's own inputN, then grant Steam access only to it.
            buffer = bytearray(128)
            fcntl.ioctl(self.fd, 0x80000000 | 128 << 16 | ord('U') << 8 | 44, buffer, True)
            sysname = buffer.split(b'\0', 1)[0].decode('ascii')
            if not sysname.startswith('input') or not sysname[5:].isdigit():
                raise ValueError('Unexpected uinput sysname')
            account = pwd.getpwnam('steam')
            sysdevice = pathlib.Path('/sys/class/input', sysname)
            deadline = time.monotonic()+2
            granted = False
            while time.monotonic() < deadline:
                for path in sysdevice.iterdir():
                    if (path.name.startswith('event') and path.name[5:].isdigit()) or (path.name.startswith('js') and path.name[2:].isdigit()):
                        node = pathlib.Path('/dev/input', path.name)
                        if node.exists():
                            os.chown(node, account.pw_uid, account.pw_gid); os.chmod(node, 0o660)
                            if path.name.startswith('event'): granted = True
                if granted:
                    # Let normal udev classification finish, then reapply ownership.
                    time.sleep(0.15)
                    for path in sysdevice.iterdir():
                        if path.name.startswith(('event','js')):
                            node = pathlib.Path('/dev/input', path.name)
                            if node.exists(): os.chown(node, account.pw_uid, account.pw_gid); os.chmod(node, 0o660)
                    break
                time.sleep(0.02)
            if not granted: raise RuntimeError('Gamepad event device did not appear')
            self.update(0, [0]*6)
        except BaseException:
            self.close()
            raise

    def update(self, buttons, axes):
        changed = []
        for kind, code, value in events(buttons, axes):
            if self.previous.get((kind, code)) != value:
                changed.append((kind, code, value)); self.previous[kind, code] = value
        if changed:
            # input_event has native signed longs: 24 bytes on ARM64/Linux.
            payload = b''.join(struct.pack('@llHHi', 0, 0, *event) for event in changed+[(0, 0, 0)])
            if os.write(self.fd, payload) != len(payload): raise OSError('Short uinput write')

    def close(self):
        if self.fd >= 0:
            try: self.fcntl.ioctl(self.fd, 0x5502)
            except OSError: pass
            os.close(self.fd); self.fd = -1


class Pads:
    def __init__(self, factory=UInput):
        self.factory = factory
        self.devices = {}
        self.sequences = {}
        self.updated = {}

    @property
    def mask(self): return sum(1 << slot for slot in self.devices)

    def apply(self, state, now):
        slot, connected, sequence, buttons, axes = state
        old = self.sequences.get(slot)
        if old is not None and not 0 < (sequence-old) & 0xffffffff < 0x80000000:
            return
        self.sequences[slot] = sequence; self.updated[slot] = now
        if not connected:
            if slot in self.devices: self.devices.pop(slot).close()
        else:
            if slot not in self.devices: self.devices[slot] = self.factory(slot)
            self.devices[slot].update(buttons, axes)

    def expire(self, now):
        for slot in list(self.devices):
            if now-self.updated[slot] > 2:
                self.devices.pop(slot).close()
                self.sequences.pop(slot, None)

    def reset(self):
        for device in self.devices.values(): device.close()
        self.devices.clear(); self.sequences.clear(); self.updated.clear()


def main():
    port = pathlib.Path('/dev/virtio-ports/org.my-pc.gamepad')
    while not port.exists(): time.sleep(0.25)
    fd = os.open(port, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
    parser, pads, last_ack = Parser(), Pads(), 0.0
    print('MYPC_CONTROLLER_READY=1', flush=True)
    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0.05)
            now = time.monotonic()
            if ready:
                try:
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        pads.reset(); parser = Parser(); time.sleep(0.1)
                    else:
                        for state in parser.feed(chunk): pads.apply(state, now)
                except OSError as error:
                    if error.errno not in (errno.EAGAIN, errno.EWOULDBLOCK): raise
            pads.expire(now)
            if now-last_ack >= 0.5:
                try:
                    os.write(fd, ACK.pack(b'ACK1', 1, pads.mask, 0)); last_ack = now
                except OSError as error:
                    if error.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EPIPE): raise
    finally:
        pads.reset(); os.close(fd)


if __name__ == '__main__': main()
