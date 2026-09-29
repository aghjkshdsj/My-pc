#!/usr/bin/env python3
"""Publish bounded stack metadata, never arbitrary archived Steam log text."""
import json
import pathlib
import re
import sys

content = pathlib.Path(sys.argv[1]).read_text(errors='replace')
assert 'MYPC_TCTI_GDB_FINISHED' in content, 'GDB did not complete the isolated diagnostic'
signals = re.findall(r'received signal (SIGSEGV|SIGILL|SIGBUS|SIGABRT|SIGFPE|SIGTRAP)', content)
pcs = re.findall(r'MYPC_TCTI_GDB_PC=(0x[0-9a-fA-F]{1,16})', content)
frames = []
for line in content.splitlines():
    match = re.match(r'#(\d{1,2})\s+(0x[0-9a-fA-F]{1,16})\s+in\s+([A-Za-z0-9_:.<>?()@,+~* -]{1,128})', line)
    if match and int(match.group(1)) < 12:
        frames.append({'frame': int(match.group(1)), 'pc': match.group(2), 'symbol': match.group(3).strip()})
print('MYPC_TCTI_GDB_RESULT ' + json.dumps({
    'signals': signals[-8:], 'pc': pcs[-1:] or None,
    'frames': frames[-12:],
    'host_policy_denials': content.count('MYPC_NOJIT_POLICY_DENIED'),
    'login_gate_passed': 'MYPC_GUEST_STEAM_WINDOW_OK' in content,
}))
