#!/usr/bin/env python3
"""Boot a real ARM64 kernel twice; require networking and durable disk writes."""
import functools
import argparse
import http.server
import json
import os
import pathlib
import subprocess
import socket
import sys
import tempfile
import threading
import time

parser = argparse.ArgumentParser()
parser.add_argument("guest")
parser.add_argument("--launcher")
parser.add_argument("--library")
parser.add_argument("--expect-existing", action="store_true")
parser.add_argument("--display", action="store_true")
parser.add_argument("--desktop", action="store_true")
parser.add_argument("--steam", action="store_true", help="Launch full Steam in the actual Linux guest")
args = parser.parse_args()
if args.desktop and args.steam:
    parser.error('Choose one desktop test mode')
guest = pathlib.Path(args.guest).resolve()
with tempfile.TemporaryDirectory() as directory:
    pathlib.Path(directory, "probe.txt").write_text("my-pc-network-ok\n")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 18080), functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for boot in ((4,) if args.steam else (3,) if args.desktop else (1, 2)):
            command = ["qemu-system-aarch64", "-machine", "virt", "-cpu", "cortex-a72", "-accel", "tcg,thread=multi,tb-size=128", "-smp", "2", "-m", "768", "-display", "none", "-monitor", "none", "-serial", "stdio", "-no-reboot", "-kernel", str(guest / "Image"), "-initrd", str(guest / "initrd.img"), "-append", "console=ttyAMA0 root=/dev/vda rw my_pc_smoke=1 panic=-1", "-drive", f"file={guest / 'rootfs.raw'},format=raw,if=virtio", "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0,romfile="]
            if args.launcher:
                if not args.library:
                    raise SystemExit("--launcher requires --library")
                command[:1] = [str(pathlib.Path(args.launcher).resolve()), str(pathlib.Path(args.library).resolve())]
                command += ["-L", str(pathlib.Path(args.launcher).resolve().parent / "qemu")]
            environment = os.environ.copy()
            if args.display or args.desktop or args.steam:
                command += ["-device", "virtio-gpu-pci,xres=960,yres=540"]
            if args.display:
                environment["MYPC_TEST_DISPLAY"] = "1"
            if args.desktop or args.steam:
                command[command.index("-m") + 1] = "2048"
                mode = 'steam' if args.steam else 'desktop'
                command[command.index("-append") + 1] = f"console=ttyAMA0 root=/dev/vda rw my_pc_{mode}_test=1 panic=-1"
                control = pathlib.Path(directory, "qmp.sock")
                command += ["-qmp", f"unix:{control},server=on,wait=off", "-device", "qemu-xhci", "-device", "usb-tablet", "-device", "usb-kbd"]
            log = guest / f"boot-{boot}.log"
            with log.open("w") as output:
                process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, env=environment)
                try:
                    if args.desktop or args.steam:
                        marker = 'MYPC_GUEST_STEAM_WINDOW_OK' if args.steam else 'MYPC_DESKTOP_READY'
                        deadline = time.monotonic() + (1500 if args.steam else 300)
                        while marker not in log.read_text(errors="replace"):
                            if args.steam and 'MYPC_GUEST_STEAM_FAILED' in log.read_text(errors="replace"):
                                raise RuntimeError('Steam in guest failed: ' + log.read_text(errors='replace')[-16000:])
                            if process.poll() is not None or time.monotonic() > deadline:
                                raise RuntimeError("Desktop did not become ready: " + log.read_text(errors="replace")[-8000:])
                            time.sleep(1)
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                            client.settimeout(10)
                            client.connect(str(control))
                            stream = client.makefile("rwb")
                            assert "QMP" in json.loads(stream.readline()), "Invalid QMP greeting"
                            def request(name, arguments=None):
                                message = {"execute": name, "id": name}
                                if arguments is not None:
                                    message["arguments"] = arguments
                                stream.write(json.dumps(message).encode() + b"\n")
                                stream.flush()
                                while True:
                                    reply = json.loads(stream.readline())
                                    if reply.get("id") == name:
                                        assert "return" in reply, reply
                                        return
                            request("qmp_capabilities")
                            request("screendump", {"filename": str(guest / ("steam.ppm" if args.steam else "desktop.ppm"))})
                            for down in (() if args.steam else (True, False)):
                                request("input-send-event", {"events": [
                                    {"type": "abs", "data": {"axis": "x", "value": 16000}},
                                    {"type": "abs", "data": {"axis": "y", "value": 16000}},
                                    {"type": "btn", "data": {"button": "left", "down": down}}
                                ]})
                                time.sleep(0.1)
                            if not args.steam:
                                # Same 10 ms transition pacing as the iPhone keyboard.
                                def key(code, down):
                                    request('input-send-event', {'events': [{'type': 'key', 'data': {'key': {'type': 'qcode', 'data': code}, 'down': down}}]})
                                    time.sleep(0.01)
                                for code, shift in [('s', True), ('t', False), ('e', False), ('a', False), ('m', False), ('spc', False), ('1', False), ('2', False), ('3', False), ('1', True), ('ret', False)]:
                                    if shift: key('shift', True)
                                    key(code, True)
                                    key(code, False)
                                    if shift: key('shift', False)
                            deadline = time.monotonic() + 60
                            while not args.steam and "MYPC_DESKTOP_INPUT_OK" not in log.read_text(errors="replace"):
                                if process.poll() is not None or time.monotonic() > deadline:
                                    raise RuntimeError("Desktop input failed: " + log.read_text(errors="replace")[-8000:])
                                time.sleep(0.2)
                            request("system_powerdown")
                    try:
                        process.wait(timeout=360)
                    except subprocess.TimeoutExpired:
                        print(log.read_text(errors="replace")[-12000:])
                        raise
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            content = log.read_text(errors="replace")
            print(content[-6000:])
            required = ["MYPC_LINUX_ARM64_BOOTED", "MYPC_LINUX_NETWORK_OK", "MYPC_LINUX_SMOKE_OK", "MYPC_LINUX_PERSISTENCE_WRITTEN" if boot == 1 and not args.expect_existing else "MYPC_LINUX_PERSISTENCE_OK"]
            if args.display:
                required.append("MYPC_APPLE_FRAMEBUFFER_OK")
            if args.desktop:
                required += ["MYPC_DESKTOP_MOUSE_OK", "MYPC_DESKTOP_KEYBOARD_OK", "MYPC_DESKTOP_INPUT_OK"]
            if args.steam:
                required += ["MYPC_GUEST_STEAM_WINDOW_OK"]
            if process.returncode or "MYPC_LINUX_FAIL:" in content or any(marker not in content for marker in required):
                raise SystemExit(f"ARM Linux boot {boot} failed; inspect {log}")
    finally:
        server.shutdown()
print("PASS: ARM64 Linux boot, networking, persistence, clean shutdown" + (", full Steam window and CEF in TCG guest" if args.steam else ", X11 mouse and keyboard" if args.desktop else " (two boots)"))
