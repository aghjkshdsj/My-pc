#!/usr/bin/env python3
"""Account-free VM gate for the exact on-device diagnostic payload."""
import importlib.util
import json
import os
import pathlib
import tempfile

folder = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('hardware', folder/'hardware-test.py')
hardware = importlib.util.module_from_spec(spec); spec.loader.exec_module(hardware)
os.environ['MYPC_HARDWARE_CI'] = '1'
with tempfile.TemporaryDirectory() as temporary:
    env = hardware.environment(folder,temporary)
    for mode in ('arm64','fex'):
        for workers in (1,6):
            row = hardware.execute(folder,mode,'cpu',workers,env,10000)
            print('MYPC_HARDWARE_RUNTIME_CHECK '+json.dumps(row),flush=True)
            assert row['status']=='passed'
        row = hardware.execute(folder,mode,'gpu',1,env)
        print('MYPC_HARDWARE_RUNTIME_CHECK '+json.dumps(row),flush=True)
        assert row['status']=='passed' and row['accelerated'] and row['readback_ok'], 'Actual FEX/virgl shader pixels required'
print('MYPC_HARDWARE_RUNTIME_OK=1',flush=True)
# Reuse the existing desktop/input/shutdown checks after actual workloads.
os.execv('/usr/bin/python3',['python3','/usr/local/lib/my-pc/desktop-test.py'])
