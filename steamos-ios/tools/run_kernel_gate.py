#!/usr/bin/env python3
"""Run real QEMU TCG and require fresh guest-produced ABI/checksum results."""
import argparse
import json
import pathlib
import subprocess
import uuid

def validate(text, nonce):
    lines = [x.split('MPC_LINUX_ABI ', 1)[1] for x in text.splitlines() if 'MPC_LINUX_ABI ' in x]
    assert len(lines) == 1, 'Missing/duplicate guest receipt'
    row = json.loads(lines[0])
    assert row['schema'] == 1 and row['run'] == nonce and row['failures'] == 0
    assert row['machine'] == row['elf_arch'] == 'aarch64' and row['page_bytes'] == 4096
    assert all(row[key] is True for key in ['signals', 'mmap_protection', 'pthread_tls_futex', 'fork_exec'])
    assert row['checksum'] == '1d250c45a7bbc87e'
    assert row['wall_ms'] >= 0 and row['cpu_ms'] >= 0
    assert 'MPC_LINUX_EXIT=0' in text
    return row

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('payload', type=pathlib.Path)
    args = parser.parse_args()
    nonce = uuid.uuid4().hex
    command = ['qemu-system-aarch64', '-machine', 'virt', '-cpu', 'max', '-accel', 'tcg,thread=multi,split-wx=on,tb-size=32',
               '-smp', '2', '-m', '512', '-nodefaults', '-nographic', '-serial', 'stdio', '-monitor', 'none',
               '-kernel', str(args.payload / 'Image'), '-initrd', str(args.payload / 'initramfs.cpio.gz'),
               '-append', 'console=ttyAMA0 rdinit=/init panic=1 mpc_run=' + nonce, '-no-reboot']
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    (args.payload / 'serial.log').write_text(result.stdout, encoding='utf-8')
    print(result.stdout)
    assert result.returncode == 0, 'Engine did not shut down successfully'
    row = validate(result.stdout, nonce)
    receipt = {'schema': 1, 'scope': 'hosted-linux-tcg-kernel-test', 'physical_iphone': False,
               'steamos': False, 'graphics_tested': False, 'engine_command': command, 'guest': row}
    (args.payload / 'kernel-test.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))
