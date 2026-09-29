#!/usr/bin/env python3
"""Publish bounded stack metadata, never arbitrary archived Steam log text."""
import json
import pathlib
import re
import sys

def summarize(content):
    assert 'MYPC_TCTI_GDB_FINISHED' in content, 'GDB did not finish the isolated diagnostic'
    signals = re.findall(r'received signal (SIGSEGV|SIGILL|SIGBUS|SIGABRT|SIGFPE|SIGTRAP)', content)
    pcs = re.findall(r'MYPC_TCTI_GDB_PC=(0x[0-9a-fA-F]{1,16})', content)
    frames = []
    for line in content.splitlines():
        match = re.match(r'#(\d{1,2})\s+(0x[0-9a-fA-F]{1,16})\s+in\s+([A-Za-z0-9_:.<>?()@,+~* -]{1,128})', line)
        if match and int(match.group(1)) < 12:
            frames.append({'frame': int(match.group(1)), 'pc': match.group(2), 'symbol': match.group(3).strip()})
    module = None
    if pcs:
        pc = int(pcs[-1], 16)
        allowed = {'steam', 'steamclient.so', 'steamui.so', 'libtier0_s.so',
                   'libc.so.6', 'ld-linux-aarch64.so.1', 'libpthread.so.0',
                   'libstdc++.so.6', 'libgcc_s.so.1', 'libm.so.6'}
        for line in content.splitlines():
            match = re.match(r'\s*(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+0x[0-9a-fA-F]+\s+(0x[0-9a-fA-F]+)\s+(?:[rwxps-]+\s+)?(/\S+)\s*$', line)
            if match and int(match[1], 16) <= pc < int(match[2], 16):
                name = pathlib.PurePosixPath(match[4]).name
                module = {'name': name if name in allowed else 'other',
                          'file_offset': hex(pc - int(match[1], 16) + int(match[3], 16))}
                break
    return {
        'signals': signals[-8:], 'pc': pcs[-1:] or None, 'frames': frames[-12:],
        'module': module, 'full_local_log': True,
        'inferior_exit_codes': re.findall(r'exited with code (0[0-7]{1,4}|[0-9]{1,3})', content)[-4:],
        'inferior_exited_normally': 'exited normally' in content,
        'no_registers': 'No registers' in content,
        'ptrace_denied': bool(re.search(r'ptrace[^\n]*(?:not permitted|denied)', content, re.I)),
        'startup_errors': len(re.findall(r'Cannot exec|No executable file|During startup program terminated|vfork:', content)),
        'host_policy_denials': content.count('MYPC_NOJIT_POLICY_DENIED'),
        'login_gate_passed': 'MYPC_GUEST_STEAM_WINDOW_OK' in content,
    }


def main():
    content = pathlib.Path(sys.argv[1]).read_text(errors='replace')
    matches = re.findall(r'^MYPC_TCTI_GDB_RESULT (\{[^\r\n]{1,4096}\})$', content, re.MULTILINE)
    assert matches, 'Guest did not summarize the complete local debugger log'
    result = json.loads(matches[-1])
    assert set(result) == set(summarize('MYPC_TCTI_GDB_FINISHED')), 'Unexpected debugger summary schema'
    print('MYPC_TCTI_GDB_RESULT ' + json.dumps(result), flush=True)
    assert result['pc'] and result['signals'], 'No stopped PC and signal captured; crash remains unresolved'


if __name__ == '__main__':
    main()
