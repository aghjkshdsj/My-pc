#!/usr/bin/env python3
"""Account-free VM gate for the exact on-device diagnostic payload."""
import importlib.util
import json
import os
import pathlib

folder = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('hardware', folder/'hardware-test.py')
hardware = importlib.util.module_from_spec(spec); spec.loader.exec_module(hardware)
os.environ['MYPC_HARDWARE_CI'] = '1'
try:
    import runpy
    runpy.run_path('/usr/local/lib/my-pc/controller/controller-ci.py',run_name='__main__')
    for kind in ('cpu','gpu'):
        updates = []
        def emit(state):
            updates.append(state)
            print('MYPC_HARDWARE_TEST '+json.dumps(state,separators=(',',':')),flush=True)
        # Exercise the same idle sampling, progress, heartbeat and child
        # cleanup path used by the phone, not just execute() in isolation.
        result = hardware.run(kind,folder,emit)
        assert result['status']=='complete', result
        assert result['idle_guest']['status']=='measured' and len(result['idle_guest']['per_core'])==6
        assert updates[0]['progress_percent']==0 and updates[-1]['progress_percent']==100
        assert all(a['heartbeat_seq']<b['heartbeat_seq'] and a['progress_percent']<=b['progress_percent']
                   for a,b in zip(updates,updates[1:]))
        for row in result['results']:
            print('MYPC_HARDWARE_RUNTIME_CHECK '+json.dumps(row),flush=True)
            assert row['status']=='passed'
            if kind=='gpu':
                assert row['accelerated'] and row['readback_ok'], 'Actual FEX/virgl shader pixels required'
        if kind=='cpu': assert [(r['mode'],r['workers']) for r in result['results']]==[('arm64',1),('arm64',6),('fex',1),('fex',6)]
    print('MYPC_HARDWARE_IDLE_PROGRESS_AND_HEARTBEAT_OK=1',flush=True)
except BaseException:
    print('MYPC_HARDWARE_RUNTIME_FAILED=1',flush=True)
    raise
print('MYPC_HARDWARE_RUNTIME_OK=1',flush=True)
# Reuse the existing desktop/input/shutdown checks after actual workloads.
os.execv('/usr/bin/python3',['python3','/usr/local/lib/my-pc/desktop-test.py'])
