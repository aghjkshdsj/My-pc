#!/usr/bin/env python3
"""Run official ARM Steam under X11, without an account or Steam credentials.

This proves only a running CEF renderer and a visible client window on Linux.
It does not prove login, downloads, GPU acceleration or iPhone performance.
"""
import argparse
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('output', type=pathlib.Path)
parser.add_argument('--guest', action='store_true', help='Use the installed guest launcher and current home')
parser.add_argument('--timeout', type=int, default=300)
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
    with (output / 'dependencies.txt').open('w') as log:
        # UI and codec modules are dlopened after the executable has started.
        # Include them so one missing library does not mask the next one.
        paths = [steam / 'steamrtarm64' / name for name in ['steam', 'steamwebhelper']]
        paths += sorted((steam / 'steamrtarm64').glob('*.so*'))
        for path in paths:
            log.write(f'\n{path.name}:\n')
            log.flush()
            subprocess.run(['ldd', str(path)], stdout=log, stderr=subprocess.STDOUT, env=environment)
success = False
with (output / 'launch.log').open('w') as log:
    launcher = '/usr/local/bin/my-pc-steam' if args.guest else str(pathlib.Path(__file__).with_name('steam-session.sh'))
    process = subprocess.Popen(['bash', launcher],
                               stdout=log, stderr=subprocess.STDOUT, env=environment, start_new_session=True)
    try:
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            time.sleep(5)
            windows = subprocess.run(['xwininfo', '-root', '-tree'], capture_output=True, text=True, check=True).stdout
            processes = subprocess.run(['ps', '-eo', 'args'], capture_output=True, text=True, check=True).stdout
            (output / 'windows.txt').write_text(windows)
            (output / 'processes.txt').write_text(processes)
            renderer = any('steamwebhelper' in line and '--type=renderer' in line for line in processes.splitlines())
            if renderer and any('"Steam"' in line or '"Sign in to Steam"' in line for line in windows.splitlines()):
                success = True
                time.sleep(10)
                break
            if process.poll() is not None:
                break
        if success and args.guest:
            dependencies()
            print('MYPC_GUEST_STEAM_WINDOW_OK', flush=True)
            # Keep Steam and X alive for the host's screenshot and powerdown.
            while True:
                time.sleep(1)
    finally:
        subprocess.run(['scrot', str(output / 'desktop.png')], check=False)
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
    for path in [output / 'launch.log', output / 'dependencies.txt', *sorted((output / 'steam-logs').glob('*.txt'))]:
        if path.is_file():
            print(f'\n{path.name}:\n{path.read_text(errors="replace")[-16000:]}')
if not success:
    if args.guest:
        print('MYPC_GUEST_STEAM_FAILED', flush=True)
    raise SystemExit('ARM Steam did not present a client window with a CEF renderer. Inspect launch/dependency/Steam logs.')
print('PASS: ARM64 Steam client window and CEF renderer on Linux; no account login attempted')
