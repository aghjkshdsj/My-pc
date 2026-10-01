#!/usr/bin/env python3
"""Reuse one completed GPU gate for the immediately following packaging repair.

All future rendering changes, or another child commit, run the full gates.
The reference run failed only its overstrict IPA size check, after GPU tests.
"""
import json
import os
import subprocess

RUN = '36659448881'
COMMIT = 'e53facc569f5b3e6ce4110f09fee1ff6fe726ecf'
ALLOWED = {'build/linux-arm/package-ipa.sh',
           'build/linux-arm-gpu/reuse-runtime-checks.py',
           '.github/workflows/steam-arm-metal.yml'}
REQUIRED = {'guest', 'qemu (ios)', 'qemu (macos)', 'ui', 'apple'}


def output(arguments):
    return subprocess.check_output(arguments, text=True).strip()


def reusable():
    # Inspect the raw object: checkout's shallow boundary hides HEAD^.
    parents = [line.split()[1] for line in output(['git', 'cat-file', '-p', 'HEAD']).splitlines()
               if line.startswith('parent ')]
    if parents != [COMMIT]:
        return False
    subprocess.run(['git', 'fetch', '--depth=1', 'origin', COMMIT], check=True)
    changed = set(output(['git', 'diff', '--name-only', COMMIT, 'HEAD']).splitlines())
    if not changed or not changed.issubset(ALLOWED):
        return False
    run = json.loads(output(['gh', 'run', 'view', RUN, '--json', 'headSha,status,conclusion']))
    assert run == {'headSha': COMMIT, 'status': 'completed', 'conclusion': 'failure'}, run
    jobs = json.loads(output(['gh', 'api', f'repos/{os.environ["GH_REPO"]}/actions/runs/{RUN}/jobs?per_page=100']))['jobs']
    checks = {job['name']: job for job in jobs if job['name'] in REQUIRED}
    assert set(checks) == REQUIRED
    assert all(job['status'] == 'completed' and job['conclusion'] == 'success' for job in checks.values())
    print(f'MYPC_REUSED_RUNTIME_CHECKS run={RUN} commit={COMMIT}; only packaging/repair-workflow inputs changed', flush=True)
    return True


if __name__ == '__main__':
    value = reusable()
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write('reuse=' + str(value).lower() + '\n')
