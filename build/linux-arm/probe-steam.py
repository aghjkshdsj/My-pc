#!/usr/bin/env python3
"""Run official ARM Steam under X11, without an account or Steam credentials.

This proves only a running CEF renderer and a visible client window on Linux.
It does not prove login, downloads, GPU acceleration or iPhone performance.
"""
import argparse
import base64
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
from steam_window import client_window
from steam_cdp import login_interface
from steam_health import helper_started, process_health

parser = argparse.ArgumentParser()
parser.add_argument('output', type=pathlib.Path)
parser.add_argument('--guest', action='store_true', help='Use the installed guest launcher and current home')
parser.add_argument('--timeout', type=int, default=300)
parser.add_argument('--install-timeout', type=int, default=0,
                    help='Separate first-install budget before CEF starts; never renewed on helper restart')
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
home = pathlib.Path.home() if args.guest else output.parent / 'steam-probe-home'
home.mkdir(exist_ok=True)
steam = home / '.local/share/Steam'
if not args.guest:
    subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('steam-arm-fetch.py')),
                    '--destination', str(steam)], check=True)
environment = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / '.local/share'))
environment['LD_LIBRARY_PATH'] = str(steam / 'steamrtarm64')
def dependencies():
    missing = []
    with (output / 'dependencies.txt').open('w') as log:
        # UI and codec modules are dlopened after the executable has started.
        # Include them so one missing library does not mask the next one.
        paths = [steam / 'steamrtarm64' / name for name in ['steam', 'steamwebhelper']]
        paths += sorted((steam / 'steamrtarm64').glob('*.so*'))
        for path in paths:
            log.write(f'\n{path.name}:\n')
            log.flush()
            result = subprocess.run(['ldd', str(path)], capture_output=True, text=True, env=environment)
            log.write(result.stdout + result.stderr)
            missing += [f'{path.name}: {line.strip()}' for line in result.stdout.splitlines() if 'not found' in line]
    (output / 'missing-dependencies.txt').write_text('\n'.join(missing) + '\n')
success = False
with (output / 'launch.log').open('w') as log:
    launcher = '/usr/local/bin/my-pc-steam' if args.guest else str(pathlib.Path(__file__).with_name('steam-session.sh'))
    # Valve's ARM64 steamclient adds --remote-debugging-address=127.0.0.1.
    process = subprocess.Popen(['bash', launcher, '-cef-enable-debugging', '-devtools-port', '8080'],
                               stdout=log, stderr=subprocess.STDOUT, env=environment, start_new_session=True)
    try:
        started = time.monotonic()
        deadline = started + (args.install_timeout or args.timeout)
        cef_started = False
        next_progress = started
        stable_window = None
        stable_since = None
        while time.monotonic() < deadline:
            time.sleep(5)
            windows = subprocess.run(['xwininfo', '-root', '-tree'], capture_output=True, text=True, check=True).stdout
            processes = subprocess.run(['ps', '-eww', '-o', 'pid,ppid,comm,args'], capture_output=True, text=True, check=True).stdout
            (output / 'windows.txt').write_text(windows)
            (output / 'processes.txt').write_text(processes)
            readiness = login_interface(output)
            # An empty disk can spend many minutes in Valve's updater. Give
            # CEF its own bounded startup budget, once only, after that phase.
            helper_seen = helper_started(processes)
            if not cef_started and (helper_seen or readiness is not None):
                cef_started = True
                if args.install_timeout:
                    deadline = time.monotonic() + args.timeout
            if time.monotonic() >= next_progress:
                (output / 'steam-health.json').write_text(json.dumps(process_health(), indent=2) + '\n')
                print('MYPC_STEAM_PROGRESS ' + json.dumps({
                    'elapsed_seconds': int(time.monotonic() - started),
                    'phase': 'cef' if cef_started else 'install',
                    'login_ready': readiness is not None,
                    'launcher_running': process.poll() is None,
                }), flush=True)
                next_progress = time.monotonic() + 60
            window = client_window(windows, readiness is not None)
            (output / 'client-window.json').write_text(json.dumps(window, indent=2) + '\n')
            if process.poll() is not None:
                break
            if window is None:
                stable_window = stable_since = None
            elif window['id'] != stable_window:
                stable_window, stable_since = window['id'], time.monotonic()
            elif time.monotonic() - stable_since >= 10:
                success = True
                print(f'Client window remained mapped with a responsive login renderer: {window["title"]!r}', flush=True)
                print(json.dumps(readiness), flush=True)
                break
        if success and args.guest:
            dependencies()
            print('MYPC_GUEST_STEAM_WINDOW_OK', flush=True)
            # Keep Steam and X alive for the host's screenshot and powerdown.
            while True:
                time.sleep(1)
    finally:
        (output / 'steam-health.json').write_text(json.dumps(process_health(), indent=2) + '\n')
        subprocess.run(['scrot', str(output / 'desktop.png')], check=False)
        screenshot = output / 'desktop.png'
        if not args.guest and screenshot.is_file() and screenshot.stat().st_size <= 250_000:
            # Keep a small viewable diagnostic available when artifact delivery fails.
            print('MYPC_STEAM_SCREENSHOT_BASE64=' + base64.b64encode(screenshot.read_bytes()).decode(), flush=True)
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        logs = steam / 'logs'
        if logs.is_dir():
            shutil.copytree(logs, output / 'steam-logs', dirs_exist_ok=True)
        dependencies()
        if (steam / 'arm64-verification.json').is_file():
            shutil.copy2(steam / 'arm64-verification.json', output / 'arm64-verification.json')
if not success:
    diagnostics = [output / name for name in ['launch.log', 'windows.txt', 'processes.txt',
                                             'client-window.json', 'cef-targets.json', 'cef-readiness.json',
                                             'missing-dependencies.txt']]
    diagnostics += sorted(path for path in (output / 'steam-logs').glob('*') if path.suffix in {'.txt', '.log'})
    for path in diagnostics:
        if path.is_file():
            print(f'\n{path.name}:\n{path.read_text(errors="replace")[-16000:]}')
if not success:
    print('MYPC_STEAM_HEALTH ' + (output / 'steam-health.json').read_text().strip(), flush=True)
    if args.guest:
        print('MYPC_GUEST_STEAM_FAILED', flush=True)
    raise SystemExit('ARM Steam did not present a client window with a CEF renderer. Inspect launch/dependency/Steam logs.')
print('PASS: ARM64 Steam client window and CEF renderer on Linux; no account login attempted')
