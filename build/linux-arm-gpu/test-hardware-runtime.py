#!/usr/bin/env python3
"""Execute real ARM and x86-under-FEX workloads; validate output independently."""
import argparse
import importlib.util
import json
import pathlib
import tempfile

spec = importlib.util.spec_from_file_location('hardware', pathlib.Path(__file__).with_name('hardware-test.py'))
hardware = importlib.util.module_from_spec(spec); spec.loader.exec_module(hardware)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('folder', type=pathlib.Path)
    parser.add_argument('--cpu-only', action='store_true'); args = parser.parse_args()
    folder = args.folder.resolve()
    with tempfile.TemporaryDirectory() as temporary:
        env = hardware.environment(folder, temporary)
        for mode in ('arm64','fex'):
            for workers in (1,6):
                result = hardware.execute(folder,mode,'cpu',workers,env,iterations=10000)
                print('MYPC_HARDWARE_RUNTIME_CHECK ' + json.dumps(result),flush=True)
                assert result['status']=='passed'
                assert result['checksum']==hardware.checksum(workers,10000)
            if not args.cpu_only:
                result = hardware.execute(folder,mode,'gpu',1,env)
                print('MYPC_HARDWARE_RUNTIME_CHECK ' + json.dumps(result),flush=True)
                assert result['status']=='passed' and result['accelerated'], 'FEX graphics fallback cannot pass'
    print('PASS: real ARM64 and x86-64/FEX workload checksums' + ('' if args.cpu_only else ' and virgl shader pixels'))
