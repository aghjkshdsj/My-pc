#!/usr/bin/env python3
"""Run official ARM Steam under X11, without an account or Steam credentials.

This proves only a running CEF renderer and a visible client window on Linux.
It does not prove login, downloads, GPU acceleration or iPhone performance.
"""
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time

output = pathlib.Path(sys.argv[1]).resolve()
output.mkdir(parents=True, exist_ok=True)
home = output.parent / 'steam-probe-home'
home.mkdir(exist_ok=True)
steam = home / '.local/share/Steam'
subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('steam-arm-fetch.py')),
                '--destination', str(steam)], check=True)
environment = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / '.local/share'))
environment['LD_LIBRARY_PATH'] = str(steam / 'steamrtarm64')
with (output / 'dependencies.txt').open('w') as log:
    for name in ['steam', 'steamwebhelper', 'steamclient.so']:
        subprocess.run(['ldd', str(steam / 'steamrtarm64' / name)], stdout=log, stderr=subprocess.STDOUT, env=environment)
success = False
with (output / 'launch.log').open('w') as log:
    process = subprocess.Popen(['bash', str(pathlib.Path(__file__).with_name('steam-session.sh'))],
                               stdout=log, stderr=subprocess.STDOUT, env=environment, start_new_session=True)
    try:
        deadline = time.monotonic() + 300
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
        shutil.copy2(steam / 'arm64-verification.json', output / 'arm64-verification.json')
if not success:
    raise SystemExit('ARM Steam did not present a client window with a CEF renderer. Inspect launch/dependency/Steam logs.')
print('PASS: ARM64 Steam client window and CEF renderer on Linux; no account login attempted')
