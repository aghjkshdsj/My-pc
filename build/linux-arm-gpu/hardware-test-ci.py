#!/usr/bin/env python3
"""Account-free VM gate for the exact on-device diagnostic payload."""
import importlib.util
import json
import os
import pathlib
import subprocess
import tempfile
import time

folder = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('hardware', folder/'hardware-test.py')
hardware = importlib.util.module_from_spec(spec); spec.loader.exec_module(hardware)
os.environ['MYPC_HARDWARE_CI'] = '1'
try:
    import runpy
    runpy.run_path('/usr/local/lib/my-pc/controller/controller-ci.py',run_name='__main__')
    for kind in ('cpu','gpu'):
        updates = []
        # Execute the real phone CLI with no X11 terminal or inherited output
        # pipe. Independently observe its atomic results so broken serial
        # delivery cannot accidentally pass the production gate.
        with tempfile.TemporaryDirectory(prefix='my-pc-cli-gate-') as temporary:
            report = pathlib.Path(temporary)/'state.json'
            child = hardware.spawn_child(['python3','-u',str(folder/'hardware-test.py'),kind,
                '--result-file',str(report)],10,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            started = last_update = time.monotonic()
            last_sequence = 0
            try:
                while child.poll() is None:
                    if report.exists():
                        state = json.loads(report.read_text())
                        if state['heartbeat_seq']!=last_sequence:
                            updates.append(state); last_sequence=state['heartbeat_seq']; last_update=time.monotonic()
                    assert time.monotonic()-started<180, 'CLI test deadline'
                    assert time.monotonic()-last_update<15, 'CLI test heartbeat stopped'
                    time.sleep(0.02)
                assert child.returncode==0, 'Phone CLI failed'
                result = json.loads(report.read_text())
                if result['heartbeat_seq']!=last_sequence: updates.append(result)
            finally: hardware.stop_child(child)
        if result['status']!='complete':
            # This is the same account-free fixed benchmark schema exposed
            # by the phone. Never export subprocess stderr or command lines.
            print('MYPC_HARDWARE_CLI_FAILURE '+json.dumps({key:result[key] for key in
                ('kind','status','stage','heartbeat_seq','elapsed_s','results')}),flush=True)
        assert result['status']=='complete', 'Phone CLI did not complete'
        assert result['idle_guest']['status']=='measured' and len(result['idle_guest']['per_core'])==6
        assert updates[0]['progress_percent']<10 and updates[-1]['progress_percent']==100
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
    import traceback
    traceback.print_exc()
    # Print the cause before the failure marker: the host stops the VM as
    # soon as it sees that marker, and would otherwise lose the traceback.
    print('MYPC_HARDWARE_RUNTIME_FAILED=1',flush=True)
    raise
print('MYPC_HARDWARE_RUNTIME_OK=1',flush=True)
# Reuse the existing desktop/input/shutdown checks after actual workloads.
os.execv('/usr/bin/python3',['python3','/usr/local/lib/my-pc/desktop-test.py'])
