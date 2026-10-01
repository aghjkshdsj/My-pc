#!/usr/bin/env python3
"""Boot a real ARM64 kernel twice; require networking and durable disk writes."""
import functools
import argparse
import http.server
import json
import os
import pathlib
import re
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
parser.add_argument("--controller", action="store_true", help="Require real virtio-serial/uinput gamepad observations")
parser.add_argument("--hardware-control-ci", type=pathlib.Path, help="Exercise the private phone diagnostic port with the fixed CI harness")
parser.add_argument("--interpreter", action="store_true", help="Use non-executable translation storage and longer boot deadlines")
parser.add_argument("--deny-jit-policy", action="store_true", help="Require the CI-only allocation guard and no attempts to generate executable host code")
parser.add_argument("--cpus", type=int, default=2)
parser.add_argument("--verify-cpu-count", action="store_true", help="Require the new guest's online CPU count marker")
parser.add_argument("--resolution", choices=['960x540', '1280x800'], default='1280x800')
args = parser.parse_args()
display_width, display_height = map(int, args.resolution.split('x'))
if not 1 <= args.cpus <= 64:
    parser.error('--cpus must be between 1 and 64')
if args.desktop and args.steam:
    parser.error('Choose one desktop test mode')
if args.deny_jit_policy and (not args.interpreter or not args.launcher):
    parser.error('--deny-jit-policy requires --interpreter and a guarded --launcher')
if args.hardware_control_ci and (not args.desktop or args.cpus != 6 or not args.controller):
    parser.error('--hardware-control-ci requires --desktop --cpus 6 --controller')
