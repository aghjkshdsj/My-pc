#!/usr/bin/env python3
"""Reuse only preview 23's unchanged payload; all Mac runtime gates still run.

That run's UI harness failed after the guest job had started. Avoid rebuilding
the same Linux/FEX payload for the harness-only repair. Any payload-source or
guest build-command change, expired artifact or unsuccessful guest job refuses
reuse. This does not reuse controller, shader, Steam or diagnostic gate results.
"""
import json
import os
import pathlib
import subprocess

RUN = 36803567684
HEAD = '0fcea240170033bd670b3a56cce53cf4c17c1150'
WORKFLOW = '.github/workflows/steam-arm-metal.yml'


def output(value):
    with open(os.environ['GITHUB_OUTPUT'],'a') as stream:
        stream.write('reuse='+str(value).lower()+'\n')
    print('Guest payload reuse: '+str(value).lower(),flush=True)


def command(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL,timeout=60)


def build_body(source):
    anchor = '      - name: Prepare a bare production runtime and validate preservation on the older disk\n'
    start = source.index(anchor)
    body = source.index('        run: |\n',start)
    end = source.index('      - uses: actions/upload-artifact@v4',body)
    return source[body:end]


try:
    repo = os.environ['GH_REPO']
    run = json.loads(command('gh','api',f'repos/{repo}/actions/runs/{RUN}'))
    assert run['head_sha']==HEAD
    jobs = json.loads(command('gh','api',f'repos/{repo}/actions/runs/{RUN}/jobs'))['jobs']
    assert any(job['name']=='guest' and job['conclusion']=='success' for job in jobs)
    artifacts = json.loads(command('gh','api',f'repos/{repo}/actions/runs/{RUN}/artifacts'))['artifacts']
    assert all(any(artifact['name']==name and not artifact['expired'] for artifact in artifacts)
               for name in ('linux-arm-guest','metal-steam-test-guest'))
    command('git','fetch','--depth=1','origin',HEAD)
    changed = set(command('git','diff','--name-only',HEAD,'HEAD','--','build/linux-arm','build/linux-arm-gpu').splitlines())
    assert changed <= {'build/linux-arm/test-gamepad-transport.py','build/linux-arm-gpu/reuse-guest-payload.py'}
    assert build_body(command('git','show',HEAD+':'+WORKFLOW))==build_body(pathlib.Path(WORKFLOW).read_text())
except (AssertionError,OSError,ValueError,KeyError,subprocess.SubprocessError):
    output(False)
else:
    output(True)
