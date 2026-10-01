#!/usr/bin/env python3
"""Require virgl shader output AND moving GL pixels through the iPhone bridge."""
import argparse
import functools
import hashlib
import http.server
import json
import os
import pathlib
import socket
import struct
import subprocess
import tempfile
import threading
import time


def frame_stats(path):
    if not path.exists():
        return None
    data = path.read_bytes()
    if len(data) < 12:
        return None
    width, height, stride = struct.unpack('<III', data[:12])
    if not (1 <= width <= 4096 and 1 <= height <= 4096 and width * 4 <= stride <= 16384):
        return None
    if len(data) != 12 + stride * height:
        return None
    red = green = blue = 0
    # Sample actual BGRA callback pixels. Primary gear colors distinguish the
    # animated GL window from the console and solid desktop background.
    for row in range(0, height, 2):
        for column in range(0, width, 2):
            offset = 12 + row * stride + column * 4
            b, g, r = data[offset:offset + 3]
            red += r > 150 and g < 80 and b < 80
            green += g > 150 and r < 80 and b < 80
            blue += b > 150 and r < 80 and g < 80
    return {'width': width, 'height': height, 'stride': stride,
            'red': red, 'green': green, 'blue': blue,
            'sha256': hashlib.sha256(data).hexdigest()}


def frame_digest(path):
    stats = frame_stats(path)
    if stats is None or min(stats['red'], stats['green'], stats['blue']) < 128:
        return None
    return stats['sha256']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('guest')
    parser.add_argument('runtime')
    args = parser.parse_args()
    guest, runtime = pathlib.Path(args.guest).resolve(), pathlib.Path(args.runtime).resolve()
    launcher = runtime / 'gpu-host-launcher'
    library = runtime / 'Frameworks/qemu-aarch64-softmmu.framework/Versions/A/qemu-aarch64-softmmu'
    assert launcher.exists() and library.exists()
    log = guest / 'gpu-boot.log'
    with tempfile.TemporaryDirectory(prefix='mypc-gpu-') as temporary:
        temporary = pathlib.Path(temporary)
        (temporary / 'probe.txt').write_text('my-pc-network-ok\n')
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 18080),
            functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(temporary)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        control = temporary / 'qmp.sock'
        frame = guest / 'gpu-frame.bgra'
        environment = os.environ.copy()
        environment['MYPC_GPU_FRAME_PATH'] = str(frame)
        command = [str(launcher), str(library), '-no-user-config', '-nodefaults',
            '-machine', 'virt-10.0,highmem=off', '-cpu', 'max,sve=off,sme=off',
            '-accel', 'tcg,thread=multi,tb-size=256,split-wx=on', '-smp', '6', '-m', '2048',
            '-kernel', str(guest / 'Image'), '-initrd', str(guest / 'initrd.img'),
            '-append', 'console=ttyAMA0 root=/dev/vda rw my_pc_desktop_test=1 my_pc_gpu_test=1 panic=-1',
            '-object', 'iothread,id=linux-disk-io,poll-max-ns=0',
            '-blockdev', json.dumps({'driver': 'file', 'filename': str(guest / 'rootfs.raw'),
                'node-name': 'linux-file', 'aio': 'threads', 'cache': {'direct': False, 'no-flush': False}}),
            '-blockdev', json.dumps({'driver': 'raw', 'file': 'linux-file', 'node-name': 'linux-root'}),
            '-device', 'virtio-blk-pci,drive=linux-root,iothread=linux-disk-io',
            '-netdev', 'user,id=net0', '-device', 'virtio-net-pci,netdev=net0,romfile=',
            '-device', 'virtio-gpu-gl-pci,xres=1280,yres=800',
            '-device', 'qemu-xhci', '-device', 'usb-tablet', '-device', 'usb-kbd',
            '-display', 'egl-headless,gl=es', '-serial', 'stdio', '-monitor', 'none',
            '-qmp', f'unix:{control},server=on,wait=off', '-no-reboot', '-L', str(runtime / 'qemu')]
        process = None
        try:
            with log.open('w') as output:
                process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, env=environment)
                deadline, report = time.monotonic() + 1200, 0
                while 'MYPC_GUEST_GPU_SHADER_OK' not in log.read_text(errors='replace'):
                    assert process.poll() is None, 'GPU guest exited before the shader result'
                    assert time.monotonic() < deadline, 'GPU guest shader test timed out'
                    if time.monotonic() > report:
                        print('Waiting for the isolated virgl shader test', flush=True)
                        report = time.monotonic() + 60
                    time.sleep(1)
                content = log.read_text(errors='replace')
                assert 'MYPC_HOST_GL_RENDERER=ANGLE' in content and 'Metal' in content
                assert 'MYPC_LINUX_NETWORK_OK' in content and 'MYPC_LINUX_PERSISTENCE_OK' in content
                print('MYPC_GUEST_GPU_SHADER_OK', flush=True)
                hashes, deadline, report = set(), time.monotonic() + 120, 0
                while len(hashes) < 2:
                    digest = frame_digest(frame)
                    if digest:
                        hashes.add(digest)
                    if time.monotonic() > report:
                        print('MYPC_GPU_CALLBACK ' + json.dumps(frame_stats(frame)), flush=True)
                        report = time.monotonic() + 20
                    assert process.poll() is None, 'GPU guest exited before display readback'
                    assert time.monotonic() < deadline, 'Moving gear pixels did not reach the iPhone display callback'
                    time.sleep(1)
                print('MYPC_GPU_BRIDGE_MOVING_PIXELS_OK', flush=True)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(10); client.connect(str(control))
                    stream = client.makefile('rwb')
                    assert 'QMP' in json.loads(stream.readline())
                    def request(name, arguments=None):
                        message = {'execute': name, 'id': name}
                        if arguments is not None: message['arguments'] = arguments
                        stream.write(json.dumps(message).encode() + b'\n'); stream.flush()
                        while True:
                            reply = json.loads(stream.readline())
                            if reply.get('id') == name:
                                assert 'return' in reply, 'GPU control command failed'
                                return
                    request('qmp_capabilities')
                    request('screendump', {'filename': str(guest / 'gpu-desktop.ppm')})
                    request('system_powerdown')
                process.wait(timeout=360)
                assert process.returncode == 0, 'GPU guest did not shut down cleanly'
        finally:
            if process and process.poll() is None:
                process.kill(); process.wait()
            server.shutdown()
    print('PASS: ANGLE Metal host, virgl guest shader/readback, moving pixels through the iPhone bridge and clean shutdown')


if __name__ == '__main__':
    main()