guest = pathlib.Path(args.guest).resolve()
with tempfile.TemporaryDirectory() as directory:
    pathlib.Path(directory, "probe.txt").write_text("my-pc-network-ok\n")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 18080), functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for boot in ((4,) if args.steam else (3,) if args.desktop else (1, 2)):
            command = ["qemu-system-aarch64", "-machine", "virt", "-cpu", "max,sve=off,sme=off", "-accel", "tcg,thread=multi,tb-size=128", "-smp", "2", "-m", "768", "-display", "none", "-monitor", "none", "-serial", "stdio", "-no-reboot", "-kernel", str(guest / "Image"), "-initrd", str(guest / "initrd.img"), "-append", "console=ttyAMA0 root=/dev/vda rw my_pc_smoke=1 panic=-1", "-drive", f"file={guest / 'rootfs.raw'},format=raw,if=virtio", "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0,romfile="]
            if args.launcher:
                if not args.library:
                    raise SystemExit("--launcher requires --library")
                command[:1] = [str(pathlib.Path(args.launcher).resolve()), str(pathlib.Path(args.library).resolve())]
                command += ["-L", str(pathlib.Path(args.launcher).resolve().parent / "qemu")]
            if args.interpreter:
                command[command.index('-accel') + 1] += ',split-wx=off'
            environment = os.environ.copy()
            command[command.index('-smp') + 1] = str(args.cpus)
            if args.display or args.desktop or args.steam:
                command += ["-device", f"virtio-gpu-pci,xres={display_width},yres={display_height}"]
            if args.display:
                environment["MYPC_TEST_DISPLAY"] = "1"
            if args.desktop or args.steam:
                command[command.index("-m") + 1] = "2048"
                mode = 'steam' if args.steam else 'desktop'
                command[command.index("-append") + 1] = f"console=ttyAMA0 root=/dev/vda rw my_pc_{mode}_test=1 panic=-1"
                control = pathlib.Path(directory, "qmp.sock")
                command += ["-qmp", f"unix:{control},server=on,wait=off", "-device", "qemu-xhci", "-device", "usb-tablet", "-device", "usb-kbd"]
            if args.verify_cpu_count:
                command[command.index('-append') + 1] += f' my_pc_expected_cpus={args.cpus}'
            log = guest / f"boot-{boot}.log"
            gamepad_path = pathlib.Path(directory, 'gamepad.sock')
            if args.controller:
                command += ['-device','virtio-serial-pci,id=linux-gamepads',
                    '-chardev',f'socket,id=linux-gamepads,path={gamepad_path},server=on,wait=off',
                    '-device','virtserialport,bus=linux-gamepads.0,chardev=linux-gamepads,name=org.my-pc.gamepad']
            diagnostics_path = pathlib.Path(directory, 'diagnostics.sock')
            if args.hardware_control_ci:
                command += ['-device', 'virtio-serial-pci,id=linux-diagnostics',
                    '-chardev', f'socket,id=linux-diagnostics,path={diagnostics_path},server=on,wait=off',
                    '-device', 'virtserialport,bus=linux-diagnostics.0,chardev=linux-diagnostics,name=org.my-pc.diagnostics']
            controller_stop = threading.Event()
            hardware_done, hardware_failed, hardware_result = threading.Event(), threading.Event(), {}
            with log.open("w") as output:
                process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, env=environment)
                if args.hardware_control_ci:
                    def exercise_hardware():
                        try:
                            import importlib.util
                            spec = importlib.util.spec_from_file_location('hardware_control_ci', args.hardware_control_ci.resolve())
                            harness = importlib.util.module_from_spec(spec); spec.loader.exec_module(harness)
                            hardware_result.update(harness.run_socket(diagnostics_path,
                                lambda: log.read_text(errors='replace'), controller_stop))
                        except BaseException:
                            hardware_failed.set()
                            print('MYPC_HARDWARE_HOST_CONTROL_FAILED=1', flush=True)
                        finally: hardware_done.set()
                    threading.Thread(target=exercise_hardware, daemon=True).start()
                if args.controller:
                    def send_controller():
                        import struct
                        deadline=time.monotonic()+300
                        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as pad:
                            while not controller_stop.is_set():
                                try: pad.connect(str(gamepad_path)); break
                                except OSError:
                                    if time.monotonic()>deadline: return
                                    controller_stop.wait(0.1)
                            pad.settimeout(1)
                            # The socket exists before Linux opens virtio-serial.
                            # Wait for its ACK instead of buffering stale input
                            # and filling QEMU's receive buffer during boot.
                            pending=bytearray(); acknowledged=False
                            while not controller_stop.is_set() and time.monotonic()<deadline:
                                try: chunk=pad.recv(256)
                                except socket.timeout: continue
                                except OSError: return
                                if not chunk: return
                                pending.extend(chunk)
                                while len(pending)>=16:
                                    start=pending.find(b'ACK1')
                                    if start<0: del pending[:-3]; break
                                    if start: del pending[:start]
                                    if len(pending)<16: break
                                    magic,version,mask,padding=struct.unpack('<4sIII',pending[:16])
                                    del pending[:16]
                                    if magic==b'ACK1' and version==1 and mask<16 and padding==0:
                                        acknowledged=True
                                if acknowledged: break
                            if not acknowledged: return
                            print('MYPC_GAMEPAD_HOST_ACK_READY=1',flush=True)
                            start=None; sequence=0; finished=False
                            while not controller_stop.is_set():
                                if not finished:
                                    evidence=log.read_text(errors='replace')
                                    finished='MYPC_CONTROLLER_EVDEV_ANALOG_BUTTONS_HOTPLUG_OK=1' in evidence
                                    if start is None and 'MYPC_CONTROLLER_OBSERVER_READY=1' in evidence:
                                        start=time.monotonic()
                                # Creating/destroying devices and pressing every
                                # button before X11/the observer starts races
                                # udev and can invalidate the observer's fd.
                                phase=(time.monotonic()-start)%12 if start is not None and not finished else None
                                connected=phase is None or not 8<=phase<9
                                pressed=phase is not None and (phase<4 or phase>=9)
                                sequence=(sequence+1)&0xffffffff
                                axes=(-16000,14000,12000,-8000,8192,24576) if connected and pressed else (0,)*6
                                data=struct.pack('<4sBBHII6hI',b'MPG1',0,int(connected),0,sequence,0xf7f9 if connected and pressed else 0,*axes,0)
                                try:
                                    pad.sendall(data)
                                    # Drain bounded acknowledgements, without waiting for one.
                                    if select.select([pad],[],[],0)[0]: pad.recv(256)
                                except OSError: return
                                controller_stop.wait(0.05)
                    import select
                    threading.Thread(target=send_controller,daemon=True).start()
                try:
                    if args.desktop or args.steam:
                        marker = 'MYPC_GUEST_STEAM_WINDOW_OK' if args.steam else 'MYPC_DESKTOP_READY'
                        deadline = time.monotonic() + (900 if args.hardware_control_ci else 2700 if args.steam else 1800 if args.interpreter else 300)
                        reported = set()
                        while marker not in log.read_text(errors="replace"):
                            if hardware_failed.is_set():
                                raise RuntimeError('Private diagnostic control failed')
                            # Only forward bounded, fixed-schema progress. Never
                            # expose arbitrary guest log lines as heartbeat data.
                            for item in re.findall(r'MYPC_STEAM_PROGRESS (\{[^\r\n]{1,256}\})', log.read_text(errors='replace')):
                                if item in reported:
                                    continue
                                reported.add(item)
                                try:
                                    state = json.loads(item)
                                except ValueError:
                                    continue
                                if (set(state) == {'elapsed_seconds', 'phase', 'login_ready', 'launcher_running'}
                                        and type(state['elapsed_seconds']) is int and 0 <= state['elapsed_seconds'] <= 3600
                                        and state['phase'] in ('install', 'cef')
                                        and type(state['login_ready']) is bool and type(state['launcher_running']) is bool):
                                    print('MYPC_STEAM_PROGRESS ' + json.dumps(state), flush=True)
                            if args.steam and 'MYPC_GUEST_STEAM_FAILED' in log.read_text(errors="replace"):
                                raise RuntimeError('Steam in guest failed: ' + log.read_text(errors='replace')[-16000:])
                            if process.poll() is not None or time.monotonic() > deadline:
                                raise RuntimeError("Desktop did not become ready: " + log.read_text(errors="replace")[-8000:])
                            time.sleep(1)
                        if args.hardware_control_ci:
                            if not hardware_done.wait(30) or hardware_failed.is_set():
                                raise RuntimeError('Private diagnostic control did not complete')
                            print('MYPC_HARDWARE_HOST_CONTROL_RESULT ' + json.dumps(hardware_result, sort_keys=True), flush=True)
                            print('MYPC_HARDWARE_HOST_PRIVATE_CONTROL_AND_CANCEL_OK=1', flush=True)
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
                            latencies = []
                            for sample in range(16):
                                started = time.monotonic()
                                request('input-send-event', {'events': [
                                    {'type': 'abs', 'data': {'axis': 'x', 'value': 8000 + sample * 64}},
                                    {'type': 'abs', 'data': {'axis': 'y', 'value': 8000}}]})
                                latencies.append((time.monotonic() - started) * 1000)
                            latencies.sort()
                            print('MYPC_QMP_INPUT_LATENCY ' + json.dumps({'samples': len(latencies),
                                'median_ms': round(latencies[len(latencies) // 2], 1),
                                'p95_ms': round(latencies[-1], 1)}), flush=True)
                            assert latencies[-1] < 2000, 'VM input processing exceeded two seconds after desktop readiness'
                            request("screendump", {"filename": str(guest / ("steam.ppm" if args.steam else "desktop.ppm"))})
                            screenshot = guest / ('steam.ppm' if args.steam else 'desktop.ppm')
                            with screenshot.open('rb') as image:
                                dimensions = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255\s', image.read(128))
                            assert dimensions and tuple(map(int, dimensions.groups())) == (display_width, display_height), 'Actual guest desktop does not match the requested resolution'
                            print(f'MYPC_DESKTOP_SIZE_OK={display_width}x{display_height}', flush=True)
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
                        process.wait(timeout=1800 if args.interpreter else 360)
                    except subprocess.TimeoutExpired:
                        if not args.hardware_control_ci: print(log.read_text(errors="replace")[-12000:])
                        raise
                finally:
                    controller_stop.set()
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            content = log.read_text(errors="replace")
            if not args.hardware_control_ci: print(content[-6000:])
            required = ["MYPC_LINUX_ARM64_BOOTED", "MYPC_LINUX_NETWORK_OK", "MYPC_LINUX_SMOKE_OK", "MYPC_LINUX_PERSISTENCE_WRITTEN" if boot == 1 and not args.expect_existing else "MYPC_LINUX_PERSISTENCE_OK"]
            if args.verify_cpu_count:
                required.append(f'MYPC_LINUX_CPU_COUNT={args.cpus}')
            if args.display:
                required.append("MYPC_APPLE_FRAMEBUFFER_OK")
            if args.deny_jit_policy:
                required += ['MYPC_NOJIT_POLICY_ACTIVE', 'MYPC_NOJIT_POLICY_SUMMARY denied_requests=0']
                if 'MYPC_NOJIT_POLICY_DENIED' in content:
                    raise SystemExit('Interpreter attempted a prohibited executable allocation')
            if args.desktop:
                required += ["MYPC_DESKTOP_MOUSE_OK", "MYPC_DESKTOP_KEYBOARD_OK", "MYPC_DESKTOP_INPUT_OK"]
            if args.steam:
                required += ["MYPC_GUEST_STEAM_WINDOW_OK"]
            if args.hardware_control_ci:
                required += ['MYPC_HARDWARE_PRIVATE_CONTROL_AND_CANCEL_OK=1', 'MYPC_HARDWARE_RUNTIME_OK=1']
            if process.returncode or "MYPC_LINUX_FAIL:" in content or any(marker not in content for marker in required):
                raise SystemExit(f"ARM Linux boot {boot} failed; inspect {log}")
    finally:
        server.shutdown()
print("PASS: ARM64 Linux boot, networking, persistence, clean shutdown" + (", full Steam window and CEF in TCG guest" if args.steam else ", X11 mouse and keyboard" if args.desktop else " (two boots)"))
