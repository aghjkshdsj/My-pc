#!/usr/bin/env python3
"""Independently observe reports produced through the phone control port."""
import importlib.util
import json
import os
import pathlib
import runpy
import time

folder = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('hardware_control_ci', folder/'hardware-control-ci.py')
control = importlib.util.module_from_spec(spec); spec.loader.exec_module(control)
os.environ['MYPC_HARDWARE_CI'] = '1'


def observe(directory=control.GUEST_DIRECTORY, checksums_path=folder/'checksums.json', timeout=600):
    """Read the runner's atomic report separately from the serial response.

    Update races are retried. The host waits for each guest marker before
    starting another test, so a later run cannot hide the completed report.
    """
    directory = pathlib.Path(directory)
    deadline = time.monotonic() + timeout
    completed, gpu_seen, heartbeats = set(), False, {}
    checksums = json.loads(pathlib.Path(checksums_path).read_text())
    print('MYPC_HARDWARE_GUEST_OBSERVER_READY=1', flush=True)
    while completed != {control.CPU_ID, control.CANCEL_GPU_ID, control.RETRY_GPU_ID}:
        control.require(time.monotonic() < deadline, 'Guest diagnostic observation deadline')
        try:
            with (directory/'state.json').open('rb') as stream: evidence = stream.read(control.MAX_FRAME + 1)
            with (directory/'runner.json').open('rb') as stream: raw = stream.read(control.MAX_FRAME + 1)
        except FileNotFoundError:
            time.sleep(0.01); continue
        control.require(len(evidence) <= control.MAX_FRAME and len(raw) <= control.MAX_FRAME,
                        'Private report exceeds limit')
        outer, runner = json.loads(evidence), json.loads(raw)
        control.require(set(outer) == {'schema', 'type', 'id', 'state'}
                        and outer['schema'] == 1 and outer['type'] == 'state'
                        and outer['id'] in {control.CPU_ID, control.CANCEL_GPU_ID, control.RETRY_GPU_ID},
                        'Private report request identity invalid')
        if outer['state'] != runner:
            time.sleep(0.01); continue
        state = control.state(runner)
        identifier = outer['id']
        expected_kind = 'cpu' if identifier == control.CPU_ID else 'gpu'
        control.require(state['kind'] == expected_kind, 'Private workload identity mismatch')
        previous = heartbeats.get(identifier)
        if previous:
            control.require(previous[0] == state['run'] and previous[1] <= state['heartbeat_seq']
                            and previous[2] <= state['progress_percent'], 'Private report regressed')
        heartbeats[identifier] = (state['run'], state['heartbeat_seq'], state['progress_percent'])
        if identifier == control.CANCEL_GPU_ID and control.gpu_work(state) and not gpu_seen:
            gpu_seen = True
            print('MYPC_HARDWARE_GUEST_GPU_WORK_OBSERVED=1', flush=True)
        if state['status'] != 'running' and identifier not in completed:
            expected_status = 'cancelled' if identifier == control.CANCEL_GPU_ID else 'complete'
            control.require(state['status'] == expected_status, 'Private workload terminal status invalid')
            if identifier == control.CANCEL_GPU_ID:
                control.require(gpu_seen, 'Cancellation happened before actual GPU work')
            else:
                for row in state['results']:
                    if row['kind'] == 'cpu':
                        control.require(row['checksum'] == checksums[f"{row['workers']}:1000000"],
                                        'Independent CPU checksum invalid')
                print('MYPC_HARDWARE_GUEST_RESULT ' + json.dumps(control.metrics(state), sort_keys=True), flush=True)
            completed.add(identifier)
            print(control.MARKERS[identifier], flush=True)
        time.sleep(0.01)


def main():
    try:
        # Retain controller axes/buttons/hotplug checks as the Steam user.
        runpy.run_path('/usr/local/lib/my-pc/controller/controller-ci.py', run_name='__main__')
        observe()
        print('MYPC_HARDWARE_IDLE_PROGRESS_AND_HEARTBEAT_OK=1', flush=True)
        print('MYPC_HARDWARE_PRIVATE_CONTROL_AND_CANCEL_OK=1', flush=True)
        print('MYPC_HARDWARE_RUNTIME_OK=1', flush=True)
    except BaseException:
        # No traceback, subprocess stderr, commands or Steam/account logs.
        print('MYPC_HARDWARE_RUNTIME_FAILED=1', flush=True)
        raise SystemExit(1)
    os.execv('/usr/bin/python3', ['python3', '/usr/local/lib/my-pc/desktop-test.py'])


if __name__ == '__main__': main()
